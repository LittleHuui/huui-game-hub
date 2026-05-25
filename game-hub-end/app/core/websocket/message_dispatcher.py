"""平台 WebSocket 消息分发。"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.time_utils import now_ms
from app.core.websocket.connection_manager import connection_manager
from app.core.websocket.message_types import MessageType
from app.core.websocket.schemas import RealtimeMessage
from app.modules.user.entity_service import UserAccountEntityService
from app.modules.user.repository import UserAccountRepository

realtime_router = APIRouter()
logger = logging.getLogger(__name__)


@realtime_router.websocket("/ws/game-hub/realtime")
async def realtime_websocket(websocket: WebSocket, db: Session = Depends(get_db)) -> None:
    """
    平台唯一实时通道。

    :param websocket: WebSocket 连接。
    :param db: 请求级数据库会话。
    :return: 无。
    """
    service_id = websocket.query_params.get("serviceId")
    if not service_id:
        await websocket.close(code=1008)
        return
    if not _is_valid_service_id(service_id, db):
        await websocket.close(code=1008)
        return
    connected = False
    try:
        await connection_manager.connect(service_id, websocket)
        connected = True
        while True:
            data = await websocket.receive_json()
            await dispatch_message(service_id, websocket, data)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected, service_id=%s", service_id)
    except Exception:
        logger.exception("WebSocket realtime error, service_id=%s", service_id)
    finally:
        if connected:
            connection_manager.disconnect(service_id, websocket)


def _is_valid_service_id(service_id: str, db: Session) -> bool:
    """
    校验实时通道 serviceId 是否对应可用用户。

    :param service_id: 用户服务端 ID。
    :param db: 请求级数据库会话。
    :return: 是否允许建立 WebSocket 业务连接。
    """
    account_service = UserAccountEntityService(UserAccountRepository(db))
    account = account_service.get_by_server_id(service_id, active_only=True)
    if account is None:
        return False
    return account.status == "normal"


async def dispatch_message(service_id: str, websocket: WebSocket, data: Dict[str, Any]) -> None:
    """
    分发平台实时通道消息。

    :param service_id: 用户服务端 ID。
    :param websocket: WebSocket 连接。
    :param data: 原始消息对象。
    :return: 无。
    """
    try:
        message = RealtimeMessage.model_validate(data)
    except ValidationError:
        await send_error(websocket, None, "消息格式无效")
        return
    if message.type == MessageType.ONLINE_PING.value:
        await websocket.send_json(
            {
                "type": MessageType.ONLINE_PONG.value,
                "requestId": message.requestId,
                "payload": {"serviceId": service_id},
                "timestamp": now_ms(),
            }
        )
        return
    await send_error(websocket, message.requestId, "不支持的消息类型")


async def send_to_user(service_id: str, message_type: MessageType, payload: Dict[str, Any]) -> bool:
    """
    向指定用户发送实时消息。

    :param service_id: 用户服务端 ID。
    :param message_type: 消息类型。
    :param payload: 消息载荷。
    :return: 是否发送成功。
    """
    return await connection_manager.send_to_user(service_id, message_type, payload)


async def broadcast(message_type: MessageType, payload: Dict[str, Any]) -> None:
    """
    广播实时消息。

    :param message_type: 消息类型。
    :param payload: 消息载荷。
    :return: 无。
    """
    await connection_manager.broadcast(message_type, payload)


async def send_error(websocket: WebSocket, request_id: Optional[str], message: str) -> None:
    """
    发送错误消息。

    :param websocket: WebSocket 连接。
    :param request_id: 请求 ID。
    :param message: 错误说明。
    :return: 无。
    """
    await websocket.send_json(
        {
            "type": MessageType.ERROR.value,
            "requestId": request_id,
            "payload": {"message": message},
            "timestamp": now_ms(),
        }
    )
