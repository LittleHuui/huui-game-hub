"""实时通道组合根装配。"""

from app.core.websocket.handler_registry import RealtimeHandlerRegistry, bind_realtime_handlers
from app.modules.room.presence_service import RoomPresenceService
from app.modules.room.repository import RoomRepository
from app.realtime.room_invitation_realtime_handler import (
    RoomInvitationRealtimeHandler,
)
from app.realtime.room_presence_realtime_handler import (
    RoomPresenceRealtimeHandler,
)


def initialize_realtime_handlers(
    repository: RoomRepository,
    presence_service: RoomPresenceService,
) -> None:
    """
    在应用组合根绑定实时通道业务 Handler。

    :param repository: 房间 Redis 仓库。
    :param presence_service: 房间探活服务。
    :return: 无。
    """
    bind_realtime_handlers(
        RealtimeHandlerRegistry(
            room_invitation_handler=RoomInvitationRealtimeHandler(repository),
            presence_handler=RoomPresenceRealtimeHandler(presence_service),
        ),
    )
