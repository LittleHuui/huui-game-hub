"""Room 聚合原子变更模型。"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class RoomMemberUpsert(BaseModel):
    """Room 聚合中的成员写入意图。"""

    model_config = ConfigDict(extra="forbid")

    playerId: str = Field(min_length=1)
    member: Dict[str, Any]


class RoomMutationCommit(BaseModel):
    """Room 聚合原子提交意图。"""

    model_config = ConfigDict(extra="forbid")

    roomId: str = Field(min_length=1)
    expectedRoomVersion: int = Field(ge=-1)
    nextRoomVersion: int = Field(ge=0)
    nextMeta: Dict[str, Any]
    memberUpserts: List[RoomMemberUpsert] = Field(default_factory=list)
    memberDeletes: List[str] = Field(default_factory=list)
    ownerChange: Optional[Dict[str, str]] = None
    ttlSeconds: int = Field(default=86400, ge=1)
    commitId: str = Field(min_length=1)
    deleteRoom: bool = False
    claimPlayerId: Optional[str] = Field(default=None, min_length=1)


class RoomMutationCommitResult(BaseModel):
    """Room 聚合原子提交结果。"""

    model_config = ConfigDict(extra="forbid")

    status: Literal["COMMITTED", "VERSION_CONFLICT", "ROOM_NOT_FOUND", "PLAYER_ALREADY_IN_ROOM"]
    committedRoomVersion: Optional[int] = Field(default=None, ge=0)
    currentRoomVersion: Optional[int] = Field(default=None, ge=0)
