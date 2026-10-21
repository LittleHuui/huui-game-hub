"""WebSocket 连接管理。"""

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import WebSocket

from app.core.time_utils import now_ms
from app.core.redis.redis_client import RedisClient, redis_client
from app.core.redis.redis_keys import RedisKeys
from app.core.websocket.message_types import MessageType

logger = logging.getLogger(__name__)

_WS_CLOSE_REPLACED = 4001
_WS_CLOSE_AUTH_INVALID = 1008
_WS_CLOSE_AUTH_EXPIRED = 4003
_CONNECTION_REGISTRATION_TTL_SECONDS = 180

_CLAIM_CONNECTION_LUA = """
local previous = redis.call('GET', KEYS[1])
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
return previous or ''
"""

_RELEASE_CONNECTION_LUA = """
local current = redis.call('GET', KEYS[1])
if not current then return 0 end
local currentData = cjson.decode(current)
if currentData.nodeId == ARGV[1] and currentData.connectionId == ARGV[2] then
  redis.call('DEL', KEYS[1])
  return 1
end
return 0
"""

_REFRESH_CONNECTION_LUA = """
local current = redis.call('GET', KEYS[1])
if not current then return 0 end
local currentData = cjson.decode(current)
if currentData.nodeId == ARGV[1] and currentData.connectionId == ARGV[2] then
  redis.call('EXPIRE', KEYS[1], ARGV[3])
  return 1
end
return 0
"""


class ConnectionManager:
    """按 serviceId 管理平台实时连接（单活动连接）。"""

    def __init__(self, redis: RedisClient = redis_client, node_id: Optional[str] = None) -> None:
        """初始化由 Redis 协调的实时连接容器。"""
        self._connections: Dict[str, WebSocket] = {}
        self._connection_ids: Dict[str, str] = {}
        self._redis = redis
        self._node_id = str(node_id or "ws-node-{0}".format(uuid.uuid4().hex)).strip()
        self._subscription = None  # type: Optional[Any]
        self._listener_task = None  # type: Optional[asyncio.Task]
        self._running = False

    async def start(self) -> None:
        """启动 Redis 跨进程消息订阅。"""
        if self._running:
            return
        self._subscription = await self._redis.subscribe_json(RedisKeys.websocket_events())
        self._running = True
        self._listener_task = asyncio.create_task(self._listen_events())

    async def stop(self) -> None:
        """停止 Redis 跨进程消息订阅并释放本进程连接登记。"""
        self._running = False
        if self._listener_task is not None:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        if self._subscription is not None:
            try:
                await self._subscription.unsubscribe(RedisKeys.websocket_events())
                await self._subscription.aclose()
            except Exception:
                logger.exception("close websocket redis subscription failed")
            self._subscription = None
        registrations = list(self._connection_ids.items())
        self._connections.clear()
        self._connection_ids.clear()
        for service_id, connection_id in registrations:
            await self._release_registration(service_id, connection_id)

    async def connect(
        self,
        service_id: str,
        websocket: WebSocket,
        *,
        connection_id: str,
    ) -> Optional[WebSocket]:
        """
        接受并登记用户连接；若已有活跃连接则关闭旧连接。

        :param service_id: 用户服务端 ID。
        :param websocket: WebSocket 连接。
        :param connection_id: 本次连接唯一 ID。
        :return: 被替换的旧连接；无则 ``None``。
        """
        await self.start()
        await websocket.accept()
        previous = await self._claim_registration(service_id, connection_id)
        old_socket = self._connections.get(service_id)
        if old_socket is not None and old_socket is not websocket:
            await self._close_replaced_connection(service_id, old_socket)
        self._connections[service_id] = websocket
        self._connection_ids[service_id] = connection_id
        if previous is not None and previous.get("nodeId") != self._node_id:
            await self._publish_event(
                {
                    "kind": "replace",
                    "targetNodeId": previous.get("nodeId"),
                    "serviceId": service_id,
                    "connectionId": previous.get("connectionId"),
                },
            )
        return old_socket if old_socket is not websocket else None

    async def disconnect(self, service_id: str, websocket: WebSocket, *, connection_id: Optional[str] = None) -> bool:
        """
        清理断开的用户连接。

        :param service_id: 用户服务端 ID。
        :param websocket: WebSocket 连接。
        :param connection_id: 连接 ID，用于避免误删新连接。
        :return: 是否移除了当前活跃连接。
        """
        active = self._connections.get(service_id)
        if active is not websocket:
            return False
        if connection_id is not None and self._connection_ids.get(service_id) != connection_id:
            return False
        self._connections.pop(service_id, None)
        self._connection_ids.pop(service_id, None)
        if connection_id is not None and self._running:
            await self._release_registration(service_id, connection_id)
        return True

    async def refresh_connection(self, service_id: str, connection_id: Optional[str] = None) -> bool:
        """刷新当前本地有效连接的 Redis 登记有效期。"""
        if not self._running:
            return False
        active_connection_id = connection_id or self._connection_ids.get(service_id)
        if not active_connection_id or service_id not in self._connections:
            return False
        result = await self._redis.eval_raw(
            _REFRESH_CONNECTION_LUA,
            1,
            [RedisKeys.websocket_connection(service_id)],
            [
                self._node_id,
                active_connection_id,
                str(_CONNECTION_REGISTRATION_TTL_SECONDS),
            ],
        )
        return bool(int(result or 0))

    async def is_active_connection(self, service_id: str, websocket: WebSocket, *, connection_id: str) -> bool:
        """
        判断给定连接是否仍为该用户的活跃连接。

        :param service_id: 用户服务端 ID。
        :param websocket: WebSocket 连接。
        :param connection_id: 连接 ID。
        :return: 是否仍为活跃连接。
        """
        if self._connections.get(service_id) is not websocket:
            return False
        if self._connection_ids.get(service_id) != connection_id:
            return False
        if not self._running:
            return True
        registration = await self._redis.get_json(RedisKeys.websocket_connection(service_id))
        return self._matches_registration(registration, connection_id)

    async def send_to_user(
        self,
        service_id: str,
        message_type: MessageType,
        payload: Dict[str, object],
    ) -> bool:
        """
        向指定用户发送消息。

        :param service_id: 用户服务端 ID。
        :param message_type: 消息类型。
        :param payload: 消息载荷。
        :return: 是否发送成功。
        """
        websocket = self._connections.get(service_id)
        if websocket is None:
            return await self._send_to_remote_connection(service_id, message_type, payload)
        try:
            await websocket.send_json(self._build_message(message_type, payload))
        except Exception as exc:
            logger.warning(
                "websocket send failed, serviceId=%s messageType=%s error=%s",
                service_id,
                message_type.value,
                exc,
            )
            if self._connections.get(service_id) is websocket:
                await self.disconnect(
                    service_id,
                    websocket,
                    connection_id=self._connection_ids.get(service_id),
                )
            return False
        return True

    async def broadcast(
        self,
        message_type: MessageType,
        payload: Dict[str, object],
    ) -> None:
        """
        广播消息到所有当前连接。

        :param message_type: 消息类型。
        :param payload: 消息载荷。
        :return: 无。
        """
        for service_id in list(self._connections.keys()):
            await self.send_to_user(service_id, message_type, payload)
        if self._running:
            await self._publish_event(
                {
                    "kind": "broadcast",
                    "messageType": message_type.value,
                    "payload": payload,
                },
            )

    async def _claim_registration(self, service_id: str, connection_id: str) -> Optional[Dict[str, str]]:
        """原子登记连接并返回被替换的连接登记。"""
        registration = {"nodeId": self._node_id, "connectionId": connection_id}
        raw = await self._redis.eval_raw(
            _CLAIM_CONNECTION_LUA,
            1,
            [RedisKeys.websocket_connection(service_id)],
            [
                json.dumps(registration, separators=(",", ":")),
                str(_CONNECTION_REGISTRATION_TTL_SECONDS),
            ],
        )
        if raw is None:
            raise RuntimeError("websocket connection registration failed")
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        if not raw:
            return None
        try:
            previous = json.loads(raw)
            if isinstance(previous, dict):
                return previous
        except (TypeError, ValueError):
            logger.warning("invalid websocket connection registration, serviceId=%s", service_id)
        return None

    async def _release_registration(self, service_id: str, connection_id: str) -> None:
        """条件删除仍属于本连接的 Redis 登记。"""
        await self._redis.eval_raw(
            _RELEASE_CONNECTION_LUA,
            1,
            [RedisKeys.websocket_connection(service_id)],
            [self._node_id, connection_id],
        )

    async def _send_to_remote_connection(
        self,
        service_id: str,
        message_type: MessageType,
        payload: Dict[str, object],
    ) -> bool:
        """向 Redis 登记的其他进程连接投递定向消息。"""
        if not self._running:
            return False
        registration = await self._redis.get_json(RedisKeys.websocket_connection(service_id))
        connection_id = registration.get("connectionId") if isinstance(registration, dict) else None
        if not connection_id:
            return False
        return bool(
            await self._publish_event(
                {
                    "kind": "deliver",
                    "serviceId": service_id,
                    "connectionId": connection_id,
                    "messageType": message_type.value,
                    "payload": payload,
                },
            ),
        )

    async def _publish_event(self, payload: Dict[str, object]) -> int:
        """发布带来源节点标识的跨进程实时事件。"""
        event = dict(payload)
        event["originNodeId"] = self._node_id
        return await self._redis.publish_json(RedisKeys.websocket_events(), event)

    async def _listen_events(self) -> None:
        """消费 Redis 广播并仅投递本节点持有的连接。"""
        while self._running and self._subscription is not None:
            try:
                raw_message = await self._subscription.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if not raw_message:
                    continue
                raw_data = raw_message.get("data") if isinstance(raw_message, dict) else None
                if isinstance(raw_data, bytes):
                    raw_data = raw_data.decode("utf-8")
                event = json.loads(raw_data) if isinstance(raw_data, str) else None
                if not isinstance(event, dict) or event.get("originNodeId") == self._node_id:
                    continue
                await self._handle_remote_event(event)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("websocket redis event handling failed")

    async def _handle_remote_event(self, event: Dict[str, object]) -> None:
        """处理连接替换、定向投递和全员广播事件。"""
        kind = str(event.get("kind", "")).strip()
        if kind == "replace":
            if event.get("targetNodeId") != self._node_id:
                return
            service_id = str(event.get("serviceId", "")).strip()
            connection_id = str(event.get("connectionId", "")).strip()
            websocket = self._connections.get(service_id)
            if websocket is not None and self._connection_ids.get(service_id) == connection_id:
                await self._close_replaced_connection(service_id, websocket)
            return
        if kind == "deliver":
            await self._send_local_event(event)
            return
        if kind == "broadcast":
            for service_id in list(self._connections.keys()):
                await self._send_local_event(dict(event, serviceId=service_id))

    async def _send_local_event(self, event: Dict[str, object]) -> None:
        """将跨进程事件投递给本节点当前有效连接。"""
        service_id = str(event.get("serviceId", "")).strip()
        connection_id = event.get("connectionId")
        websocket = self._connections.get(service_id)
        if websocket is None:
            return
        if connection_id and self._connection_ids.get(service_id) != connection_id:
            return
        try:
            message_type = MessageType(str(event.get("messageType", "")))
        except ValueError:
            return
        await self.send_to_user(service_id, message_type, event.get("payload") if isinstance(event.get("payload"), dict) else {})

    async def _close_replaced_connection(self, service_id: str, websocket: WebSocket) -> None:
        """关闭被替换的本地连接并保留当前 Redis 登记。"""
        connection_id = self._connection_ids.get(service_id)
        try:
            await websocket.close(code=_WS_CLOSE_REPLACED, reason="replaced_by_new_connection")
        except Exception as exc:
            logger.info("close replaced websocket failed, serviceId=%s error=%s", service_id, exc)
        if self._connections.get(service_id) is websocket:
            self._connections.pop(service_id, None)
            self._connection_ids.pop(service_id, None)
        if connection_id:
            await self._release_registration(service_id, connection_id)

    def _matches_registration(self, registration: object, connection_id: str) -> bool:
        """判断 Redis 登记是否属于当前节点和给定连接。"""
        return isinstance(registration, dict) and (
            registration.get("nodeId") == self._node_id
            and registration.get("connectionId") == connection_id
        )

    def _build_message(
        self,
        message_type: MessageType,
        payload: Dict[str, object],
    ) -> Dict[str, object]:
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

WS_CLOSE_REPLACED = _WS_CLOSE_REPLACED
WS_CLOSE_AUTH_INVALID = _WS_CLOSE_AUTH_INVALID
WS_CLOSE_AUTH_EXPIRED = _WS_CLOSE_AUTH_EXPIRED
