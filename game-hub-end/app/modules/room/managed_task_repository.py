"""托管回合任务 Redis 仓库。"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.core.redis.redis_client import RedisClient, redis_client
from app.core.redis.redis_keys import RedisKeys
from app.core.time_utils import now_ms

logger = logging.getLogger(__name__)

MANAGED_TASK_DATA_EXPIRE_SECONDS = 86400
MANAGED_TASK_DEDUPE_EXPIRE_SECONDS = 86400
MANAGED_TASK_DUE_EXPIRE_SECONDS = 604800
MANAGED_TASK_PROCESSING_EXPIRE_SECONDS = 604800
MANAGED_TASK_VISIBILITY_TIMEOUT_MS = 30000
MANAGED_TASK_KEY_PREFIX = "game-hub:managed-task:"
MANAGED_TASK_ORPHAN_CLAIM_RETRIES = 20
MANAGED_TASK_RECOVER_BATCH_SIZE = 50

_ENQUEUE_TASK_CREATED = 1
_ENQUEUE_TASK_DUPLICATED = 2
_ENQUEUE_TASK_FAILED = 0

_ENQUEUE_TASK_SCRIPT = """
local dedupeCreated = redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', tonumber(ARGV[2]))
if not dedupeCreated then
    return 2
end
local taskSaved = redis.call('SET', KEYS[2], ARGV[3], 'EX', tonumber(ARGV[4]))
if not taskSaved then
    redis.call('DEL', KEYS[1])
    return 0
end
redis.call('ZADD', KEYS[3], ARGV[5], ARGV[1])
redis.call('EXPIRE', KEYS[3], tonumber(ARGV[6]))
return 1
"""

_RELEASE_TO_DUE_SCRIPT = """
redis.call('SET', KEYS[1], ARGV[2], 'EX', tonumber(ARGV[4]))
redis.call('ZADD', KEYS[3], ARGV[3], ARGV[1])
redis.call('EXPIRE', KEYS[3], tonumber(ARGV[5]))
redis.call('ZREM', KEYS[2], ARGV[1])
return 1
"""

_FINALIZE_TASK_SCRIPT = """
redis.call('SET', KEYS[1], ARGV[2], 'EX', tonumber(ARGV[3]))
redis.call('ZREM', KEYS[2], ARGV[1])
redis.call('ZREM', KEYS[3], ARGV[1])
return 1
"""

_CLEANUP_ORPHAN_TASK_SCRIPT = """
redis.call('ZREM', KEYS[1], ARGV[1])
redis.call('ZREM', KEYS[2], ARGV[1])
return 1
"""

_CLAIM_DUE_TASK_SCRIPT = """
local tasks = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, 1)
if #tasks == 0 then
    return ''
end
local taskId = tasks[1]
redis.call('ZREM', KEYS[1], taskId)
redis.call('ZADD', KEYS[2], ARGV[2], taskId)
redis.call('EXPIRE', KEYS[2], tonumber(ARGV[3]))
local taskKey = ARGV[4] .. taskId
local taskJson = redis.call('GET', taskKey)
if not taskJson then
    redis.call('ZREM', KEYS[2], taskId)
    return 'ORPHAN:' .. taskId
end
local task = cjson.decode(taskJson)
local status = task['status'] or ''
if status == 'done' or status == 'skipped' or status == 'failed' then
    redis.call('ZREM', KEYS[2], taskId)
    return 'ORPHAN:' .. taskId
end
if status ~= 'pending' and status ~= 'running' then
    redis.call('ZREM', KEYS[2], taskId)
    redis.call('ZREM', KEYS[1], taskId)
    return 'ORPHAN:' .. taskId
end
task['status'] = 'running'
task['updatedAt'] = tonumber(ARGV[5])
local newJson = cjson.encode(task)
redis.call('SET', taskKey, newJson, 'EX', tonumber(ARGV[6]))
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
local taskKey = ARGV[2] .. taskId
local taskJson = redis.call('GET', taskKey)
if not taskJson then
    redis.call('ZREM', KEYS[1], taskId)
    redis.call('ZREM', KEYS[2], taskId)
    return 'ORPHAN:' .. taskId
end
local task = cjson.decode(taskJson)
local status = task['status'] or ''
if status == 'done' or status == 'skipped' or status == 'failed' then
    redis.call('ZREM', KEYS[1], taskId)
    return 'FINAL:' .. taskId
end
if status ~= 'running' and status ~= 'pending' then
    redis.call('ZREM', KEYS[1], taskId)
    redis.call('ZREM', KEYS[2], taskId)
    return 'ORPHAN:' .. taskId
end
local executeAfter = tonumber(task['executeAfterMs']) or tonumber(ARGV[1])
if executeAfter < tonumber(ARGV[1]) then
    executeAfter = tonumber(ARGV[1])
end
task['status'] = 'pending'
task['updatedAt'] = tonumber(ARGV[4])
local newJson = cjson.encode(task)
redis.call('SET', taskKey, newJson, 'EX', tonumber(ARGV[3]))
redis.call('ZADD', KEYS[2], executeAfter, taskId)
redis.call('EXPIRE', KEYS[2], tonumber(ARGV[5]))
redis.call('ZREM', KEYS[1], taskId)
return taskId
"""


class ManagedTaskEnqueueResult(object):
    """托管任务入队结果。"""

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


class ManagedTaskRepository(object):
    """托管任务 Redis 读写。"""

    def __init__(self, redis: RedisClient = redis_client) -> None:
        """
        初始化托管任务仓库。

        :param redis: Redis 工具。
        """
        self._redis = redis

    async def enqueue_task(
        self,
        room_id: str,
        player_id: str,
        expected_version: int,
        task_data: Dict[str, Any],
    ) -> ManagedTaskEnqueueResult:
        """
        原子写入 dedupe、任务数据与 due zset。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param expected_version: 期望房间版本。
        :param task_data: 任务对象。
        :return: 入队结果（created / duplicated / failed）。
        """
        task_id = str(task_data.get("taskId", "")).strip()
        if not task_id:
            return ManagedTaskEnqueueResult(failed=True)
        execute_after_ms = task_data.get("executeAfterMs")
        if execute_after_ms is None:
            return ManagedTaskEnqueueResult(failed=True)
        dedupe_key = RedisKeys.managed_task_dedupe(room_id, player_id, expected_version)
        stored_task_data = dict(task_data)
        stored_task_data["dedupeKey"] = dedupe_key
        try:
            task_json = json.dumps(stored_task_data, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            logger.exception("managed task enqueue encode failed, taskId=%s", task_id)
            return ManagedTaskEnqueueResult(failed=True)
        task_key = RedisKeys.managed_task(task_id)
        due_key = RedisKeys.managed_task_due()
        result = await self._redis.eval(
            _ENQUEUE_TASK_SCRIPT,
            3,
            [dedupe_key, task_key, due_key],
            [
                task_id,
                str(MANAGED_TASK_DEDUPE_EXPIRE_SECONDS),
                task_json,
                str(MANAGED_TASK_DATA_EXPIRE_SECONDS),
                str(float(execute_after_ms)),
                str(MANAGED_TASK_DUE_EXPIRE_SECONDS),
            ],
        )
        normalized_result = int(result or 0)
        if normalized_result == _ENQUEUE_TASK_CREATED:
            return ManagedTaskEnqueueResult(created=True)
        if normalized_result == _ENQUEUE_TASK_DUPLICATED:
            return ManagedTaskEnqueueResult(duplicated=True)
        return ManagedTaskEnqueueResult(failed=True)

    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        读取托管任务数据。

        :param task_id: 任务 ID。
        :return: 任务对象；不存在时返回 ``None``。
        """
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            return None
        data = await self._redis.get_json(RedisKeys.managed_task(normalized_task_id))
        if not isinstance(data, dict):
            return None
        return data

    async def update_task(self, task_id: str, task_data: Dict[str, Any]) -> bool:
        """
        更新托管任务数据。

        :param task_id: 任务 ID。
        :param task_data: 任务对象。
        :return: 是否更新成功。
        """
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            return False
        task_data["updatedAt"] = now_ms()
        return await self._save_task(task_data)

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
        visibility_timeout_ms: int = MANAGED_TASK_VISIBILITY_TIMEOUT_MS,
    ) -> Optional[Dict[str, Any]]:
        """
        原子领取一个到期任务：移入 processing 并标记 running。

        :param current_time_ms: 当前时间（毫秒）。
        :param visibility_timeout_ms: 可见性超时（毫秒）。
        :return: 已领取任务对象；无到期任务时返回 ``None``。
        """
        visibility_deadline_ms = int(current_time_ms) + int(visibility_timeout_ms)
        updated_at = now_ms()
        for _attempt in range(MANAGED_TASK_ORPHAN_CLAIM_RETRIES):
            result = await self._redis.eval_raw(
                _CLAIM_DUE_TASK_SCRIPT,
                2,
                [RedisKeys.managed_task_due(), RedisKeys.managed_task_processing()],
                [
                    str(int(current_time_ms)),
                    str(visibility_deadline_ms),
                    str(MANAGED_TASK_PROCESSING_EXPIRE_SECONDS),
                    MANAGED_TASK_KEY_PREFIX,
                    str(updated_at),
                    str(MANAGED_TASK_DATA_EXPIRE_SECONDS),
                ],
            )
            if result is None:
                return None
            result_text = str(result).strip()
            if not result_text:
                return None
            if result_text.startswith("ORPHAN:"):
                continue
            try:
                task_data = json.loads(result_text)
            except (TypeError, ValueError):
                logger.warning("managed task claim decode failed, raw=%s", result_text)
                continue
            if not isinstance(task_data, dict):
                continue
            return task_data
        return None

    async def remove_from_processing(self, task_id: str) -> bool:
        """
        从 processing zset 移除任务。

        :param task_id: 任务 ID。
        :return: 是否执行完成。
        """
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            return False
        await self._redis.zrem(RedisKeys.managed_task_processing(), normalized_task_id)
        return True

    async def release_to_due(
        self,
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
        if status in ("done", "skipped", "failed"):
            return False
        stored_task_data = dict(task_data)
        stored_task_data["status"] = "pending"
        stored_task_data["updatedAt"] = now_ms()
        try:
            task_json = json.dumps(stored_task_data, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            logger.exception("managed task release encode failed, taskId=%s", normalized_task_id)
            return False
        result = await self._redis.eval(
            _RELEASE_TO_DUE_SCRIPT,
            3,
            [
                RedisKeys.managed_task(normalized_task_id),
                RedisKeys.managed_task_processing(),
                RedisKeys.managed_task_due(),
            ],
            [
                normalized_task_id,
                task_json,
                str(float(execute_after_ms)),
                str(MANAGED_TASK_DATA_EXPIRE_SECONDS),
                str(MANAGED_TASK_DUE_EXPIRE_SECONDS),
            ],
        )
        return int(result or 0) > 0

    async def finalize_task(self, task_id: str, task_data: Dict[str, Any]) -> bool:
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
        stored_task_data["updatedAt"] = now_ms()
        try:
            task_json = json.dumps(stored_task_data, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            logger.exception("managed task finalize encode failed, taskId=%s", normalized_task_id)
            return False
        result = await self._redis.eval(
            _FINALIZE_TASK_SCRIPT,
            3,
            [
                RedisKeys.managed_task(normalized_task_id),
                RedisKeys.managed_task_processing(),
                RedisKeys.managed_task_due(),
            ],
            [
                normalized_task_id,
                task_json,
                str(MANAGED_TASK_DATA_EXPIRE_SECONDS),
            ],
        )
        return int(result or 0) > 0

    async def recover_stale_processing_tasks(self, current_time_ms: int) -> List[str]:
        """
        恢复 processing zset 中可见性已过期的任务。

        :param current_time_ms: 当前时间（毫秒）。
        :return: 已恢复的任务 ID 列表。
        """
        recovered = []
        updated_at = now_ms()
        for _attempt in range(MANAGED_TASK_RECOVER_BATCH_SIZE):
            result = await self._redis.eval_raw(
                _RECOVER_STALE_PROCESSING_SCRIPT,
                2,
                [RedisKeys.managed_task_processing(), RedisKeys.managed_task_due()],
                [
                    str(int(current_time_ms)),
                    MANAGED_TASK_KEY_PREFIX,
                    str(MANAGED_TASK_DATA_EXPIRE_SECONDS),
                    str(updated_at),
                    str(MANAGED_TASK_DUE_EXPIRE_SECONDS),
                ],
            )
            if result is None:
                break
            result_text = str(result).strip()
            if not result_text:
                break
            if result_text.startswith("ORPHAN:") or result_text.startswith("FINAL:"):
                continue
            recovered.append(result_text)
        return recovered

    async def _cleanup_orphan_task(self, task_id: str) -> None:
        """
        原子清理无 task data 的 processing 与 due 脏项。

        :param task_id: 任务 ID。
        :return: 无。
        """
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            return
        await self._redis.eval(
            _CLEANUP_ORPHAN_TASK_SCRIPT,
            2,
            [RedisKeys.managed_task_processing(), RedisKeys.managed_task_due()],
            [normalized_task_id],
        )

    async def _save_task(self, task_data: Dict[str, Any]) -> bool:
        """
        写入托管任务数据。

        :param task_data: 任务对象。
        :return: 是否写入成功。
        """
        task_id = str(task_data.get("taskId", "")).strip()
        if not task_id:
            return False
        return await self._redis.set_json(
            RedisKeys.managed_task(task_id),
            task_data,
            MANAGED_TASK_DATA_EXPIRE_SECONDS,
        )
