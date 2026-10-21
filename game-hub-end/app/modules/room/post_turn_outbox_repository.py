"""回合后任务 Outbox 仓库。"""

import json
import logging
from typing import List, Optional, Set, Tuple

from pydantic import ValidationError

from app.core.redis.redis_client import RedisClient, redis_client
from app.core.redis.redis_keys import RedisKeys
from app.core.time_utils import now_ms
from app.modules.room.post_turn_outbox_lua import (
    ACK_ROOM_OUTBOX_LUA,
    CLAIM_ROOM_OUTBOX_LUA,
    CLAIM_READY_ROOMS_LUA,
    CLEANUP_ROOM_OUTBOX_LUA,
    CLEAR_ROOM_OUTBOX_LUA,
    DISCARD_ROOM_OUTBOX_LUA,
    ENQUEUE_ROOM_OUTBOX_IF_ABSENT_LUA,
    FAIL_ROOM_OUTBOX_LUA,
    MARK_ROOM_READY_LUA,
    READ_ROOM_OUTBOX_RECORDS_LUA,
    RECOVER_ROOM_OUTBOX_LUA,
    RECOVER_ROOM_OUTBOX_LEASES_LUA,
    REMOVE_ROOM_READY_LUA,
    RETRY_GAME_SETTLEMENT_OUTBOX_LUA,
    RETRY_ROOM_OUTBOX_LUA,
)
from app.modules.room.room_game_commit_schemas import PostTurnOutboxRecord

logger = logging.getLogger(__name__)

POST_TURN_OUTBOX_LEASE_MS = 30000
POST_TURN_OUTBOX_BACKOFF_MS = 5000
POST_TURN_OUTBOX_MAX_ATTEMPTS = 5
POST_TURN_OUTBOX_BATCH_SIZE = 20
POST_TURN_OUTBOX_CLAIM_SCAN_LIMIT = 200
POST_TURN_OUTBOX_EXPIRE_SECONDS = 86400
POST_TURN_OUTBOX_DONE_RETENTION_MS = 3600000
POST_TURN_OUTBOX_FAILED_RETENTION_MS = 86400000
OUTBOX_READY_ROOMS_EXPIRE_SECONDS = 86400
OUTBOX_READY_REPAIR_SCAN_COUNT = 50


class PostTurnOutboxRepository(object):
    """基于房间级 Redis 结构的 Outbox 持久化与状态转换。"""

    def __init__(self, redis: RedisClient = redis_client) -> None:
        """
        初始化 Outbox 仓库。

        :param redis: Redis 客户端。
        """
        self._redis = redis
        self._ready_shard_cursor = 0

    async def mark_room_ready(
        self,
        room_id: str,
        next_attempt_at_ms: Optional[int] = None,
    ) -> bool:
        """
        将房间加入 ready-room 派生索引。

        :param room_id: 房间 ID。
        :param next_attempt_at_ms: 房间最早可执行时间；为空时自动探测。
        :return: 是否写入成功。
        """
        normalized_room_id = str(room_id or "").strip()
        if not normalized_room_id:
            return False
        score = (
            int(next_attempt_at_ms)
            if next_attempt_at_ms is not None
            else await self._get_room_next_attempt_at_ms(normalized_room_id)
        )
        if score is None:
            return False
        result = await self._redis.eval_raw(
            MARK_ROOM_READY_LUA,
            1,
            [RedisKeys.outbox_ready_rooms(normalized_room_id)],
            [
                normalized_room_id,
                str(int(score)),
                str(OUTBOX_READY_ROOMS_EXPIRE_SECONDS),
            ],
        )
        return bool(int(result or 0))

    async def unmark_room_ready(self, room_id: str) -> bool:
        """
        将房间从 ready-room 派生索引移除。

        :param room_id: 房间 ID。
        :return: 是否移除成功。
        """
        normalized_room_id = str(room_id or "").strip()
        if not normalized_room_id:
            return False
        result = await self._redis.eval_raw(
            REMOVE_ROOM_READY_LUA,
            1,
            [RedisKeys.outbox_ready_rooms(normalized_room_id)],
            [normalized_room_id],
        )
        return bool(int(result or 0))

    async def list_ready_rooms(self) -> Set[str]:
        """
        读取 ready-room 派生索引中的房间 ID。

        :return: 房间 ID 集合。
        """
        room_ids = set()
        for ready_key in RedisKeys.outbox_ready_room_shards():
            room_ids.update(await self._redis.zrange(ready_key, 0, -1))
        return room_ids

    async def room_has_pending_outbox(self, room_id: str) -> bool:
        """
        判断房间是否存在未终态 Outbox 记录。

        :param room_id: 房间 ID。
        :return: 是否存在待处理记录。
        """
        normalized_room_id = str(room_id or "").strip()
        if not normalized_room_id:
            return False
        due_key = RedisKeys.room_outbox_due(normalized_room_id)
        members = await self._redis.zrange(due_key, 0, 0)
        if members:
            return True
        for record in await self._read_records(normalized_room_id):
            status = record.status
            if status in ("PENDING", "PROCESSING"):
                return True
        return False

    async def repair_ready_room_index(self, room_ids: List[str]) -> int:
        """
        根据房间本地 Outbox 事实修复 ready-room 派生索引。

        :param room_ids: 待检查房间 ID 列表。
        :return: 新加入索引的房间数量。
        """
        repaired = 0
        for room_id in room_ids:
            normalized_room_id = str(room_id or "").strip()
            if not normalized_room_id:
                continue
            if await self.room_has_pending_outbox(normalized_room_id):
                saved = await self.mark_room_ready(normalized_room_id)
                if saved:
                    repaired += 1
        return repaired

    async def scan_repair_ready_room_index(
        self,
        cursor: int = 0,
        scan_count: int = OUTBOX_READY_REPAIR_SCAN_COUNT,
    ) -> Tuple[int, int]:
        """
        分页 SCAN Outbox records key，将存在待处理 Outbox 的房间重新加入 ready-room 索引。

        :param cursor: SCAN 游标；0 表示新一轮扫描起点。
        :param scan_count: 单次 SCAN 命令建议返回 key 数量。
        :return: ``(下一游标, 修复房间数)``。
        """
        next_cursor, keys = await self._redis.scan_keys_page(
            RedisKeys.room_outbox_records_pattern(),
            cursor=int(cursor),
            count=int(scan_count),
        )
        repaired = 0
        for key in keys:
            room_id = self._room_id_from_outbox_records_key(str(key or "").strip())
            if not room_id:
                logger.warning("skip invalid outbox records key while scan repairing, key=%s", key)
                continue
            next_attempt_at = await self._get_room_next_attempt_at_ms(room_id)
            if next_attempt_at is None:
                continue
            saved = await self.mark_room_ready(room_id, next_attempt_at)
            if saved:
                repaired += 1
        return int(next_cursor), int(repaired)

    async def scan_cleanup_terminal_records(
        self,
        cursor: int = 0,
        now_timestamp_ms: Optional[int] = None,
        scan_count: int = OUTBOX_READY_REPAIR_SCAN_COUNT,
    ) -> Tuple[int, int]:
        """Incrementally cleanup terminal outbox records for every room with records."""
        timestamp = int(now_timestamp_ms) if now_timestamp_ms is not None else now_ms()
        next_cursor, keys = await self._redis.scan_keys_page(
            RedisKeys.room_outbox_records_pattern(),
            cursor=int(cursor),
            count=int(scan_count),
        )
        removed = 0
        for key in keys:
            room_id = self._room_id_from_outbox_records_key(str(key or "").strip())
            if not room_id:
                continue
            removed += await self.cleanup(room_id, timestamp)
        return int(next_cursor), int(removed)

    async def claim(
        self,
        room_id: str,
        limit: int,
        now_timestamp_ms: Optional[int] = None,
        lease_ms: int = POST_TURN_OUTBOX_LEASE_MS,
    ) -> List[PostTurnOutboxRecord]:
        """
        从指定房间领取可处理 Outbox 记录并设置租约。

        :param room_id: 房间 ID。
        :param limit: 最大领取条数。
        :param now_timestamp_ms: 当前时间戳；为空时使用当前时间。
        :param lease_ms: 租约时长（毫秒）。
        :return: 已领取记录列表。
        """
        normalized_room_id = str(room_id or "").strip()
        if not normalized_room_id or int(limit) <= 0:
            return []
        timestamp = int(now_timestamp_ms) if now_timestamp_ms is not None else now_ms()
        keys = [
            RedisKeys.room_outbox_records(normalized_room_id),
            RedisKeys.room_outbox_due(normalized_room_id),
            RedisKeys.room_outbox_dedupe(normalized_room_id),
            RedisKeys.outbox_ready_rooms(normalized_room_id),
            RedisKeys.room_outbox_dispatch_lease(normalized_room_id),
        ]
        args = [
            str(timestamp),
            str(int(lease_ms)),
            str(max(1, int(limit))),
            str(POST_TURN_OUTBOX_CLAIM_SCAN_LIMIT),
            str(POST_TURN_OUTBOX_EXPIRE_SECONDS),
            normalized_room_id,
            str(OUTBOX_READY_ROOMS_EXPIRE_SECONDS),
        ]
        raw_result = await self._redis.eval_raw(
            CLAIM_ROOM_OUTBOX_LUA,
            len(keys),
            keys,
            args,
        )
        return self._parse_record_list(raw_result)

    async def claim_from_ready_rooms(
        self,
        room_batch_size: int,
        per_room_limit: int,
        now_timestamp_ms: Optional[int] = None,
        lease_ms: int = POST_TURN_OUTBOX_LEASE_MS,
    ) -> List[PostTurnOutboxRecord]:
        """
        从 ready-room 索引批量领取 Outbox 记录。

        :param room_batch_size: 每轮扫描房间数。
        :param per_room_limit: 每个房间最大领取条数。
        :param now_timestamp_ms: 当前时间戳；为空时使用当前时间。
        :param lease_ms: 租约时长（毫秒）。
        :return: 已领取记录列表。
        """
        timestamp = int(now_timestamp_ms) if now_timestamp_ms is not None else now_ms()
        ready_keys = RedisKeys.outbox_ready_room_shards()
        shard_count = len(ready_keys)
        if shard_count <= 0:
            return []
        start_index = self._ready_shard_cursor % shard_count
        self._ready_shard_cursor = (start_index + 1) % shard_count
        ready_rooms = []
        per_shard_limit = max(2, int(room_batch_size) * 2)
        for offset in range(shard_count):
            ready_key = ready_keys[(start_index + offset) % shard_count]
            raw_room_ids = await self._redis.eval_raw(
                CLAIM_READY_ROOMS_LUA,
                1,
                [ready_key],
                [str(timestamp), str(per_shard_limit)],
            )
            ready_rooms.extend(self._parse_string_list(raw_room_ids))
        if not ready_rooms:
            return []
        claimed_records = []
        claimed_room_count = 0
        for room_id in ready_rooms:
            try:
                room_records = await self.claim(
                    room_id,
                    per_room_limit,
                    now_timestamp_ms=now_timestamp_ms,
                    lease_ms=lease_ms,
                )
            except Exception:
                logger.exception("outbox room claim failed, roomId=%s", room_id)
                continue
            claimed_records.extend(room_records)
            if room_records:
                claimed_room_count += 1
                if claimed_room_count >= max(1, int(room_batch_size)):
                    break
        return claimed_records

    async def ack(self, room_id: str, record: PostTurnOutboxRecord) -> bool:
        """
        确认 Outbox 记录处理成功。

        :param room_id: 房间 ID。
        :param record: Outbox 记录。
        :return: 是否更新成功。
        """
        return await self._transition_record(
            room_id,
            record.outboxId,
            ACK_ROOM_OUTBOX_LUA,
            [
                record.outboxId,
                str(now_ms()),
                str(POST_TURN_OUTBOX_EXPIRE_SECONDS),
            ],
            include_dedupe=False,
        )

    async def retry(
        self,
        room_id: str,
        record: PostTurnOutboxRecord,
        failure_reason: str,
        backoff_ms: int = POST_TURN_OUTBOX_BACKOFF_MS,
    ) -> bool:
        """
        标记 Outbox 记录临时失败并退避重试。

        :param room_id: 房间 ID。
        :param record: Outbox 记录。
        :param failure_reason: 失败原因。
        :param backoff_ms: 退避毫秒数。
        :return: 是否更新成功。
        """
        return await self._transition_record(
            room_id,
            record.outboxId,
            RETRY_ROOM_OUTBOX_LUA,
            [
                record.outboxId,
                str(now_ms()),
                str(int(backoff_ms)),
                str(failure_reason or ""),
                str(failure_reason or ""),
                str(POST_TURN_OUTBOX_EXPIRE_SECONDS),
            ],
            include_dedupe=False,
        )

    async def recover(
        self,
        room_id: str,
        record: PostTurnOutboxRecord,
        failure_code: str,
        failure_reason: str,
        backoff_ms: int = POST_TURN_OUTBOX_BACKOFF_MS,
    ) -> bool:
        """Enter a recovery cycle without creating a new Outbox record."""
        return await self._transition_record(
            room_id,
            record.outboxId,
            RECOVER_ROOM_OUTBOX_LUA,
            [
                record.outboxId,
                str(now_ms()),
                str(int(backoff_ms)),
                str(failure_code or ""),
                str(failure_reason or ""),
                str(POST_TURN_OUTBOX_EXPIRE_SECONDS),
            ],
            include_dedupe=False,
        )

    async def retry_game_settlement(
        self,
        room_id: str,
        record: PostTurnOutboxRecord,
        failure_reason: str,
        backoff_ms: int = POST_TURN_OUTBOX_BACKOFF_MS,
    ) -> bool:
        """
        在失败终局尚未提交时保持 GAME_SETTLEMENT Outbox 可调度。

        :param room_id: 房间 ID。
        :param record: GAME_SETTLEMENT Outbox 记录。
        :param failure_reason: 本次失败原因。
        :param backoff_ms: 下次恢复前退避毫秒数。
        :return: 是否更新成功。
        """
        return await self._transition_record(
            room_id,
            record.outboxId,
            RETRY_GAME_SETTLEMENT_OUTBOX_LUA,
            [
                record.outboxId,
                str(now_ms()),
                str(int(backoff_ms)),
                str(failure_reason or ""),
                str(POST_TURN_OUTBOX_EXPIRE_SECONDS),
            ],
            include_dedupe=False,
        )

    async def discard(
        self,
        room_id: str,
        record: PostTurnOutboxRecord,
        failure_reason: str,
    ) -> bool:
        """
        丢弃已过期的 Outbox 记录。

        :param room_id: 房间 ID。
        :param record: Outbox 记录。
        :param failure_reason: 丢弃原因。
        :return: 是否更新成功。
        """
        return await self._transition_record(
            room_id,
            record.outboxId,
            DISCARD_ROOM_OUTBOX_LUA,
            [
                record.outboxId,
                str(now_ms()),
                str(failure_reason or ""),
                str(POST_TURN_OUTBOX_EXPIRE_SECONDS),
            ],
            include_dedupe=True,
        )

    async def fail(
        self,
        room_id: str,
        record: PostTurnOutboxRecord,
        failure_reason: str,
    ) -> bool:
        """
        标记 Outbox 记录为永久失败。

        :param room_id: 房间 ID。
        :param record: Outbox 记录。
        :param failure_reason: 失败原因。
        :return: 是否更新成功。
        """
        return await self._transition_record(
            room_id,
            record.outboxId,
            FAIL_ROOM_OUTBOX_LUA,
            [
                record.outboxId,
                str(now_ms()),
                str(failure_reason or ""),
                str(POST_TURN_OUTBOX_EXPIRE_SECONDS),
            ],
            include_dedupe=False,
        )

    async def recover_expired_leases(
        self,
        room_id: str,
        now_timestamp_ms: Optional[int] = None,
    ) -> int:
        """
        恢复指定房间租约已过期的 PROCESSING 记录。

        :param room_id: 房间 ID。
        :param now_timestamp_ms: 当前时间戳；为空时使用当前时间。
        :return: 恢复的记录数量。
        """
        normalized_room_id = str(room_id or "").strip()
        if not normalized_room_id:
            return 0
        timestamp = int(now_timestamp_ms) if now_timestamp_ms is not None else now_ms()
        keys = [
            RedisKeys.room_outbox_records(normalized_room_id),
            RedisKeys.room_outbox_due(normalized_room_id),
            RedisKeys.outbox_ready_rooms(normalized_room_id),
            RedisKeys.room_outbox_dispatch_lease(normalized_room_id),
        ]
        args = [
            str(timestamp),
            str(POST_TURN_OUTBOX_EXPIRE_SECONDS),
            normalized_room_id,
            str(OUTBOX_READY_ROOMS_EXPIRE_SECONDS),
        ]
        raw_result = await self._redis.eval_raw(
            RECOVER_ROOM_OUTBOX_LEASES_LUA,
            len(keys),
            keys,
            args,
        )
        recovered = int(raw_result or 0)
        return recovered

    async def cleanup(self, room_id: str, now_timestamp_ms: Optional[int] = None) -> int:
        """
        清理指定房间已到保留期的终态 Outbox 记录。

        :param room_id: 房间 ID。
        :param now_timestamp_ms: 当前时间戳；为空时使用当前时间。
        :return: 删除记录数量。
        """
        normalized_room_id = str(room_id or "").strip()
        if not normalized_room_id:
            return 0
        timestamp = int(now_timestamp_ms) if now_timestamp_ms is not None else now_ms()
        keys = [
            RedisKeys.room_outbox_records(normalized_room_id),
            RedisKeys.room_outbox_due(normalized_room_id),
            RedisKeys.room_outbox_dedupe(normalized_room_id),
            RedisKeys.outbox_ready_rooms(normalized_room_id),
            RedisKeys.room_outbox_dispatch_lease(normalized_room_id),
        ]
        args = [
            str(timestamp),
            str(POST_TURN_OUTBOX_DONE_RETENTION_MS),
            str(POST_TURN_OUTBOX_FAILED_RETENTION_MS),
            str(POST_TURN_OUTBOX_EXPIRE_SECONDS),
            normalized_room_id,
            str(OUTBOX_READY_ROOMS_EXPIRE_SECONDS),
        ]
        raw_result = await self._redis.eval_raw(
            CLEANUP_ROOM_OUTBOX_LUA,
            len(keys),
            keys,
            args,
        )
        removed = int(raw_result or 0)
        return removed

    async def enqueue_record_if_absent(self, record: PostTurnOutboxRecord) -> bool:
        """幂等入队并刷新索引；已有记录损坏时原子隔离并释放其分发租约。"""
        normalized_room_id = str(record.roomId or "").strip()
        dedupe_key = str(record.dedupeKey or "").strip()
        if not normalized_room_id or not dedupe_key:
            return False
        payload = json.dumps(record.model_dump(), ensure_ascii=False, separators=(",", ":"))
        result = await self._redis.eval_raw(
            ENQUEUE_ROOM_OUTBOX_IF_ABSENT_LUA,
            5,
            [
                RedisKeys.room_outbox_records(normalized_room_id),
                RedisKeys.room_outbox_due(normalized_room_id),
                RedisKeys.room_outbox_dedupe(normalized_room_id),
                RedisKeys.outbox_ready_rooms(normalized_room_id),
                RedisKeys.room_outbox_dispatch_lease(normalized_room_id),
            ],
            [
                record.outboxId,
                dedupe_key,
                payload,
                str(int(record.availableAt)),
                normalized_room_id,
                str(POST_TURN_OUTBOX_EXPIRE_SECONDS),
                str(OUTBOX_READY_ROOMS_EXPIRE_SECONDS),
            ],
        )
        return int(result or 0) > 0

    async def clear_room_outbox(self, room_id: str) -> bool:
        """
        清空房间全部 Outbox 结构。

        :param room_id: 房间 ID。
        :return: 是否清理成功。
        """
        normalized_room_id = str(room_id or "").strip()
        if not normalized_room_id:
            return False
        keys = [
            RedisKeys.room_outbox_records(normalized_room_id),
            RedisKeys.room_outbox_due(normalized_room_id),
            RedisKeys.room_outbox_dedupe(normalized_room_id),
            RedisKeys.outbox_ready_rooms(normalized_room_id),
            RedisKeys.room_outbox_dispatch_lease(normalized_room_id),
        ]
        result = await self._redis.eval_raw(
            CLEAR_ROOM_OUTBOX_LUA,
            len(keys),
            keys,
            [normalized_room_id],
        )
        return bool(int(result or 0))

    async def get_record(
        self,
        room_id: str,
        outbox_id: str,
    ) -> Optional[PostTurnOutboxRecord]:
        """
        读取单条 Outbox 记录。

        :param room_id: 房间 ID。
        :param outbox_id: Outbox 记录 ID。
        :return: Outbox 记录；不存在时返回 ``None``。
        """
        normalized_room_id = str(room_id or "").strip()
        normalized_outbox_id = str(outbox_id or "").strip()
        if not normalized_room_id or not normalized_outbox_id:
            return None
        records = await self._read_records(normalized_room_id, normalized_outbox_id)
        return records[0] if records else None

    async def _read_records(self, room_id: str, outbox_id: str = "") -> List[PostTurnOutboxRecord]:
        """受保护读取指定记录或全部记录；损坏外层同时隔离并收敛调度索引。"""
        keys = [RedisKeys.room_outbox_records(room_id), RedisKeys.room_outbox_due(room_id),
                RedisKeys.outbox_ready_rooms(room_id), RedisKeys.room_outbox_dispatch_lease(room_id)]
        raw = await self._redis.eval_raw(
            READ_ROOM_OUTBOX_RECORDS_LUA, len(keys), keys,
            [room_id, outbox_id, str(now_ms()), str(OUTBOX_READY_ROOMS_EXPIRE_SECONDS)],
        )
        return self._parse_record_list(raw)

    async def _transition_record(
        self,
        room_id: str,
        outbox_id: str,
        script: str,
        args: List[str],
        include_dedupe: bool,
    ) -> bool:
        """
        执行 Outbox 状态转换 Lua。

        :param room_id: 房间 ID。
        :param outbox_id: Outbox 记录 ID。
        :param script: Lua 脚本。
        :param args: Lua 参数。
        :param include_dedupe: 是否包含 dedupe key。
        :return: 是否更新成功。
        """
        normalized_room_id = str(room_id or "").strip()
        normalized_outbox_id = str(outbox_id or "").strip()
        if not normalized_room_id or not normalized_outbox_id:
            return False
        keys = [
            RedisKeys.room_outbox_records(normalized_room_id),
            RedisKeys.room_outbox_due(normalized_room_id),
        ]
        if include_dedupe:
            keys.append(RedisKeys.room_outbox_dedupe(normalized_room_id))
        keys.append(RedisKeys.outbox_ready_rooms(normalized_room_id))
        keys.append(RedisKeys.room_outbox_dispatch_lease(normalized_room_id))
        args = list(args) + [
            normalized_room_id,
            str(OUTBOX_READY_ROOMS_EXPIRE_SECONDS),
        ]
        result = await self._redis.eval_raw(script, len(keys), keys, args)
        updated = bool(int(result or 0))
        return updated

    async def refresh_room_ready(self, room_id: str) -> bool:
        """Refresh ready-room score from this room's earliest unfinished Outbox."""
        normalized_room_id = str(room_id or "").strip()
        if not normalized_room_id:
            return False
        next_attempt_at = await self._get_room_next_attempt_at_ms(normalized_room_id)
        if next_attempt_at is None:
            return await self.unmark_room_ready(normalized_room_id)
        return await self.mark_room_ready(normalized_room_id, next_attempt_at)

    def _parse_record_list(self, raw_result: object) -> List[PostTurnOutboxRecord]:
        """
        解析 Lua 返回的 Outbox 记录列表。

        :param raw_result: Lua 原始返回值。
        :return: 记录列表。
        """
        if raw_result is None:
            return []
        try:
            if isinstance(raw_result, (bytes, bytearray)):
                raw_result = raw_result.decode("utf-8")
            if not isinstance(raw_result, str):
                return []
            payload = json.loads(raw_result)
            if not isinstance(payload, list):
                return []
            records = []
            for item in payload:
                record = self._coerce_record(item)
                if record is not None:
                    records.append(record)
            return records
        except (TypeError, ValueError):
            return []

    def _parse_string_list(self, raw_result: object) -> List[str]:
        """
        解析 Lua 返回的字符串列表。

        :param raw_result: Lua 原始返回值。
        :return: 字符串列表。
        """
        if raw_result is None:
            return []
        try:
            if isinstance(raw_result, (bytes, bytearray)):
                raw_result = raw_result.decode("utf-8")
            if not isinstance(raw_result, str):
                return []
            payload = json.loads(raw_result)
            if not isinstance(payload, list):
                return []
            room_ids = []
            for item in payload:
                room_id = str(item or "").strip()
                if room_id:
                    room_ids.append(room_id)
            return room_ids
        except (TypeError, ValueError):
            return []

    def _coerce_record(self, raw: object) -> Optional[PostTurnOutboxRecord]:
        """
        将原始字典转换为 Outbox 记录。

        :param raw: 原始字典。
        :return: Outbox 记录；无效时返回 ``None``。
        """
        if not isinstance(raw, dict):
            return None
        try:
            return PostTurnOutboxRecord.model_validate(raw)
        except (TypeError, ValueError, ValidationError):
            return None


    @staticmethod
    def _room_id_from_outbox_records_key(key: str) -> Optional[str]:
        """
        从 Outbox records Redis key 解析房间 ID。

        :param key: Redis key。
        :return: 房间 ID；无法解析时返回 ``None``。
        """
        prefix = "game-hub:{room-shard:"
        room_prefix = "}:room:"
        suffix = ":outbox:records"
        normalized_key = str(key or "").strip()
        if not normalized_key.startswith(prefix) or not normalized_key.endswith(suffix):
            return None
        room_prefix_index = normalized_key.find(room_prefix, len(prefix))
        if room_prefix_index < 0:
            return None
        room_id = normalized_key[
            room_prefix_index + len(room_prefix): -len(suffix)
        ].strip()
        return room_id or None

    async def _get_room_next_attempt_at_ms(self, room_id: str) -> Optional[int]:
        """
        读取房间最早可执行的 Outbox 时间戳。

        :param room_id: 房间 ID。
        :return: 最早时间戳；无待处理任务时返回 ``None``。
        """
        normalized_room_id = str(room_id or "").strip()
        if not normalized_room_id:
            return None
        due_key = RedisKeys.room_outbox_due(normalized_room_id)
        outbox_ids = await self._redis.zrange(due_key, 0, -1)
        if not outbox_ids:
            return None
        for outbox_id in outbox_ids:
            record = await self.get_record(normalized_room_id, str(outbox_id or "").strip())
            if record is None or record.status not in ("PENDING", "PROCESSING", "RECOVERING"):
                continue
            if record.status == "PROCESSING":
                if record.leaseUntil is not None:
                    return int(record.leaseUntil)
                continue
            return int(record.nextAttemptAt if record.nextAttemptAt is not None else record.availableAt)
        return None


post_turn_outbox_repository = PostTurnOutboxRepository()
