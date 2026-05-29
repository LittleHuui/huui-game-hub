"""托管回合任务服务。"""

import asyncio
import logging
from typing import Awaitable, Callable, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.lock.distributed_lock import LockAcquireError, RedisDistributedLock, distributed_lock
from app.core.redis.redis_keys import RedisKeys
from app.core.time_utils import now_ms
from app.modules.room.managed_task_repository import (
    MANAGED_TASK_VISIBILITY_TIMEOUT_MS,
    ManagedTaskEnqueueResult,
    ManagedTaskRepository,
)

logger = logging.getLogger(__name__)

MANAGED_LOCK_RETRY_DELAYS_MS = [100, 300, 700]
MANAGED_ROOM_RUNNING_LOCK_TTL_SECONDS = 8
MANAGED_TASK_MAX_CLAIM_PER_TICK = 50
# 平台托管动作默认延迟 1 秒执行。
MANAGED_TURN_DELAY_MS = 1000
MANAGED_TASK_PERMANENT_SKIP_REASONS = frozenset(
    {
        "versionChanged",
        "currentPlayerChanged",
        "playerNotManaged",
        "roomNotPlaying",
        "noLegalAction",
    }
)
MANAGED_TASK_TEMPORARY_FAILURE_REASONS = frozenset(
    {
        "lockTimeout",
        "submitFailed",
        "unexpectedError",
        "redisError",
    }
)


class ManagedTurnTask(BaseModel):
    """托管回合任务。"""

    model_config = ConfigDict(extra="forbid")

    taskId: str
    roomId: str
    gameCode: str
    playerId: str
    expectedVersion: int = Field(ge=0)
    expectedCurrentPlayerId: str
    executeAfterMs: int = Field(ge=0)
    status: str
    createdAt: int = Field(ge=0)
    reason: str
    skipReason: Optional[str] = None
    retryCount: int = Field(default=0, ge=0)
    updatedAt: Optional[int] = None
    dedupeKey: Optional[str] = None


class ManagedTaskSubmitResult(BaseModel):
    """托管任务提交结果。"""

    model_config = ConfigDict(extra="forbid")

    status: str
    skipReason: Optional[str] = None


class ManagedTurnTaskService(object):
    """按房间串行执行托管回合任务。"""

    def __init__(
        self,
        repository: Optional[ManagedTaskRepository] = None,
        lock_service: RedisDistributedLock = distributed_lock,
    ) -> None:
        """
        初始化托管任务服务。

        :param repository: 托管任务 Redis 仓库。
        :param lock_service: 分布式锁工具。
        """
        self._repository = repository or ManagedTaskRepository()
        self._lock_service = lock_service
        self._running = False
        self._task = None  # type: Optional[asyncio.Task]
        self._submit_handler = None  # type: Optional[Callable[[ManagedTurnTask], Awaitable[ManagedTaskSubmitResult]]]
        self._handlers_bound = False

    def bind_submit_handler(
        self,
        submit_handler: Callable[[ManagedTurnTask], Awaitable[ManagedTaskSubmitResult]],
    ) -> None:
        """
        绑定托管动作提交通道。

        :param submit_handler: 托管动作提交函数。
        :return: 无。
        """
        self._submit_handler = submit_handler
        self._handlers_bound = True

    async def start(self) -> None:
        """
        启动托管任务后台循环。

        :return: 无。
        """
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """
        停止托管任务后台循环。

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

    async def enqueue_task(self, task: ManagedTurnTask) -> ManagedTaskEnqueueResult:
        """
        入队托管任务，重复任务返回 duplicated。

        :param task: 托管任务。
        :return: 入队结果。
        """
        current_time = now_ms()
        task_data = task.model_dump()
        task_data["updatedAt"] = current_time
        result = await self._repository.enqueue_task(
            task.roomId,
            task.playerId,
            int(task.expectedVersion),
            task_data,
        )
        if result.duplicated:
            logger.debug(
                "managed task enqueue dedupe hit, roomId=%s playerId=%s expectedVersion=%s taskId=%s",
                task.roomId,
                task.playerId,
                task.expectedVersion,
                task.taskId,
            )
        elif result.failed:
            logger.warning(
                "managed task enqueue failed, roomId=%s playerId=%s expectedVersion=%s taskId=%s",
                task.roomId,
                task.playerId,
                task.expectedVersion,
                task.taskId,
            )
        return result

    async def get_task(self, task_id: str) -> Optional[ManagedTurnTask]:
        """
        读取托管任务。

        :param task_id: 任务 ID。
        :return: 托管任务；不存在时返回 ``None``。
        """
        task_data = await self._repository.get_task(task_id)
        if task_data is None:
            return None
        return ManagedTurnTask.model_validate(task_data)

    async def _run_loop(self) -> None:
        """
        后台循环：扫描到期任务并执行。

        :return: 无。
        """
        while self._running:
            try:
                await self._tick_once()
            except Exception:
                logger.exception("managed task tick failed")
            await asyncio.sleep(0.05)

    async def _tick_once(self) -> None:
        """
        扫描并领取到期任务。

        :return: 无。
        """
        if self._submit_handler is None:
            return
        current_time = now_ms()
        await self._repository.recover_stale_processing_tasks(current_time)
        claimed_count = 0
        while claimed_count < MANAGED_TASK_MAX_CLAIM_PER_TICK:
            task_data = await self._repository.claim_due_task(
                current_time,
                MANAGED_TASK_VISIBILITY_TIMEOUT_MS,
            )
            if task_data is None:
                break
            claimed_count += 1
            asyncio.create_task(self._process_claimed_task(task_data))

    async def _process_claimed_task(self, task_data: Dict[str, object]) -> None:
        """
        执行已领取的托管任务。

        :param task_data: 已领取任务对象。
        :return: 无。
        """
        task_id = str(task_data.get("taskId", "")).strip()
        if not task_id:
            return
        try:
            task = ManagedTurnTask.model_validate(task_data)
        except Exception:
            await self._repository.remove_from_processing(task_id)
            return
        status = str(task.status).strip()
        if status not in ("pending", "running"):
            await self._repository.remove_from_processing(task_id)
            return
        if int(task.executeAfterMs) > now_ms():
            task_data["status"] = "pending"
            await self._repository.release_to_due(
                task.taskId,
                int(task.executeAfterMs),
                task_data,
            )
            return
        lock_key = RedisKeys.managed_task_room_running(task.roomId)
        lock_handle = None
        try:
            lock_handle = await self._lock_service.acquire(
                lock_key,
                ttl_seconds=MANAGED_ROOM_RUNNING_LOCK_TTL_SECONDS,
                wait_timeout_ms=0,
                owner_hint="managed-task:{0}".format(task.taskId),
            )
        except LockAcquireError:
            await self._reschedule_or_skip(task, "lockTimeout")
            return
        try:
            refreshed = await self._repository.get_task(task.taskId)
            if refreshed is None:
                await self._repository.remove_from_processing(task_id)
                return
            task = ManagedTurnTask.model_validate(refreshed)
            if str(task.status).strip() not in ("pending", "running"):
                await self._repository.remove_from_processing(task_id)
                return
            result = await self._execute_task(task)
            await self._apply_submit_result(task, result)
        finally:
            if lock_handle is not None:
                await lock_handle.release()

    async def _execute_task(self, task: ManagedTurnTask) -> ManagedTaskSubmitResult:
        """
        调用托管动作提交通道。

        :param task: 托管任务。
        :return: 提交结果。
        """
        submit_handler = self._submit_handler
        if submit_handler is None:
            return ManagedTaskSubmitResult(status="failed", skipReason="unexpectedError")
        try:
            return await submit_handler(task)
        except Exception:
            logger.exception("managed task execute failed, roomId=%s taskId=%s", task.roomId, task.taskId)
            return ManagedTaskSubmitResult(status="failed", skipReason="unexpectedError")

    async def _apply_submit_result(
        self,
        task: ManagedTurnTask,
        result: ManagedTaskSubmitResult,
    ) -> None:
        """
        根据提交结果更新任务状态。

        :param task: 托管任务。
        :param result: 提交结果。
        :return: 无。
        """
        if result.status == "done":
            await self._finish_task(task, "done", None)
            return
        if result.status == "skipped":
            await self._finish_task(task, "skipped", result.skipReason)
            return
        if result.status == "pending":
            await self._reschedule_or_skip(task, "lockTimeout")
            return
        await self._finish_task(task, "failed", result.skipReason)

    async def _finish_task(
        self,
        task: ManagedTurnTask,
        status: str,
        skip_reason: Optional[str],
    ) -> None:
        """
        终结托管任务并按失败类型决定是否释放 dedupe。

        :param task: 托管任务。
        :param status: 终态（done / skipped / failed）。
        :param skip_reason: 跳过或失败原因。
        :return: 无。
        """
        refreshed = await self._repository.get_task(task.taskId)
        task_data = dict(refreshed if isinstance(refreshed, dict) else task.model_dump())
        task_data["status"] = status
        task_data["skipReason"] = skip_reason
        await self._repository.finalize_task(task.taskId, task_data)
        if self._should_release_dedupe(status, skip_reason):
            await self._release_task_dedupe(task_data)

    def _should_release_dedupe(self, status: str, skip_reason: Optional[str]) -> bool:
        """
        判断终态是否应释放 dedupe key。

        :param status: 任务终态。
        :param skip_reason: 跳过或失败原因。
        :return: 是否释放。
        """
        normalized_reason = str(skip_reason or "").strip()
        if normalized_reason in MANAGED_TASK_PERMANENT_SKIP_REASONS:
            return False
        if normalized_reason in MANAGED_TASK_TEMPORARY_FAILURE_REASONS:
            return True
        if status == "failed":
            return True
        return False

    async def _release_task_dedupe(self, task_data: Dict[str, object]) -> None:
        """
        释放任务对应 dedupe key（仅当仍指向本任务）。

        :param task_data: 任务对象。
        :return: 无。
        """
        dedupe_key = str(task_data.get("dedupeKey", "")).strip()
        task_id = str(task_data.get("taskId", "")).strip()
        if not dedupe_key:
            room_id = str(task_data.get("roomId", "")).strip()
            player_id = str(task_data.get("playerId", "")).strip()
            expected_version = task_data.get("expectedVersion")
            if room_id and player_id and expected_version is not None:
                dedupe_key = RedisKeys.managed_task_dedupe(
                    room_id,
                    player_id,
                    int(expected_version),
                )
        if not dedupe_key or not task_id:
            return
        released = await self._repository.release_dedupe_if_owner(dedupe_key, task_id)
        if not released:
            logger.info(
                "managed task dedupe not released, taskId=%s dedupeKey=%s",
                task_id,
                dedupe_key,
            )

    async def _reschedule_or_skip(self, task: ManagedTurnTask, skip_reason: str) -> None:
        """
        锁冲突时按退避重试，耗尽后标记跳过。

        :param task: 托管任务。
        :param skip_reason: 跳过原因。
        :return: 无。
        """
        next_retry_count = int(task.retryCount) + 1
        task_data = task.model_dump()
        task_data["retryCount"] = next_retry_count
        if next_retry_count > len(MANAGED_LOCK_RETRY_DELAYS_MS):
            await self._finish_task(task, "skipped", skip_reason)
            return
        delay_ms = MANAGED_LOCK_RETRY_DELAYS_MS[next_retry_count - 1]
        next_execute_after_ms = now_ms() + delay_ms
        task_data["status"] = "pending"
        task_data["executeAfterMs"] = next_execute_after_ms
        task_data["skipReason"] = None
        await self._repository.release_to_due(task.taskId, next_execute_after_ms, task_data)


managed_turn_task_service = ManagedTurnTaskService()
