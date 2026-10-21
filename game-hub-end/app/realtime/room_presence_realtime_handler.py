"""房间探活 Pong 实时 Handler 适配器。"""

from typing import Dict

from app.modules.room.presence_service import RoomPresenceService


class RoomPresenceRealtimeHandler:
    """将 ``RoomPresenceService`` 适配为探活 Pong Handler。"""

    def __init__(self, presence_service: RoomPresenceService) -> None:
        """
        初始化探活 Handler。

        :param presence_service: 房间探活服务。
        """
        self._presence_service = presence_service

    async def handle(
        self,
        user_service_id: str,
        payload: Dict[str, object],
    ) -> None:
        """
        将 pong 消息委托给房间探活服务。

        :param user_service_id: 当前连接用户 serviceId。
        :param payload: pong 载荷。
        :return: 无。
        """
        await self._presence_service.accept_pong(user_service_id, payload)
