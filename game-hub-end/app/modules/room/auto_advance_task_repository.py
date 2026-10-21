"""阶段自动推进任务的队列键与去重身份。"""

from typing import Any, Dict

from app.core.clock import Clock, system_clock
from app.core.redis.redis_client import RedisClient, redis_client
from app.core.redis.redis_keys import RedisKeys
from app.modules.room.task_queue_repository import TaskEnqueueResult, TaskQueueKeys, TaskQueueRepository


class AutoAdvanceTaskRepository(TaskQueueRepository):
    """声明阶段自动推进队列存储与领域去重维度。"""

    def __init__(self, redis: RedisClient = redis_client, clock: Clock = system_clock) -> None:
        """装配独立任务键空间与共享队列存储。"""
        super().__init__(TaskQueueKeys(
            records=RedisKeys.auto_advance_task_records,
            due=RedisKeys.auto_advance_task_due,
            processing=RedisKeys.auto_advance_task_processing,
            records_shard=RedisKeys.auto_advance_task_records_shard,
            due_shard=RedisKeys.auto_advance_task_due_shard,
            processing_shard=RedisKeys.auto_advance_task_processing_shard,
        ), redis=redis, clock=clock)

    async def enqueue_task(self, room_id: str, expected_version: int, expected_phase: str, task_data: Dict[str, Any]) -> TaskEnqueueResult:
        """校验阶段并以房间、版本和阶段标识唯一自动推进任务。"""
        phase = str(expected_phase or "").strip()
        if not phase:
            return TaskEnqueueResult(failed=True)
        dedupe_key = RedisKeys.auto_advance_task_dedupe(room_id, expected_version, phase)
        return await self._enqueue_task(room_id, dedupe_key, task_data)
