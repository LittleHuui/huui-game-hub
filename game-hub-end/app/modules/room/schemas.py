"""房间模块 Pydantic 模型。"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.strategy_turn.schemas import GameView

RoomStatus = Literal["waiting", "playing"]


class CreateRoomRequest(BaseModel):
    """创建房间请求。"""

    model_config = ConfigDict(extra="forbid")

    gameCode: str = Field(min_length=1, description="游戏编码")
    mode: str = Field(min_length=1, description="玩法模式")
    expireSeconds: Optional[int] = Field(default=None, ge=1, description="房间 Redis TTL（秒）")
    roomName: Optional[str] = Field(default=None, description="房间展示名称")
    roomConfig: Optional[Dict[str, Any]] = Field(default=None, description="房间玩法配置覆盖项")


class RemoveRoomMemberRequest(BaseModel):
    """房主移除房间成员请求。"""

    model_config = ConfigDict(extra="forbid")

    targetPlayerId: str = Field(min_length=1, description="被移除成员玩家 ID")


class UpdateRoomConfigRequest(BaseModel):
    """房主更新 waiting 房间配置；支持 maxPlayers 与 roomConfig 覆盖项。"""

    model_config = ConfigDict(extra="forbid")

    maxPlayers: Optional[int] = Field(default=None, ge=2, description="房间人数上限")
    roomConfig: Optional[Dict[str, Any]] = Field(default=None, description="房间玩法配置覆盖项")


class RoomListItemResponse(BaseModel):
    """房间列表项响应。"""

    model_config = ConfigDict(extra="forbid")

    roomId: str
    roomName: str
    ownerPlayerId: str
    ownerNickname: str
    memberCount: int
    maxPlayers: int
    aiCount: int
    status: RoomStatus
    gameCode: str
    mode: str


class RoomMemberResponse(BaseModel):
    """房间成员响应项。"""

    model_config = ConfigDict(extra="forbid")

    playerId: str
    nickname: str
    avatar: Optional[str] = None
    joinedAt: int
    isAi: bool = Field(default=False, description="是否为 AI 玩家")
    isManaged: bool = Field(default=False, description="是否由托管策略接管")
    managedMode: Optional[Literal["active", "shell"]] = Field(
        default=None,
        description="托管模式（active=在线托管，shell=空壳托管）",
    )
    managedReason: Optional[Literal["manual", "leave", "timeout", "ai"]] = Field(
        default=None,
        description="托管原因",
    )
    managedAt: Optional[int] = Field(default=None, description="托管开始时间（毫秒）")


class RoomResponse(BaseModel):
    """房间详情响应（元信息 + 成员列表）。"""

    model_config = ConfigDict(extra="forbid")

    roomId: str
    roomName: str
    gameCode: str
    mode: str
    ownerPlayerId: str
    ownerNickname: str
    maxPlayers: int
    aiCount: int
    version: int
    status: RoomStatus
    memberCount: int
    members: List[RoomMemberResponse]
    roomConfig: Dict[str, Any] = Field(default_factory=dict, description="房间玩法配置")
    allowAi: bool = Field(default=True, description="是否允许 AI")
    maxAiCount: int = Field(default=0, ge=0, description="AI 数量上限")
    createdAt: int
    updatedAt: int


class MyActiveRoomResponse(BaseModel):
    """当前用户活跃房间查询响应。"""

    model_config = ConfigDict(extra="forbid")

    room: Optional[RoomResponse] = Field(default=None, description="活跃房间详情；无则 null")


class RoomActionRequest(BaseModel):
    """提交房间对局操作请求。"""

    model_config = ConfigDict(extra="forbid")

    actionId: str = Field(min_length=1, description="合法操作 ID")
    baseVersion: int = Field(ge=0, description="客户端已知房间版本号")
    clientSeq: Optional[int] = Field(
        default=None,
        ge=0,
        description="客户端操作序号，用于事件追踪与客户端关联",
    )


class RoomLeaveResponse(BaseModel):
    """离开房间响应。"""

    model_config = ConfigDict(extra="forbid")

    roomId: str
    gameCode: str
    dissolved: bool = Field(description="房间是否已解散")
    room: Optional[RoomResponse] = Field(default=None, description="房间仍存在时的详情")


RoomGameViewResponse = GameView
