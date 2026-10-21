"""Outbox Handler 严格执行结果。"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OutboxHandlerStatus(str, Enum):
    """Outbox Handler 的完整执行状态。"""

    DONE = "DONE"
    ALREADY_DONE = "ALREADY_DONE"
    RETRY = "RETRY"
    RECOVER = "RECOVER"
    OBSOLETE = "OBSOLETE"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"


class OutboxHandlerResult(BaseModel):
    """Outbox Handler 的严格执行结果。"""

    model_config = ConfigDict(extra="forbid")

    status: OutboxHandlerStatus
    reasonCode: str = Field(min_length=1, max_length=64)
    reasonMessage: str = Field(default="", max_length=500)
    retryAfterMs: Optional[int] = Field(default=None, ge=0)


class TaskSchedulingStatus(str, Enum):
    """Post-turn 后台任务创建状态。"""

    SCHEDULED = "SCHEDULED"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    NOT_REQUIRED = "NOT_REQUIRED"
    RETRY = "RETRY"
