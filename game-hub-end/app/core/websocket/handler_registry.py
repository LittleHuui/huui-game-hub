"""WebSocket 实时 Handler 注册表。"""

from dataclasses import dataclass
from typing import Optional

from app.core.websocket.protocols import PresenceMessageHandler, RoomInvitationHandler


@dataclass
class RealtimeHandlerRegistry:
    """平台实时通道已注册的 Handler 集合。"""

    room_invitation_handler: Optional[RoomInvitationHandler] = None
    presence_handler: Optional[PresenceMessageHandler] = None


_registry = RealtimeHandlerRegistry()


def bind_realtime_handlers(registry: RealtimeHandlerRegistry) -> None:
    """
    绑定实时通道业务 Handler 到注册表。

    :param registry: Handler 注册表。
    :return: 无。
    """
    global _registry
    _registry = registry


def get_realtime_handlers() -> RealtimeHandlerRegistry:
    """
    获取当前绑定的实时通道 Handler 注册表。

    :return: Handler 注册表。
    """
    return _registry
