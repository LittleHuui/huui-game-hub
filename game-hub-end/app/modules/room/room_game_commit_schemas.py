"""房间对局原子提交模型。"""

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from app.modules.strategy_turn.schemas import RuntimeSnapshot
from app.modules.strategy_turn.terminal_schemas import TerminalOwnerTransferPlan
from app.modules.room.post_turn_plan import PostTurnPlan

CommitResultStatus = Literal[
    "COMMITTED",
    "REPLAY",
    "VERSION_CONFLICT",
    "REQUEST_CONFLICT",
    "ROOM_NOT_FOUND",
]


class ActionRequestRecord(BaseModel):
    """房间动作请求幂等记录。"""

    model_config = ConfigDict(extra="forbid")

    roomId: str = Field(min_length=1)
    playerId: str = Field(min_length=1)
    requestId: str = Field(min_length=1, max_length=128)
    requestHash: str = Field(min_length=1)
    actionType: str = Field(min_length=1)
    committedGameVersion: int = Field(ge=0)
    resolvedActionId: str = Field(default="")
    createdAt: int = Field(ge=0)
    expiresAt: int = Field(ge=0)


class GameSettlementOutboxPayload(BaseModel):
    """GAME_SETTLEMENT Outbox 载荷。"""

    model_config = ConfigDict(extra="forbid")

    roomId: str = Field(min_length=1)
    gameVersion: int = Field(ge=0)
    settlementId: Optional[str] = Field(default=None)
    gameCode: str = Field(default="")


class TerminalFinalizeOutboxPayload(BaseModel):
    """TERMINAL_FINALIZE Outbox 载荷。"""

    model_config = ConfigDict(extra="forbid")

    roomId: str = Field(min_length=1)
    gameVersion: int = Field(ge=0)
    dissolveAfterTerminal: bool = Field(default=False)
    memberIdsToRemove: List[str] = Field(default_factory=list)
    ownerTransferPlan: Optional[TerminalOwnerTransferPlan] = Field(default=None)
    finalizedAt: int = Field(ge=0)


OutboxTaskPayload = Union[PostTurnPlan, GameSettlementOutboxPayload, TerminalFinalizeOutboxPayload]


class PostTurnOutboxRecord(BaseModel):
    """回合后任务 Outbox 记录。"""

    model_config = ConfigDict(extra="forbid")

    outboxId: str = Field(min_length=1)
    roomId: str = Field(min_length=1)
    sourceCommitId: str = Field(min_length=1)
    sourceVersion: int = Field(ge=0)
    taskType: str = Field(min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)
    status: Literal["PENDING", "PROCESSING", "RECOVERING", "DONE", "DISCARDED", "FAILED"] = "PENDING"
    attemptCount: int = Field(default=0, ge=0)
    retryCount: int = Field(default=0, ge=0)
    recoveryCount: int = Field(default=0, ge=0)
    availableAt: int = Field(ge=0)
    nextAttemptAt: Optional[int] = Field(default=None, ge=0)
    leaseUntil: Optional[int] = Field(default=None, ge=0)
    lastFailureCode: Optional[str] = None
    lastFailureReason: Optional[str] = None
    createdAt: int = Field(ge=0)
    updatedAt: int = Field(ge=0)
    dedupeKey: Optional[str] = Field(default=None, description="roomId+version+taskType 幂等键")

class RoomGameCommit(BaseModel):
    """房间对局状态原子提交意图。"""

    model_config = ConfigDict(extra="forbid")

    roomId: str = Field(min_length=1)
    expectedGameVersion: int = Field(ge=0)
    nextGameVersion: int = Field(ge=0)
    expectedRoomVersion: Optional[int] = Field(default=None, ge=0)
    nextRoomVersion: Optional[int] = Field(default=None, ge=0)
    nextRuntimeSnapshot: Optional[RuntimeSnapshot] = None
    deleteRuntime: bool = False
    nextRoomMeta: Optional[Dict[str, Any]] = None
    memberUpserts: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    memberDeletes: List[str] = Field(default_factory=list)
    requestRecord: Optional[ActionRequestRecord] = None
    outboxRecords: List[PostTurnOutboxRecord] = Field(default_factory=list)
    ttlSeconds: int = Field(default=86400, ge=1)
    commitId: str = Field(min_length=1)
    committedAt: int = Field(ge=0)


class RoomGameCommitResult(BaseModel):
    """房间对局原子提交结果。"""

    model_config = ConfigDict(extra="forbid")

    status: CommitResultStatus
    committedVersion: Optional[int] = Field(default=None, ge=0)
    currentVersion: Optional[int] = Field(default=None, ge=0)
