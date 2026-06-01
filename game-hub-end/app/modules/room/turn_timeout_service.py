"""房间对局回合截止时间扫描服务。"""

import asyncio
import logging
from typing import Awaitable, Callable, Dict, List, Optional

from app.core.time_utils import now_ms
from app.modules.room.repository import RoomRepository

logger = logging.getLogger(__name__)

SCAN_INTERVAL_MS = 1000
ACTIVE_MANAGED_REASONS = frozenset({"turnTimeout"})


class TurnTimeoutService(object):
    """扫描 playing 房间 runtime 回合截止时间并触发 active 托管。"""

    def __init__(self) -> None:
        """初始化回合超时扫描服务。"""
        self._repository = RoomRepository()
        self._mark_member_active_managed_handler = None  # type: Optional[Callable[[str, str, str], Awaitable[bool]]]
        self._running = False
        self._task = None  # type: Optional[asyncio.Task]

    def bind_mark_member_active_managed_handler(
        self,
        handler: Callable[[str, str, str], Awaitable[bool]],
    ) -> None:
        """
        绑定成员 active 托管处理函数。

        :param handler: ``mark_member_active_managed(room_id, player_id, reason) -> bool``。
        :return: 无。
        """
        self._mark_member_active_managed_handler = handler

    async def start(self) -> None:
        """
        启动后台回合超时扫描循环。

        :return: 无。
        """
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """
        停止后台回合超时扫描循环。

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

    async def _run_loop(self) -> None:
        """
        后台循环：扫描 playing 房间并判定回合超时。

        :return: 无。
        """
        while self._running:
            try:
                await self._tick_once()
            except Exception:
                logger.exception("turn timeout tick failed")
            await asyncio.sleep(SCAN_INTERVAL_MS / 1000.0)

    async def _tick_once(self) -> None:
        """
        执行一次回合超时扫描。

        :return: 无。
        """
        room_ids = await self._list_playing_room_ids()
        for room_id in room_ids:
            await self._tick_room(room_id)

    async def _list_playing_room_ids(self) -> List[str]:
        """
        读取有效 playing 房间 ID 列表。

        :return: 房间 ID 列表。
        """
        room_ids = await self._repository.list_playing_room_ids()
        valid_room_ids = []
        for room_id in room_ids:
            meta = await self._repository.get_meta(room_id)
            if meta is None or str(meta.get("status", "")).strip() != "playing":
                await self._repository.remove_playing_room(room_id)
                continue
            valid_room_ids.append(room_id)
        return valid_room_ids

    async def _tick_room(self, room_id: str) -> None:
        """
        对单个房间判定当前行动玩家是否已超过回合截止时间。

        :param room_id: 房间 ID。
        :return: 无。
        """
        meta = await self._repository.get_meta(room_id)
        if meta is None or str(meta.get("status", "")).strip() != "playing":
            return
        runtime_data = await self._repository.get_runtime(room_id)
        if runtime_data is None:
            return
        if bool(runtime_data.get("isGameOver", False)):
            return
        runtime_state = runtime_data.get("runtimeState")
        if not isinstance(runtime_state, dict):
            return
        current_player_id = str(runtime_state.get("currentPlayerId", "")).strip()
        if not current_player_id:
            return
        deadline_raw = runtime_state.get("currentTurnDeadlineAt")
        if deadline_raw is None:
            return
        try:
            deadline_at = int(deadline_raw)
        except (TypeError, ValueError):
            return
        if deadline_at <= 0:
            return
        current_time = now_ms()
        if current_time < deadline_at:
            return
        members = await self._repository.list_players(room_id)
        target_member = self._find_member(members, current_player_id)
        if target_member is None:
            return
        if bool(target_member.get("isAi")):
            return
        if bool(target_member.get("isManaged")):
            return
        marked = await self._notify_active_managed(room_id, current_player_id, "turnTimeout")
        if not marked:
            logger.warning(
                "turn timeout active managed mark failed, roomId=%s playerId=%s deadlineAt=%s",
                room_id,
                current_player_id,
                deadline_at,
            )

    async def _notify_active_managed(self, room_id: str, player_id: str, reason: str) -> bool:
        """
        调用房间模块 active 托管处理函数。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param reason: 托管原因。
        :return: 是否成功标记或房间已无需处理。
        """
        normalized_reason = str(reason or "").strip()
        if normalized_reason not in ACTIVE_MANAGED_REASONS:
            return True
        handler = self._mark_member_active_managed_handler
        if handler is None:
            logger.warning(
                "turn timeout active managed handler not bound, roomId=%s playerId=%s",
                room_id,
                player_id,
            )
            return False
        return bool(await handler(room_id, player_id, normalized_reason))

    def _find_member(
        self,
        members: List[Dict[str, object]],
        player_id: str,
    ) -> Optional[Dict[str, object]]:
        """
        在成员列表中查找指定玩家。

        :param members: 成员列表。
        :param player_id: 玩家 ID。
        :return: 成员对象；未找到时返回 ``None``。
        """
        for member in members:
            if str(member.get("playerId", "")).strip() == player_id:
                return member
        return None


turn_timeout_service = TurnTimeoutService()
