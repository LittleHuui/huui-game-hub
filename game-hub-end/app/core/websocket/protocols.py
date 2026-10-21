"""WebSocket 实时通道端口协议定义。"""

from typing import Dict, Optional, Protocol, runtime_checkable

from app.core.auth.schemas import AuthenticatedUser
from app.core.websocket.schemas import RealtimeHandlerResult, RealtimeMessage


@runtime_checkable
class AuthenticationPort(Protocol):
    """实时通道连接认证端口。"""

    async def authenticate_ticket(self, ticket: str) -> Optional[AuthenticatedUser]:
        """消费一次性 WebSocket Ticket 并返回认证主体。"""
        ...


@runtime_checkable
class RealtimeMessageHandler(Protocol):
    """通用实时消息 Handler 端口。"""

    async def handle(self, service_id: str, message: RealtimeMessage) -> Optional[RealtimeHandlerResult]:
        """处理一条实时消息。"""
        ...


@runtime_checkable
class RoomInvitationHandler(Protocol):
    """房间邀请实时 Handler 端口。"""

    async def handle(self, sender_service_id: str, payload: Dict[str, object], request_id: Optional[str]) -> RealtimeHandlerResult:
        """处理房间邀请请求。"""
        ...


@runtime_checkable
class PresenceMessageHandler(Protocol):
    """房间探活 Pong Handler 端口。"""

    async def handle(self, user_service_id: str, payload: Dict[str, object]) -> None:
        """处理房间探活 pong 消息。"""
        ...
