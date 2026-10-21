"""WebSocket 消息模型。"""

from dataclasses import dataclass
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class RealtimeMessage(BaseModel):
    """平台实时通道统一消息结构。"""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1, description="消息类型")
    requestId: Optional[str] = Field(default=None, description="请求 ID")
    payload: Dict[str, object] = Field(default_factory=dict, description="消息载荷")
    timestamp: int = Field(description="毫秒时间戳")


@dataclass(frozen=True)
class RealtimeHandlerResult:
    """实时业务 Handler 标准返回，供 Dispatcher 发送。"""

    error_message: Optional[str] = None
    forward_service_id: Optional[str] = None
    forward_payload: Optional[Dict[str, str]] = None
    offline_error_message: Optional[str] = None


class RoomInviteClientPayload(BaseModel):
    """客户端 ROOM_INVITE 请求载荷（仅允许 roomId 与 targetServiceId）。"""

    model_config = ConfigDict(extra="forbid")

    roomId: str = Field(min_length=1, description="房间 ID")
    targetServiceId: str = Field(min_length=1, description="被邀请用户 serviceId")


class RoomInviteForwardPayload(BaseModel):
    """服务端权威 ROOM_INVITE 转发载荷。"""

    model_config = ConfigDict(extra="forbid")

    roomId: str = Field(min_length=1, description="房间 ID")
    roomName: str = Field(min_length=1, description="房间展示名称")
    gameCode: str = Field(min_length=1, description="游戏编码")
    inviterPlayerId: str = Field(min_length=1, description="邀请方玩家 ID")
    inviterNickname: str = Field(min_length=1, description="邀请方昵称")
