"""实时通道 WebSocket 路由。"""

from fastapi import APIRouter, Depends, WebSocket

from app.core.websocket import message_dispatcher
from app.core.websocket.protocols import AuthenticationPort
from app.realtime.deps import get_authentication_port

realtime_router = APIRouter()


@realtime_router.websocket("/ws/game-hub/realtime")
async def realtime_websocket(
    websocket: WebSocket,
    auth_port: AuthenticationPort = Depends(get_authentication_port),
) -> None:
    """
    平台唯一实时通道。

    :param websocket: WebSocket 连接。
    :param auth_port: 实时通道认证端口。
    :return: 无。
    """
    await message_dispatcher.handle_realtime_connection(websocket, auth_port)
