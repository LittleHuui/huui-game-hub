"""房间后台任务共享 Redis 队列存储原语。"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from app.core.clock import Clock, system_clock
from app.core.redis.redis_client import RedisClient, redis_client

logger = logging.getLogger(__name__)

TASK_QUEUE_DATA_EXPIRE_SECONDS = 86400
TASK_QUEUE_DEDUPE_EXPIRE_SECONDS = 86400
TASK_QUEUE_DUE_EXPIRE_SECONDS = 604800
TASK_QUEUE_PROCESSING_EXPIRE_SECONDS = 604800
TASK_QUEUE_VISIBILITY_TIMEOUT_MS = 30000
TASK_QUEUE_ORPHAN_CLAIM_RETRIES = 20
TASK_QUEUE_RECOVER_BATCH_SIZE = 50

_ENQUEUE_TASK_CREATED = 1
_ENQUEUE_TASK_DUPLICATED = 2

_ENQUEUE_TASK_SCRIPT = """
local dedupeCreated = redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', tonumber(ARGV[2]))
if not dedupeCreated then
    return 2
end
redis.call('HSET', KEYS[2], ARGV[1], ARGV[3])
redis.call('EXPIRE', KEYS[2], tonumber(ARGV[4]))
redis.call('ZADD', KEYS[3], ARGV[5], ARGV[1])
redis.call('EXPIRE', KEYS[3], tonumber(ARGV[6]))
return 1
"""

_RELEASE_TO_DUE_SCRIPT = """
redis.call('HSET', KEYS[1], ARGV[1], ARGV[2])
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[4]))
redis.call('ZADD', KEYS[3], ARGV[3], ARGV[1])
redis.call('EXPIRE', KEYS[3], tonumber(ARGV[5]))
redis.call('ZREM', KEYS[2], ARGV[1])
return 1
"""

_FINALIZE_TASK_SCRIPT = """
redis.call('HSET', KEYS[1], ARGV[1], ARGV[2])
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
redis.call('ZREM', KEYS[2], ARGV[1])
redis.call('ZREM', KEYS[3], ARGV[1])
return 1
"""

_CLAIM_DUE_TASK_SCRIPT = """
local tasks = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, 1)
if #tasks == 0 then
    return ''
end
local taskId = tasks[1]
local taskJson = redis.call('HGET', KEYS[3], taskId)
if not taskJson then
    redis.call('ZREM', KEYS[1], taskId)
    return 'ORPHAN:' .. taskId
end
local decoded, task = pcall(cjson.decode, taskJson)
if not decoded or type(task) ~= 'table' then
    redis.call('ZREM', KEYS[1], taskId)
    return 'CORRUPT:' .. taskId
end
local status = task['status'] or ''
if status == 'DONE' or status == 'SKIPPED' or status == 'FAILED' then
    redis.call('ZREM', KEYS[1], taskId)
    return 'ORPHAN:' .. taskId
end
if status ~= 'PENDING' and status ~= 'RUNNING' then
    redis.call('ZREM', KEYS[1], taskId)
    return 'ORPHAN:' .. taskId
end
local attemptCount = tonumber(task['attemptCount'] or 0)
if not attemptCount then
    redis.call('ZREM', KEYS[1], taskId)
    return 'ORPHAN:' .. taskId
end
task['status'] = 'RUNNING'
task['leaseUntil'] = tonumber(ARGV[2])
task['attemptCount'] = attemptCount + 1
task['updatedAt'] = tonumber(ARGV[4])
local newJson = cjson.encode(task)
redis.call('ZREM', KEYS[1], taskId)
redis.call('ZADD', KEYS[2], ARGV[2], taskId)
redis.call('EXPIRE', KEYS[2], tonumber(ARGV[3]))
redis.call('HSET', KEYS[3], taskId, newJson)
redis.call('EXPIRE', KEYS[3], tonumber(ARGV[5]))
return newJson
"""

_RELEASE_DEDUPE_IF_OWNER_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""

_RECOVER_STALE_PROCESSING_SCRIPT = """
local stale = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, 1)
if #stale == 0 then
    return ''
end
local taskId = stale[1]
local taskJson = redis.call('HGET', KEYS[3], taskId)
if not taskJson then
    redis.call('ZREM', KEYS[1], taskId)
    redis.call('ZREM', KEYS[2], taskId)
    return 'ORPHAN:' .. taskId
end
local decoded, task = pcall(cjson.decode, taskJson)
if not decoded or type(task) ~= 'table' then
    redis.call('ZREM', KEYS[1], taskId)
    redis.call('ZREM', KEYS[2], taskId)
    return 'CORRUPT:' .. taskId
end
local status = task['status'] or ''
if status == 'DONE' or status == 'SKIPPED' or status == 'FAILED' then
    redis.call('ZREM', KEYS[1], taskId)
    return 'FINAL:' .. taskId
end
if status ~= 'RUNNING' then
    redis.call('ZREM', KEYS[1], taskId)
    if status == 'PENDING' then
        return 'PENDING:' .. taskId
    end
    redis.call('ZREM', KEYS[2], taskId)
    return 'ORPHAN:' .. taskId
end
local executeAfter = tonumber(task['executeAfterMs']) or tonumber(ARGV[1])
if executeAfter < tonumber(ARGV[1]) then
    executeAfter = tonumber(ARGV[1])
end
task['status'] = 'PENDING'
task['leaseUntil'] = cjson.null
task['updatedAt'] = tonumber(ARGV[3])
local newJson = cjson.encode(task)
redis.call('HSET', KEYS[3], taskId, newJson)
redis.call('EXPIRE', KEYS[3], tonumber(ARGV[2]))
redis.call('ZADD', KEYS[2], executeAfter, taskId)
redis.call('EXPIRE', KEYS[2], tonumber(ARGV[4]))
redis.call('ZREM', KEYS[1], taskId)
return taskId
"""


class TaskEnqueueResult(object):
    """后台任务入队结果。"""

    def __init__(self, created=False, duplicated=False, failed=False):
        """
        初始化入队结果。

        :param created: 是否新建任务。
        :param duplicated: 是否命中去重。
        :param failed: 是否入队失败。
        """
        self.created = bool(created)
        self.duplicated = bool(duplicated)
        self.failed = bool(failed)


@dataclass(frozen=True)
class TaskQueueKeys:
    """将具体任务队列映射到各自 Redis 存储键。"""

    records: Callable[[str], str]
    due: Callable[[str], str]
    processing: Callable[[str], str]
    records_shard: Callable[[int], str]
    due_shard: Callable[[int], str]
    processing_shard: Callable[[int], str]


class TaskQueueRepository(object):
    """后台任务 Redis 读写。"""

    def __init__(
        self,
        keys: TaskQueueKeys,
        redis: RedisClient = redis_client,
        clock: Clock = system_clock,
    ) -> None:
        """
        初始化后台任务仓库。

        :param redis: Redis 工具。
        :param clock: 可注入时钟。
        """
        self._keys = keys
        self._redis = redis
        self._clock = clock

    async def _enqueue_task(
        self,
        room_id: str,
        dedupe_key: str,
        task_data: Dict[str, Any],
    ) -> TaskEnqueueResult:
        """
        原子写入 dedupe、任务数据与 due zset。

        :param room_id: 房间 ID。
        :param dedupe_key: 已按任务业务身份构造的去重键。
        :param task_data: 任务对象。
        :return: 入队结果（created / duplicated / failed）。
        """
        task_id = str(task_data.get("taskId", "")).strip()
        if not task_id:
            return TaskEnqueueResult(failed=True)
        execute_after_ms = task_data.get("executeAfterMs")
        if execute_after_ms is None:
            return TaskEnqueueResult(failed=True)
        stored_task_data = dict(task_data)
        stored_task_data["dedupeKey"] = dedupe_key
        try:
            task_json = json.dumps(stored_task_data, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            logger.exception("room task enqueue encode failed, taskId=%s", task_id)
            return TaskEnqueueResult(failed=True)
        records_key = self._keys.records(room_id)
        due_key = self._keys.due(room_id)
        result = await self._redis.eval(
            _ENQUEUE_TASK_SCRIPT,
            3,
            [dedupe_key, records_key, due_key],
            [
                task_id,
                str(TASK_QUEUE_DEDUPE_EXPIRE_SECONDS),
                task_json,
                str(TASK_QUEUE_DATA_EXPIRE_SECONDS),
                str(float(execute_after_ms)),
                str(TASK_QUEUE_DUE_EXPIRE_SECONDS),
            ],
        )
        normalized_result = int(result or 0)
        if normalized_result == _ENQUEUE_TASK_CREATED:
            return TaskEnqueueResult(created=True)
        if normalized_result == _ENQUEUE_TASK_DUPLICATED:
            return TaskEnqueueResult(duplicated=True)
        return TaskEnqueueResult(failed=True)

    async def get_task(self, room_id: str, task_id: str) -> Optional[Dict[str, Any]]:
        """
        读取后台任务数据。

        :param task_id: 任务 ID。
        :return: 任务对象；不存在时返回 ``None``。
        """
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            return None
        data = await self._redis.hget_json(
            self._keys.records(room_id), normalized_task_id
        )
        if not isinstance(data, dict):
            return None
        return data

    async def update_task(self, room_id: str, task_id: str, task_data: Dict[str, Any]) -> bool:
        """
        更新后台任务数据。

        :param task_id: 任务 ID。
        :param task_data: 任务对象。
        :return: 是否更新成功。
        """
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            return False
        task_data["updatedAt"] = self._clock.now_ms()
        return await self._save_task(room_id, task_data)

    async def release_dedupe_if_owner(self, dedupe_key: str, task_id: str) -> bool:
        """
        仅当 dedupe key 仍指向指定任务时释放去重锁。

        :param dedupe_key: 去重 Redis key。
        :param task_id: 任务 ID。
        :return: 是否释放成功。
        """
        normalized_dedupe_key = str(dedupe_key or "").strip()
        normalized_task_id = str(task_id or "").strip()
        if not normalized_dedupe_key or not normalized_task_id:
            return False
        result = await self._redis.eval(
            _RELEASE_DEDUPE_IF_OWNER_SCRIPT,
            1,
            [normalized_dedupe_key],
            [normalized_task_id],
        )
        return int(result or 0) > 0

    async def claim_due_task(
        self,
        current_time_ms: int,
        shard_index: int,
        visibility_timeout_ms: int = TASK_QUEUE_VISIBILITY_TIMEOUT_MS,
    ) -> Optional[Dict[str, Any]]:
        """
        原子领取一个到期任务：移入 processing 并标记 running。

        :param current_time_ms: 当前时间（毫秒）。
        :param visibility_timeout_ms: 可见性超时（毫秒）。
        :return: 已领取任务对象；无到期任务时返回 ``None``。
        """
        visibility_deadline_ms = int(current_time_ms) + int(visibility_timeout_ms)
        updated_at = self._clock.now_ms()
        for _attempt in range(TASK_QUEUE_ORPHAN_CLAIM_RETRIES):
            result = await self._redis.eval_raw(
                _CLAIM_DUE_TASK_SCRIPT,
                3,
                [
                    self._keys.due_shard(shard_index),
                    self._keys.processing_shard(shard_index),
                    self._keys.records_shard(shard_index),
                ],
                [
                    str(int(current_time_ms)),
                    str(visibility_deadline_ms),
                    str(TASK_QUEUE_PROCESSING_EXPIRE_SECONDS),
                    str(updated_at),
                    str(TASK_QUEUE_DATA_EXPIRE_SECONDS),
                ],
            )
            if result is None:
                return None
            result_text = str(result).strip()
            if not result_text:
                return None
            if result_text.startswith("CORRUPT:"):
                logger.error("room task corrupt record isolated, shard=%s taskId=%s", shard_index, result_text[8:])
                continue
            if result_text.startswith("ORPHAN:"):
                continue
            try:
                task_data = json.loads(result_text)
            except (TypeError, ValueError):
                logger.warning("room task claim decode failed, raw=%s", result_text)
                continue
            if not isinstance(task_data, dict):
                continue
            return task_data
        return None

    async def remove_from_processing(self, room_id: str, task_id: str) -> bool:
        """
        从 processing zset 移除任务。

        :param task_id: 任务 ID。
        :return: 是否执行完成。
        """
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            return False
        await self._redis.zrem(self._keys.processing(room_id), normalized_task_id)
        return True

    async def release_to_due(
        self,
        room_id: str,
        task_id: str,
        execute_after_ms: int,
        task_data: Dict[str, Any],
    ) -> bool:
        """
        原子将任务从 processing 放回 due 并更新任务数据。

        :param task_id: 任务 ID。
        :param execute_after_ms: 下次执行时间（毫秒）。
        :param task_data: 任务对象。
        :return: 是否操作成功。
        """
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            return False
        status = str(task_data.get("status", "")).strip()
        if status in ("DONE", "SKIPPED", "FAILED"):
            return False
        stored_task_data = dict(task_data)
        stored_task_data["status"] = "PENDING"
        stored_task_data["updatedAt"] = self._clock.now_ms()
        try:
            task_json = json.dumps(stored_task_data, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            logger.exception("room task release encode failed, taskId=%s", normalized_task_id)
            return False
        result = await self._redis.eval(
            _RELEASE_TO_DUE_SCRIPT,
            3,
            [
                self._keys.records(room_id),
                self._keys.processing(room_id),
                self._keys.due(room_id),
            ],
            [
                normalized_task_id,
                task_json,
                str(float(execute_after_ms)),
                str(TASK_QUEUE_DATA_EXPIRE_SECONDS),
                str(TASK_QUEUE_DUE_EXPIRE_SECONDS),
            ],
        )
        return int(result or 0) > 0

    async def finalize_task(self, room_id: str, task_id: str, task_data: Dict[str, Any]) -> bool:
        """
        原子终结任务：写入终态 taskData、移出 processing 与 due。

        :param task_id: 任务 ID。
        :param task_data: 任务对象（含 status、skipReason）。
        :return: 是否操作成功。
        """
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            return False
        stored_task_data = dict(task_data)
        stored_task_data["updatedAt"] = self._clock.now_ms()
        try:
            task_json = json.dumps(stored_task_data, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            logger.exception("room task finalize encode failed, taskId=%s", normalized_task_id)
            return False
        result = await self._redis.eval(
            _FINALIZE_TASK_SCRIPT,
            3,
            [
                self._keys.records(room_id),
                self._keys.processing(room_id),
                self._keys.due(room_id),
            ],
            [
                normalized_task_id,
                task_json,
                str(TASK_QUEUE_DATA_EXPIRE_SECONDS),
            ],
        )
        return int(result or 0) > 0

    async def recover_stale_processing_tasks(
        self,
        current_time_ms: int,
        shard_index: int,
        max_count: int = TASK_QUEUE_RECOVER_BATCH_SIZE,
    ) -> List[str]:
        """
        恢复 processing zset 中可见性已过期的任务。

        :param current_time_ms: 当前时间（毫秒）。
        :return: 已恢复的任务 ID 列表。
        """
        recovered = []
        updated_at = self._clock.now_ms()
        for _attempt in range(max(0, int(max_count))):
            result = await self._redis.eval_raw(
                _RECOVER_STALE_PROCESSING_SCRIPT,
                3,
                [
                    self._keys.processing_shard(shard_index),
                    self._keys.due_shard(shard_index),
                    self._keys.records_shard(shard_index),
                ],
                [
                    str(int(current_time_ms)),
                    str(TASK_QUEUE_DATA_EXPIRE_SECONDS),
                    str(updated_at),
                    str(TASK_QUEUE_DUE_EXPIRE_SECONDS),
                ],
            )
            if result is None:
                break
            result_text = str(result).strip()
            if not result_text:
                break
            if result_text.startswith("CORRUPT:"):
                logger.error("room task corrupt lease record isolated, shard=%s taskId=%s", shard_index, result_text[8:])
                continue
            if (
                result_text.startswith("ORPHAN:")
                or result_text.startswith("FINAL:")
                or result_text.startswith("PENDING:")
            ):
                continue
            recovered.append(result_text)
        return recovered

    async def _save_task(self, room_id: str, task_data: Dict[str, Any]) -> bool:
        """
        写入后台任务数据。

        :param task_data: 任务对象。
        :return: 是否写入成功。
        """
        task_id = str(task_data.get("taskId", "")).strip()
        if not task_id:
            return False
        return await self._redis.hset_json(
            self._keys.records(room_id),
            task_id,
            task_data,
            TASK_QUEUE_DATA_EXPIRE_SECONDS,
        )
