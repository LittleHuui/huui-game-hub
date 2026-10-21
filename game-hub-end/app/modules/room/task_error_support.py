"""后台任务错误分类与结果映射。"""

import logging
from typing import Optional, Tuple

from redis.exceptions import RedisError

from app.core.lock.distributed_lock import LockAcquireError
from app.core.redis.redis_errors import RedisOperationError
from app.modules.room.task_errors import (
    TaskConflictReason,
    TaskContractError,
    TaskContractReason,
    TaskExecutionConflict,
    TaskObsoleteError,
    TaskObsoleteReason,
    TaskTemporaryInfrastructureError,
    TaskTemporaryReason,
)

logger = logging.getLogger(__name__)

TASK_PERMANENT_SKIP_REASONS = frozenset(
    {
        TaskObsoleteReason.VERSION_CHANGED,
        TaskObsoleteReason.PHASE_CHANGED,
        TaskObsoleteReason.CURRENT_PLAYER_CHANGED,
        TaskObsoleteReason.PLAYER_NOT_MANAGED,
        TaskObsoleteReason.ROOM_NOT_PLAYING,
        TaskObsoleteReason.RUNTIME_MISSING,
        TaskObsoleteReason.TASK_ALREADY_OBSOLETE,
    }
)

TASK_TEMPORARY_FAILURE_REASONS = frozenset(
    {
        TaskTemporaryReason.LOCK_TIMEOUT,
        TaskTemporaryReason.LOCK_UNAVAILABLE,
        TaskTemporaryReason.REDIS_ERROR,
        TaskTemporaryReason.REDIS_UNAVAILABLE,
        TaskTemporaryReason.REPOSITORY_TIMEOUT,
        TaskTemporaryReason.QUEUE_UNAVAILABLE,
        TaskTemporaryReason.DATABASE_UNAVAILABLE,
        TaskTemporaryReason.STATE_READER_RETRY,
        TaskTemporaryReason.UNKNOWN_ERROR,
        TaskConflictReason.VERSION_CONFLICT,
    }
)

TASK_CONTRACT_FAILURE_REASONS = frozenset(
    {
        TaskContractReason.NO_LEGAL_ACTION,
        TaskContractReason.RESOLVER_REJECTED,
        TaskContractReason.CANDIDATE_CONTRACT_ERROR,
        TaskContractReason.INVALID_TASK_PAYLOAD,
        TaskContractReason.ADVANCE_CONTRACT_ERROR,
        TaskContractReason.FALLBACK_CONTRACT_ERROR,
    }
)


def is_temporary_failure_reason(reason: Optional[str]) -> bool:
    """
    判断失败原因是否应进入短重试/恢复。

    :param reason: 失败原因码。
    :return: 是否临时失败。
    """
    return str(reason or "").strip() in TASK_TEMPORARY_FAILURE_REASONS


def is_contract_failure_reason(reason: Optional[str]) -> bool:
    """
    判断失败原因是否应永久 FAILED。

    :param reason: 失败原因码。
    :return: 是否合同失败。
    """
    return str(reason or "").strip() in TASK_CONTRACT_FAILURE_REASONS


def is_permanent_skip_reason(reason: Optional[str]) -> bool:
    """
    判断跳过原因是否表示任务已过期。

    :param reason: 跳过原因码。
    :return: 是否永久跳过。
    """
    return str(reason or "").strip() in TASK_PERMANENT_SKIP_REASONS


def temporary_reason_from_exception(exc: Exception) -> str:
    """
    将未分类异常映射为临时失败原因码。

    :param exc: 原始异常。
    :return: 临时失败原因码。
    """
    if isinstance(exc, TaskTemporaryInfrastructureError):
        return exc.reason
    if isinstance(exc, TaskExecutionConflict):
        return exc.reason
    if isinstance(exc, LockAcquireError):
        return TaskTemporaryReason.LOCK_UNAVAILABLE
    if isinstance(exc, (RedisError, RedisOperationError, OSError, TimeoutError)):
        return TaskTemporaryReason.REDIS_UNAVAILABLE
    exc_type_name = type(exc).__name__
    if exc_type_name == "RetryableGameStateInconsistentException":
        return TaskTemporaryReason.STATE_READER_RETRY
    logger.warning(
        "task unknown exception classified as temporary retry, type=%s",
        type(exc).__name__,
    )
    return TaskTemporaryReason.UNKNOWN_ERROR


def map_task_exception_to_submit(
    exc: Exception,
) -> Tuple[str, str]:
    """
    将任务执行异常映射为 submit 结果。

    :param exc: 任务执行异常。
    :return: ``(status, reason)``，status 为 ``done`` / ``skipped`` / ``failed`` / ``pending``。
    """
    if isinstance(exc, TaskObsoleteError):
        return "skipped", exc.reason
    if isinstance(exc, TaskTemporaryInfrastructureError):
        return "failed", exc.reason
    if isinstance(exc, TaskContractError):
        return "failed", exc.reason
    if isinstance(exc, TaskExecutionConflict):
        return "failed", exc.reason
    if isinstance(exc, LockAcquireError):
        return "pending", TaskTemporaryReason.LOCK_UNAVAILABLE
    return "failed", temporary_reason_from_exception(exc)


def wrap_redis_operation_error(exc: Exception) -> TaskTemporaryInfrastructureError:
    """
    将 Redis 层异常包装为任务临时基础设施异常。

    :param exc: Redis 相关异常。
    :return: 任务临时基础设施异常。
    """
    if isinstance(exc, TaskTemporaryInfrastructureError):
        return exc
    if isinstance(exc, RedisOperationError):
        return TaskTemporaryInfrastructureError(TaskTemporaryReason.REDIS_UNAVAILABLE, cause=exc)
    if isinstance(exc, RedisError):
        return TaskTemporaryInfrastructureError(TaskTemporaryReason.REDIS_ERROR, cause=exc)
    if isinstance(exc, (OSError, TimeoutError)):
        return TaskTemporaryInfrastructureError(TaskTemporaryReason.REPOSITORY_TIMEOUT, cause=exc)
    return TaskTemporaryInfrastructureError(TaskTemporaryReason.UNKNOWN_ERROR, cause=exc)


def auto_advance_submit_result_from_exception(exc: Exception):
    """
    将任务异常映射为自动推进提交结果。

    :param exc: 任务执行异常。
    :return: 自动推进任务提交结果。
    """
    from app.modules.room.auto_advance_task_service import AutoAdvanceTaskSubmitResult

    status, reason = map_task_exception_to_submit(exc)
    if status == "pending":
        return AutoAdvanceTaskSubmitResult(status="pending", skipReason=reason)
    if status == "skipped":
        return AutoAdvanceTaskSubmitResult(status="skipped", skipReason=reason)
    return AutoAdvanceTaskSubmitResult(status="failed", skipReason=reason)


def managed_submit_result_from_exception(exc: Exception):
    """
    将任务异常映射为托管提交结果。

    :param exc: 任务执行异常。
    :return: 托管任务提交结果。
    """
    from app.modules.room.managed_task_service import ManagedTaskSubmitResult

    status, reason = map_task_exception_to_submit(exc)
    if status == "pending":
        return ManagedTaskSubmitResult(status="pending", skipReason=reason)
    if status == "skipped":
        return ManagedTaskSubmitResult(status="skipped", skipReason=reason)
    return ManagedTaskSubmitResult(status="failed", skipReason=reason)
