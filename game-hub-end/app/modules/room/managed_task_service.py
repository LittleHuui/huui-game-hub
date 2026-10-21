"""托管回合任务服务。"""

import asyncio
import logging
from typing import Awaitable, Callable, Dict, Literal, Optional, Set

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.lock.distributed_lock import LockAcquireError, RedisDistributedLock, distributed_lock
from app.core.redis.redis_keys import RedisKeys
from app.core.clock import Clock, Sleeper, system_clock, system_sleeper
from app.modules.room.managed_task_repository import (
    ManagedTaskRepository,
)
from app.modules.room.task_error_support import (
    TASK_PERMANENT_SKIP_REASONS,
    TASK_TEMPORARY_FAILURE_REASONS,
    is_temporary_failure_reason,
    managed_submit_result_from_exception,
)
from app.modules.room.task_errors import (
    TaskObsoleteError,
    TaskTemporaryInfrastructureError,
)
from app.modules.room.task_retry_policy import MANAGED_TASK_RETRY_POLICY, TaskRetryPolicy

from app.modules.room.task_queue_repository import TASK_QUEUE_VISIBILITY_TIMEOUT_MS, TaskEnqueueResult

logger = logging.getLogger(__name__)

MANAGED_ROOM_RUNNING_LOCK_TTL_SECONDS = 8
MANAGED_TASK_MAX_CLAIM_PER_TICK = 50
MANAGED_TASK_TICK_INTERVAL_MS = 50
# 平台托管动作默认延迟 1 秒执行。
MANAGED_TURN_DELAY_MS = 1000
MANAGED_TASK_PERMANENT_SKIP_REASONS = TASK_PERMANENT_SKIP_REASONS
MANAGED_TASK_TEMPORARY_FAILURE_REASONS = TASK_TEMPORARY_FAILURE_REASONS


class ManagedTurnTask(BaseModel):
    """托管回合任务。"""

    model_config = ConfigDict(extra="forbid")

    taskId: str
    roomId: str
    gameCode: str
    playerId: str
    expectedVersion: int = Field(ge=0)
    expectedGameVersion: Optional[int] = Field(default=None, ge=0)
    expectedPhase: Optional[str] = None
    expectedPlayerId: Optional[str] = None
    expectedCurrentPlayerId: str
    executeAfterMs: int = Field(ge=0)
    status: Literal["PENDING", "RUNNING", "DONE", "SKIPPED", "FAILED"]
    createdAt: int = Field(ge=0)
    reason: str
    skipReason: Optional[str] = None
    retryCount: int = Field(default=0, ge=0)
    attemptCount: int = Field(default=0, ge=0)
    recoveryCount: int = Field(default=0, ge=0)
    lastFailureReason: Optional[str] = None
    nextAttemptAt: Optional[int] = Field(default=None, ge=0)
    leaseUntil: Optional[int] = Field(default=None, ge=0)
    updatedAt: Optional[int] = None
    dedupeKey: Optional[str] = None

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value):
        """将持久化任务状态规范为严格大写枚举。"""
        return str(value or "").strip().upper()


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
        clock: Clock = system_clock,
        sleeper: Sleeper = system_sleeper,
        retry_policy: TaskRetryPolicy = MANAGED_TASK_RETRY_POLICY,
    ) -> None:
        """
        初始化托管任务服务。

        :param repository: 托管任务 Redis 仓库。
        :param lock_service: 分布式锁工具。
        :param clock: 可注入时钟。
        :param sleeper: 可注入异步等待器。
        :param retry_policy: 短重试与恢复策略。
        """
        self._repository = repository or ManagedTaskRepository(clock=clock)
        self._lock_service = lock_service
        self._clock = clock
        self._sleeper = sleeper
        self._retry_policy = retry_policy
        self._running = False
        self._task = None  # type: Optional[asyncio.Task]
        self._worker_tasks = set()  # type: Set[asyncio.Task]
        self._submit_handler = None  # type: Optional[Callable[[ManagedTurnTask], Awaitable[ManagedTaskSubmitResult]]]
        self._recovery_validator = None  # type: Optional[Callable[[ManagedTurnTask], Awaitable[Optional[str]]]]
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

    def bind_recovery_validator(
        self,
        recovery_validator: Callable[[ManagedTurnTask], Awaitable[Optional[str]]],
    ) -> None:
        """
        绑定短重试耗尽后的同任务恢复校验器。

        :param recovery_validator: 返回永久跳过原因；仍有效时返回 ``None``。
        :return: 无。
        """
        self._recovery_validator = recovery_validator

    async def start(self) -> None:
        """
        启动托管任务后台循环。

        :return: 无。
        """
        if not self._handlers_bound or self._submit_handler is None:
            raise RuntimeError("托管任务 submit handler 未绑定")
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
        workers = list(self._worker_tasks)
        for worker in workers:
            worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        self._worker_tasks.clear()

    async def enqueue_task(self, task: ManagedTurnTask) -> TaskEnqueueResult:
        """
        入队托管任务，重复任务返回 duplicated。

        :param task: 托管任务。
        :return: 入队结果。
        """
        current_time = self._clock.now_ms()
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

    async def get_task(self, room_id: str, task_id: str) -> Optional[ManagedTurnTask]:
        """
        读取托管任务。

        :param task_id: 任务 ID。
        :return: 托管任务；不存在时返回 ``None``。
        """
        task_data = await self._repository.get_task(room_id, task_id)
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
            await self._sleeper.sleep_ms(MANAGED_TASK_TICK_INTERVAL_MS)

    async def _tick_once(self) -> None:
        """
        扫描并领取到期任务。

        :return: 无。
        """
        if self._submit_handler is None:
            return
        current_time = self._clock.now_ms()
        for shard_index in range(RedisKeys.ROOM_SHARD_COUNT):
            await self._repository.recover_stale_processing_tasks(
                current_time, shard_index, max_count=1
            )
        claimed_count = 0
        while claimed_count < MANAGED_TASK_MAX_CLAIM_PER_TICK:
            claimed_in_round = False
            for shard_index in range(RedisKeys.ROOM_SHARD_COUNT):
                if claimed_count >= MANAGED_TASK_MAX_CLAIM_PER_TICK:
                    break
                task_data = await self._repository.claim_due_task(
                    current_time, shard_index, TASK_QUEUE_VISIBILITY_TIMEOUT_MS
                )
                if task_data is None:
                    continue
                claimed_in_round = True
                claimed_count += 1
                self._create_worker_task(task_data)
            if not claimed_in_round:
                break

    def _create_worker_task(self, task_data: Dict[str, object]) -> None:
        """
        创建并跟踪托管 worker 子任务。

        :param task_data: 已领取任务对象。
        :return: 无。
        """
        task = asyncio.create_task(self._process_claimed_task(task_data))
        self._worker_tasks.add(task)
        task.add_done_callback(self._on_worker_done)

    def _on_worker_done(self, task: asyncio.Task) -> None:
        """
        清理结束的 worker 并记录未处理异常。

        :param task: 已结束 worker。
        :return: 无。
        """
        self._worker_tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error(
                "managed task worker failed",
                exc_info=(type(error), error, error.__traceback__),
            )

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
            await self._repository.remove_from_processing(str(task_data.get("roomId", "")).strip(), task_id)
            return
        status = str(task.status).strip()
        if status not in ("PENDING", "RUNNING"):
            await self._repository.remove_from_processing(task.roomId, task_id)
            return
        if int(task.executeAfterMs) > self._clock.now_ms():
            task_data["status"] = "PENDING"
            await self._repository.release_to_due(
                task.roomId,
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
            refreshed = await self._repository.get_task(task.roomId, task.taskId)
            if refreshed is None:
                await self._repository.remove_from_processing(task.roomId, task_id)
                return
            task = ManagedTurnTask.model_validate(refreshed)
            if str(task.status).strip() not in ("PENDING", "RUNNING"):
                await self._repository.remove_from_processing(task.roomId, task_id)
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
            return ManagedTaskSubmitResult(status="failed", skipReason="invalidTaskPayload")
        try:
            return await submit_handler(task)
        except (TaskObsoleteError, TaskTemporaryInfrastructureError) as exc:
            return managed_submit_result_from_exception(exc)
        except Exception as exc:
            logger.exception(
                "managed task execute failed, roomId=%s taskId=%s type=%s",
                task.roomId,
                task.taskId,
                type(exc).__name__,
            )
            return managed_submit_result_from_exception(exc)

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
            await self._finish_task(task, "DONE", None)
            return
        if result.status == "skipped":
            await self._finish_task(task, "SKIPPED", result.skipReason)
            return
        if result.status == "pending":
            await self._reschedule_or_skip(task, "lockTimeout")
            return
        skip_reason = str(result.skipReason or "").strip()
        if not skip_reason:
            skip_reason = "invalidTaskPayload"
        if is_temporary_failure_reason(skip_reason):
            await self._reschedule_or_skip(task, skip_reason)
            return
        await self._finish_task(task, "FAILED", skip_reason)

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
        refreshed = await self._repository.get_task(task.roomId, task.taskId)
        task_data = dict(refreshed if isinstance(refreshed, dict) else task.model_dump())
        task_data["status"] = status
        task_data["skipReason"] = skip_reason
        task_data["lastFailureReason"] = skip_reason
        task_data["updatedAt"] = self._clock.now_ms()
        await self._repository.finalize_task(task.roomId, task.taskId, task_data)
        if status == "FAILED":
            logger.error(
                "managed task failed permanently, roomId=%s taskId=%s reason=%s attemptCount=%s retryCount=%s recoveryCount=%s",
                task.roomId,
                task.taskId,
                skip_reason,
                task_data.get("attemptCount"),
                task_data.get("retryCount"),
                task_data.get("recoveryCount"),
            )
        if status != "FAILED" and self._should_release_dedupe(status, skip_reason):
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
        return status == "DONE"

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
        临时失败时短退避重试；短重试耗尽后进入同任务恢复周期。

        :param task: 托管任务。
        :param skip_reason: 失败原因。
        :return: 无。
        """
        next_retry_count = int(task.retryCount) + 1
        if next_retry_count > len(self._retry_policy.retry_delays_ms):
            await self._recover_same_task(task, skip_reason)
            return
        delay_ms = self._retry_policy.retry_delays_ms[next_retry_count - 1]
        next_execute_after_ms = self._clock.now_ms() + delay_ms
        task_data = task.model_dump()
        task_data["retryCount"] = next_retry_count
        task_data["lastFailureReason"] = skip_reason
        task_data["status"] = "PENDING"
        task_data["executeAfterMs"] = next_execute_after_ms
        task_data["nextAttemptAt"] = next_execute_after_ms
        task_data["skipReason"] = None
        task_data["updatedAt"] = self._clock.now_ms()
        await self._repository.release_to_due(task.roomId, task.taskId, next_execute_after_ms, task_data)

    async def _recover_same_task(self, task: ManagedTurnTask, failure_reason: str) -> None:
        """
        短重试耗尽后，在同一 taskId 上进入恢复周期。

        :param task: 托管任务。
        :param failure_reason: 短重试耗尽原因。
        :return: 无。
        """
        try:
            obsolete_reason = await self._validate_task_for_recovery(task)
        except TaskTemporaryInfrastructureError as exc:
            # 恢复校验失败同样消耗恢复周期，并经过队列退避；禁止即时互递归。
            obsolete_reason = None
            failure_reason = exc.reason
        if obsolete_reason:
            await self._finish_task(task, "SKIPPED", obsolete_reason)
            return
        next_recovery_count = int(task.recoveryCount) + 1
        if next_recovery_count > self._retry_policy.max_recovery_count:
            logger.error(
                "managed task recovery exhausted, roomId=%s taskId=%s reason=%s attemptCount=%s retryCount=%s recoveryCount=%s",
                task.roomId,
                task.taskId,
                failure_reason,
                task.attemptCount,
                task.retryCount,
                task.recoveryCount,
            )
            refreshed = await self._repository.get_task(task.roomId, task.taskId)
            task_data = dict(refreshed if isinstance(refreshed, dict) else task.model_dump())
            task_data["retryCount"] = int(task.retryCount)
            task_data["recoveryCount"] = int(task.recoveryCount)
            task_data["attemptCount"] = int(task.attemptCount)
            await self._finish_task(
                ManagedTurnTask.model_validate(task_data),
                "FAILED",
                failure_reason,
            )
            return
        delay_ms = self._retry_policy.recovery_delay_ms(next_recovery_count)
        next_execute_after_ms = self._clock.now_ms() + delay_ms
        refreshed = await self._repository.get_task(task.roomId, task.taskId)
        task_data = dict(refreshed if isinstance(refreshed, dict) else task.model_dump())
        task_data["recoveryCount"] = next_recovery_count
        task_data["retryCount"] = 0
        task_data["lastFailureReason"] = failure_reason
        task_data["status"] = "PENDING"
        task_data["executeAfterMs"] = next_execute_after_ms
        task_data["nextAttemptAt"] = next_execute_after_ms
        task_data["skipReason"] = None
        task_data["updatedAt"] = self._clock.now_ms()
        logger.warning(
            "managed task entering recovery cycle, roomId=%s taskId=%s recoveryCount=%s nextAttemptAt=%s reason=%s",
            task.roomId,
            task.taskId,
            next_recovery_count,
            next_execute_after_ms,
            failure_reason,
        )
        await self._repository.release_to_due(task.roomId, task.taskId, next_execute_after_ms, task_data)

    async def _validate_task_for_recovery(self, task: ManagedTurnTask) -> Optional[str]:
        """
        恢复前校验任务是否已过期。

        :param task: 托管任务。
        :return: 永久跳过原因；仍有效时返回 ``None``。
        """
        validator = self._recovery_validator
        if validator is None:
            return None
        try:
            return await validator(task)
        except TaskTemporaryInfrastructureError:
            raise
        except TaskObsoleteError as exc:
            return exc.reason
        except Exception as exc:
            logger.exception(
                "managed task recovery validation failed, roomId=%s taskId=%s type=%s",
                task.roomId,
                task.taskId,
                type(exc).__name__,
            )
            raise TaskTemporaryInfrastructureError(
                "unknownError",
                cause=exc,
            )


managed_turn_task_service = ManagedTurnTaskService()
