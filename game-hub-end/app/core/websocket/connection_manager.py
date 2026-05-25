"""WebSocket 连接管理。"""

from typing import Any, Dict

from fastapi import WebSocket

from app.core.time_utils import now_ms
from app.core.websocket.message_types import MessageType


class ConnectionManager(object):
    """按 serviceId 管理平台实时连接。"""

    def __init__(self) -> None:
        """初始化连接容器。"""
        self._connections: Dict[str, WebSocket] = {}

    async def connect(self, service_id: str, websocket: WebSocket) -> None:
        """
        接受并登记用户连接。

        :param service_id: 用户服务端 ID。
        :param websocket: WebSocket 连接。
        :return: 无。
        """
        await websocket.accept()
        self._connections[service_id] = websocket

    def disconnect(self, service_id: str, websocket: WebSocket) -> None:
        """
        清理断开的用户连接。

        :param service_id: 用户服务端 ID。
        :param websocket: WebSocket 连接。
        :return: 无。
        """
        if self._connections.get(service_id) is websocket:
            self._connections.pop(service_id, None)

    async def send_to_user(self, service_id: str, message_type: MessageType, payload: Dict[str, Any]) -> bool:
        """
        向指定用户发送消息。

        :param service_id: 用户服务端 ID。
        :param message_type: 消息类型。
        :param payload: 消息载荷。
        :return: 是否发送成功。
        """
        websocket = self._connections.get(service_id)
        if websocket is None:
            return False
        await websocket.send_json(self._build_message(message_type, payload))
        return True

    async def broadcast(self, message_type: MessageType, payload: Dict[str, Any]) -> None:
        """
        广播消息到所有当前连接。

        :param message_type: 消息类型。
        :param payload: 消息载荷。
        :return: 无。
        """
        dead_service_ids = []
        for service_id, websocket in self._connections.items():
            try:
                await websocket.send_json(self._build_message(message_type, payload))
            except RuntimeError:
                dead_service_ids.append(service_id)
        for service_id in dead_service_ids:
            self._connections.pop(service_id, None)

    def _build_message(self, message_type: MessageType, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        构造统一消息对象。

        :param message_type: 消息类型。
        :param payload: 消息载荷。
        :return: 可序列化消息。
        """
        return {
            "type": message_type.value,
            "requestId": None,
            "payload": payload,
            "timestamp": now_ms(),
        }


connection_manager = ConnectionManager()
