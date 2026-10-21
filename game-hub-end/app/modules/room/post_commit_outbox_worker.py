"""提交后 Outbox 独立 Worker。"""

import asyncio
import logging
from typing import Awaitable, Callable, List, Optional, Set

from app.core.time_utils import now_ms
from app.modules.room.post_turn_outbox_dispatcher import PostTurnOutboxDispatcher
from app.modules.room.post_turn_outbox_repository import (
    POST_TURN_OUTBOX_BATCH_SIZE,
    POST_TURN_OUTBOX_LEASE_MS,
    PostTurnOutboxRepository,
)
from app.modules.room.repository import RoomRepository

logger = logging.getLogger(__name__)

OUTBOX_WORKER_TICK_SECONDS = 0.05
OUTBOX_WORKER_ROOM_BATCH_SIZE = 20
OUTBOX_WORKER_REPAIR_INTERVAL_MS = 30000
OUTBOX_WORKER_CLEANUP_INTERVAL_MS = 60000


class PostCommitOutboxWorker(object):
    """独立消费房间级 Outbox 的后台 Worker。"""

    def __init__(
        self,
        outbox_repository: PostTurnOutboxRepository,
        outbox_dispatcher: PostTurnOutboxDispatcher,
        room_repository: Optional[RoomRepository] = None,
        clock: Optional[Callable[[], int]] = None,
        sleeper: Optional[Callable[[float], Awaitable[None]]] = None,
    ) -> None:
        """
        初始化 Outbox Worker。

        :param outbox_repository: Outbox 仓库。
        :param outbox_dispatcher: Outbox 分发器。
        :param room_repository: 房间仓库，用于修复 ready-room 索引。
        :param clock: 时钟函数，返回毫秒时间戳。
        :param sleeper: 异步睡眠函数。
        """
        self._outbox_repository = outbox_repository
        self._outbox_dispatcher = outbox_dispatcher
        self._room_repository = room_repository or RoomRepository()
        self._clock = clock or now_ms
        self._sleeper = sleeper or asyncio.sleep
        self._running = False
        self._task = None  # type: Optional[asyncio.Task]
        self._last_repair_at_ms = 0
        self._last_cleanup_at_ms = 0
        self._repair_scan_cursor = 0
        self._cleanup_scan_cursor = 0
        self._processed_total = 0
        self._tick_total = 0

    @property
    def processed_total(self) -> int:
        """
        返回累计处理条数指标。

        :return: 处理条数。
        """
        return int(self._processed_total)

    @property
    def tick_total(self) -> int:
        """
        返回累计 tick 次数指标。

        :return: tick 次数。
        """
        return int(self._tick_total)

    async def start(self) -> None:
        """
        启动 Outbox Worker 后台循环。

        :return: 无。
        """
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("post commit outbox worker started")

    async def stop(self) -> None:
        """
        停止 Outbox Worker 后台循环。

        :return: 无。
        """
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("post commit outbox worker stopped")

    async def tick_once(self) -> int:
        """
        执行一次 Outbox 扫描、领取与分发。

        :return: 本轮处理条数。
        """
        current_time = int(self._clock())
        self._tick_total += 1
        await self._maybe_repair_ready_index(current_time)
        await self._maybe_cleanup(current_time)
        records = await self._outbox_repository.claim_from_ready_rooms(
            OUTBOX_WORKER_ROOM_BATCH_SIZE,
            POST_TURN_OUTBOX_BATCH_SIZE,
            now_timestamp_ms=current_time,
            lease_ms=POST_TURN_OUTBOX_LEASE_MS,
        )
        processed = await self._outbox_dispatcher.dispatch_claimed_records(records)
        self._processed_total += int(processed)
        return int(processed)

    async def _run_loop(self) -> None:
        """
        后台循环按固定间隔执行 tick。

        :return: 无。
        """
        while self._running:
            try:
                await self.tick_once()
            except Exception:
                logger.exception("post commit outbox worker tick failed")
            await self._sleeper(OUTBOX_WORKER_TICK_SECONDS)

    async def _maybe_repair_ready_index(self, current_time_ms: int) -> None:
        """
        定期 SCAN Outbox records 与 playing-room 索引，修复 ready-room 派生索引。

        :param current_time_ms: 当前毫秒时间戳。
        :return: 无。
        """
        if current_time_ms - self._last_repair_at_ms < OUTBOX_WORKER_REPAIR_INTERVAL_MS:
            return
        self._last_repair_at_ms = current_time_ms
        next_cursor, repaired = await self._outbox_repository.scan_repair_ready_room_index(
            self._repair_scan_cursor,
        )
        self._repair_scan_cursor = int(next_cursor)
        playing_room_ids = await self._room_repository.list_playing_room_ids()
        if playing_room_ids:
            repaired += await self._outbox_repository.repair_ready_room_index(playing_room_ids)
            repaired += await self._outbox_dispatcher.recover_missing_terminal_finalize(
                playing_room_ids,
            )
            repaired += await self._outbox_dispatcher.recover_missing_post_turn_tasks(
                playing_room_ids,
            )
        if repaired > 0:
            logger.info("outbox ready-room index repaired, count=%s", repaired)

    async def _maybe_cleanup(self, current_time_ms: int) -> None:
        """
        定期清理各房间已到保留期的终态 Outbox 记录。

        :param current_time_ms: 当前毫秒时间戳。
        :return: 无。
        """
        if current_time_ms - self._last_cleanup_at_ms < OUTBOX_WORKER_CLEANUP_INTERVAL_MS:
            return
        self._last_cleanup_at_ms = current_time_ms
        next_cursor, removed_total = await self._outbox_repository.scan_cleanup_terminal_records(
            self._cleanup_scan_cursor,
            now_timestamp_ms=current_time_ms,
        )
        self._cleanup_scan_cursor = int(next_cursor)
        room_ids = list(await self._outbox_repository.list_ready_rooms())
        playing_room_ids = await self._room_repository.list_playing_room_ids()
        room_ids.extend(playing_room_ids)
        unique_room_ids = list(self._unique_room_ids(room_ids))
        for room_id in unique_room_ids:
            removed_total += await self._outbox_repository.cleanup(
                room_id,
                now_timestamp_ms=current_time_ms,
            )
        if removed_total > 0:
            logger.info("outbox cleanup removed records, count=%s", removed_total)

    def _unique_room_ids(self, room_ids: List[str]) -> Set[str]:
        """
        去重房间 ID 列表。

        :param room_ids: 房间 ID 列表。
        :return: 去重后的房间 ID 集合。
        """
        result = set()
        for room_id in room_ids:
            normalized_room_id = str(room_id or "").strip()
            if normalized_room_id:
                result.add(normalized_room_id)
        return result
