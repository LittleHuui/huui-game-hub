"""托管回合任务的队列键与去重身份。"""

from typing import Any, Dict

from app.core.clock import Clock, system_clock
from app.core.redis.redis_client import RedisClient, redis_client
from app.core.redis.redis_keys import RedisKeys
from app.modules.room.task_queue_repository import TaskEnqueueResult, TaskQueueKeys, TaskQueueRepository


class ManagedTaskRepository(TaskQueueRepository):
    """声明托管回合队列存储与领域去重维度。"""

    def __init__(self, redis: RedisClient = redis_client, clock: Clock = system_clock) -> None:
        """装配独立任务键空间与共享队列存储。"""
        super().__init__(TaskQueueKeys(
            records=RedisKeys.managed_task_records,
            due=RedisKeys.managed_task_due,
            processing=RedisKeys.managed_task_processing,
            records_shard=RedisKeys.managed_task_records_shard,
            due_shard=RedisKeys.managed_task_due_shard,
            processing_shard=RedisKeys.managed_task_processing_shard,
        ), redis=redis, clock=clock)

    async def enqueue_task(self, room_id: str, player_id: str, expected_version: int, task_data: Dict[str, Any]) -> TaskEnqueueResult:
        """以房间、玩家、版本和阶段标识唯一托管任务并原子入队。"""
        dedupe_key = RedisKeys.managed_task_dedupe(
            room_id, player_id, expected_version, str(task_data.get("expectedPhase", "")).strip(),
        )
        return await self._enqueue_task(room_id, dedupe_key, task_data)
