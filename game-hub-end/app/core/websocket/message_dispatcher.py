"""平台 WebSocket 消息分发。"""

import logging
import uuid
from typing import Dict, Optional

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.common.exceptions import BizException
from app.core.auth.schemas import AuthenticatedUser
from app.core.time_utils import now_ms
from app.core.websocket.connection_manager import WS_CLOSE_AUTH_EXPIRED, WS_CLOSE_AUTH_INVALID, connection_manager
from app.core.websocket.handler_registry import get_realtime_handlers
from app.core.websocket.message_types import MessageType
from app.core.websocket.protocols import AuthenticationPort
from app.core.websocket.schemas import RealtimeHandlerResult, RealtimeMessage

logger = logging.getLogger(__name__)


def _extract_realtime_ticket(websocket: WebSocket) -> Optional[str]:
    """从 WebSocket 查询参数读取一次性 Ticket。"""
    ticket = websocket.query_params.get("ticket")
    if ticket and str(ticket).strip():
        return str(ticket).strip()
    return None


async def handle_realtime_connection(websocket: WebSocket, auth_port: AuthenticationPort) -> None:
    """处理平台实时 WebSocket 连接生命周期。"""
    ticket = _extract_realtime_ticket(websocket)
    if not ticket:
        await websocket.close(code=WS_CLOSE_AUTH_INVALID)
        return
    auth_user = await auth_port.authenticate_ticket(ticket)
    if auth_user is None:
        await websocket.close(code=WS_CLOSE_AUTH_INVALID)
        return
    if auth_user.expiresAt <= now_ms():
        await websocket.close(code=WS_CLOSE_AUTH_EXPIRED)
        return

    service_id = auth_user.serviceId
    connection_id = "conn_{0}".format(uuid.uuid4().hex)
    connected = False
    try:
        await connection_manager.connect(service_id, websocket, connection_id=connection_id)
        connected = True
        while True:
            if not await connection_manager.is_active_connection(service_id, websocket, connection_id=connection_id):
                break
            data = await websocket.receive_json()
            if not await connection_manager.is_active_connection(service_id, websocket, connection_id=connection_id):
                break
            await dispatch_message(auth_user, websocket, data)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected, service_id=%s", service_id)
    except Exception:
        logger.exception("WebSocket realtime error, service_id=%s", service_id)
    finally:
        if connected:
            await connection_manager.disconnect(service_id, websocket, connection_id=connection_id)


async def dispatch_message(auth_user: AuthenticatedUser, websocket: WebSocket, data: Dict[str, object]) -> None:
    """分发平台实时通道消息，身份始终来自连接上下文。"""
    service_id = auth_user.serviceId
    try:
        message = RealtimeMessage.model_validate(data)
    except ValidationError:
        await send_error(websocket, None, "消息格式无效")
        return
    if message.type == MessageType.ONLINE_PING.value:
        await connection_manager.refresh_connection(auth_user.serviceId, connection_id=None)
        await websocket.send_json({"type": MessageType.ONLINE_PONG.value, "requestId": message.requestId, "payload": {"serviceId": service_id}, "timestamp": now_ms()})
        return
    if message.type == MessageType.ROOM_INVITE.value:
        await _dispatch_room_invite(auth_user, websocket, message)
        return
    if message.type == MessageType.ROOM_PRESENCE_PONG.value:
        await _dispatch_presence_pong(service_id, message.payload)
        return
    await send_error(websocket, message.requestId, "不支持的消息类型")


async def _dispatch_room_invite(auth_user: AuthenticatedUser, websocket: WebSocket, message: RealtimeMessage) -> None:
    """路由房间邀请消息。"""
    sender_service_id = auth_user.serviceId
    registry = get_realtime_handlers()
    handler = registry.room_invitation_handler
    if handler is None:
        await send_error(websocket, message.requestId, "邀请服务不可用")
        return
    if not isinstance(message.payload, dict):
        await send_error(websocket, message.requestId, "邀请参数无效")
        return
    payload_sender = message.payload.get("senderServiceId") or message.payload.get("senderUserId")
    if payload_sender is not None and str(payload_sender).strip() and str(payload_sender).strip() != sender_service_id:
        await send_error(websocket, message.requestId, "邀请参数无效")
        return
    try:
        result = await handler.handle(sender_service_id, message.payload, message.requestId)
    except BizException as exc:
        await send_error(websocket, message.requestId, exc.message)
        return
    except Exception:
        logger.exception("room invite handler failed, sender=%s", sender_service_id)
        await send_error(websocket, message.requestId, "邀请发送失败")
        return
    await _send_handler_result(websocket, message.requestId, result)


async def _dispatch_presence_pong(service_id: str, payload: Dict[str, object]) -> None:
    """路由房间探活 pong 消息。"""
    registry = get_realtime_handlers()
    handler = registry.presence_handler
    if handler is None or not isinstance(payload, dict):
        return
    try:
        await handler.handle(service_id, payload)
    except Exception:
        logger.exception("presence pong handler failed, serviceId=%s", service_id)


async def _send_handler_result(websocket: WebSocket, request_id: Optional[str], result: RealtimeHandlerResult) -> None:
    """发送 Handler 处理结果。"""
    if result.error_message:
        await send_error(websocket, request_id, result.error_message)
        return
    if not result.forward_service_id:
        return
    sent = await send_to_user(result.forward_service_id, MessageType.ROOM_INVITE, result.forward_payload or {})
    if not sent:
        await send_error(websocket, request_id, result.offline_error_message or "被邀请用户不在线")


async def send_to_user(service_id: str, message_type: MessageType, payload: Dict[str, object]) -> bool:
    """向指定用户发送实时消息。"""
    return await connection_manager.send_to_user(service_id, message_type, payload)


async def broadcast(message_type: MessageType, payload: Dict[str, object]) -> None:
    """广播实时消息。"""
    await connection_manager.broadcast(message_type, payload)


async def send_error(websocket: WebSocket, request_id: Optional[str], message: str) -> None:
    """发送错误消息。"""
    await websocket.send_json({"type": MessageType.ERROR.value, "requestId": request_id, "payload": {"message": message}, "timestamp": now_ms()})
