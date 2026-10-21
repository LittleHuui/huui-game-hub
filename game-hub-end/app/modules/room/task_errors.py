"""后台任务错误分类。"""

from typing import Optional


class TaskObsoleteReason(object):
    """任务已过期原因码（勿用异常 message 文本判断）。"""

    VERSION_CHANGED = "versionChanged"
    PHASE_CHANGED = "phaseChanged"
    CURRENT_PLAYER_CHANGED = "currentPlayerChanged"
    PLAYER_NOT_MANAGED = "playerNotManaged"
    ROOM_NOT_PLAYING = "roomNotPlaying"
    GAME_ALREADY_OVER = "gameAlreadyOver"
    RUNTIME_MISSING = "runtimeMissing"
    TASK_ALREADY_OBSOLETE = "taskAlreadyObsolete"


class TaskTemporaryReason(object):
    """任务临时基础设施失败原因码。"""

    LOCK_TIMEOUT = "lockTimeout"
    LOCK_UNAVAILABLE = "lockUnavailable"
    REDIS_ERROR = "redisError"
    REDIS_UNAVAILABLE = "redisUnavailable"
    REPOSITORY_TIMEOUT = "repositoryTimeout"
    QUEUE_UNAVAILABLE = "queueUnavailable"
    DATABASE_UNAVAILABLE = "databaseUnavailable"
    STATE_READER_RETRY = "stateReaderRetry"
    UNKNOWN_ERROR = "unknownError"


class TaskContractReason(object):
    """任务合同/确定性失败原因码。"""

    NO_LEGAL_ACTION = "noLegalAction"
    RESOLVER_REJECTED = "resolverRejected"
    CANDIDATE_CONTRACT_ERROR = "candidateContractError"
    INVALID_TASK_PAYLOAD = "invalidTaskPayload"
    ADVANCE_CONTRACT_ERROR = "advanceContractError"
    FALLBACK_CONTRACT_ERROR = "fallbackContractError"


class TaskConflictReason(object):
    """提交冲突原因码。"""

    VERSION_CONFLICT = "versionConflict"


class TaskObsoleteError(Exception):
    """任务上下文已过期，应 SKIPPED。"""

    def __init__(self, reason: str) -> None:
        """
        初始化任务过期异常。

        :param reason: ``TaskObsoleteReason`` 原因码。
        """
        self.reason = str(reason or TaskObsoleteReason.TASK_ALREADY_OBSOLETE).strip()
        super().__init__(self.reason)


class TaskTemporaryInfrastructureError(Exception):
    """临时基础设施失败，应 RETRY/RECOVERY。"""

    def __init__(self, reason: str, cause: Optional[Exception] = None) -> None:
        """
        初始化临时基础设施异常。

        :param reason: ``TaskTemporaryReason`` 原因码。
        :param cause: 原始异常。
        """
        self.reason = str(reason or TaskTemporaryReason.UNKNOWN_ERROR).strip()
        self.cause = cause
        message = self.reason
        if cause is not None:
            message = "{0}: {1}".format(self.reason, cause)
        super().__init__(message)


class TaskContractError(Exception):
    """任务合同损坏，应永久 FAILED。"""

    def __init__(self, reason: str) -> None:
        """
        初始化任务合同异常。

        :param reason: ``TaskContractReason`` 原因码。
        """
        self.reason = str(reason or TaskContractReason.INVALID_TASK_PAYLOAD).strip()
        super().__init__(self.reason)


class TaskExecutionConflict(Exception):
    """提交时版本冲突，需重新读取权威状态后决定 SKIPPED 或重试。"""

    def __init__(self, reason: str = TaskConflictReason.VERSION_CONFLICT) -> None:
        """
        初始化任务执行冲突异常。

        :param reason: ``TaskConflictReason`` 原因码。
        """
        self.reason = str(reason or TaskConflictReason.VERSION_CONFLICT).strip()
        super().__init__(self.reason)
