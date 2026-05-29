"""房间对局探活服务。"""

import asyncio
import logging
from typing import Awaitable, Callable, Dict, List, Optional

from app.core.time_utils import now_ms
from app.core.websocket.message_types import MessageType
from app.modules.room.repository import RoomRepository
from app.core.websocket.connection_manager import connection_manager

logger = logging.getLogger(__name__)

PING_INTERVAL_MS = 6000
TIMEOUT_MISS_LIMIT = 3

SHELL_MANAGED_REASONS = frozenset({"timeout"})


class RoomPresenceService(object):
    """对局内玩家探活与断线判定。"""

    def __init__(self) -> None:
        """初始化探活服务。"""
        self._repository = RoomRepository()
        self._mark_member_shell_managed_handler = None  # type: Optional[Callable[[str, str, str], Awaitable[bool]]]
        self._running = False
        self._task = None  # type: Optional[asyncio.Task]

    def bind_mark_member_shell_managed_handler(
        self,
        handler: Callable[[str, str, str], Awaitable[bool]],
    ) -> None:
        """
        绑定成员 shell 托管处理函数。

        :param handler: ``mark_member_shell_managed(room_id, player_id, reason) -> bool``。
        :return: 无。
        """
        self._mark_member_shell_managed_handler = handler

    async def start(self) -> None:
        """
        启动后台探活循环。

        :return: 无。
        """
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """
        停止后台探活循环。

        :return: 无。
        """
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def accept_pong(self, service_id: str, payload: Dict[str, object]) -> None:
        """
        处理客户端 room presence pong。

        :param service_id: 当前连接用户 serviceId。
        :param payload: pong 载荷。
        :return: 无。
        """
        room_id = str(payload.get("roomId", "")).strip()
        game_code = str(payload.get("gameCode", "")).strip()
        sequence = int(payload.get("sequence", 0) or 0)
        if not room_id or not game_code or sequence <= 0:
            return
        meta = await self._repository.get_meta(room_id)
        if meta is None:
            return
        if str(meta.get("gameCode", "")).strip() != game_code:
            return
        state = await self._repository.get_presence_state(room_id, service_id)
        if state is None:
            return
        expected_sequence = int(state.get("sequence", 0) or 0)
        if expected_sequence <= 0:
            return
        if sequence != expected_sequence:
            return
        current_time = now_ms()
        state["missedCount"] = 0
        state["lastPongAt"] = current_time
        state["lastAckSequence"] = sequence
        await self._repository.save_presence_state(room_id, service_id, state)

    async def _run_loop(self) -> None:
        """
        后台循环：扫描 playing 房间并发送 ping。

        :return: 无。
        """
        while self._running:
            try:
                await self._tick_once()
            except Exception:
                logger.exception("room presence tick failed")
            await asyncio.sleep(PING_INTERVAL_MS / 1000.0)

    async def _tick_once(self) -> None:
        """
        执行一次探活扫描。

        :return: 无。
        """
        room_ids = await self._list_playing_room_ids()
        for room_id in room_ids:
            await self._tick_room(room_id)

    async def _list_playing_room_ids(self) -> List[str]:
        """
        读取有效 playing 房间 ID 列表。

        :return: 房间 ID 列表。
        """
        room_ids = await self._repository.list_playing_room_ids()
        valid_room_ids = []
        for room_id in room_ids:
            meta = await self._repository.get_meta(room_id)
            if meta is None or str(meta.get("status", "")).strip() != "playing":
                await self._repository.remove_playing_room(room_id)
                continue
            valid_room_ids.append(room_id)
        return valid_room_ids

    async def _tick_room(self, room_id: str) -> None:
        """
        对单个房间执行探活 ping 与超时判定。

        :param room_id: 房间 ID。
        :return: 无。
        """
        members = await self._repository.list_players(room_id)
        meta = await self._repository.get_meta(room_id)
        if meta is None or str(meta.get("status", "")).strip() != "playing":
            await self._repository.delete_presence(room_id)
            return
        game_code = str(meta.get("gameCode", "")).strip()
        current_time = now_ms()
        for member in members:
            if bool(member.get("isAi")):
                continue
            if str(member.get("managedMode", "")).strip() == "shell":
                continue
            player_id = str(member.get("playerId", "")).strip()
            if not player_id:
                continue
            state = await self._repository.get_presence_state(room_id, player_id)
            if state is None:
                state = {}
            sequence = int(state.get("sequence", 0) or 0) + 1
            missed = int(state.get("missedCount", 0) or 0) + 1
            state["sequence"] = sequence
            state["missedCount"] = missed
            state["lastPingAt"] = current_time
            await self._repository.save_presence_state(room_id, player_id, state)
            await connection_manager.send_to_user(
                player_id,
                MessageType.ROOM_PRESENCE_PING,
                {
                    "roomId": room_id,
                    "gameCode": game_code,
                    "sequence": sequence,
                    "sentAt": current_time,
                },
            )
            if missed >= TIMEOUT_MISS_LIMIT:
                marked = await self._notify_shell_managed(room_id, player_id, "timeout")
                if marked:
                    await self._repository.delete_presence_state(room_id, player_id)
                else:
                    logger.warning(
                        "presence shell mark failed, keep state, roomId=%s playerId=%s missed=%s",
                        room_id,
                        player_id,
                        missed,
                    )

    async def _notify_shell_managed(self, room_id: str, player_id: str, reason: str) -> bool:
        """
        调用房间模块 shell 托管处理函数。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param reason: 托管原因。
        :return: 是否成功标记或房间已无需处理。
        """
        normalized_reason = str(reason or "").strip()
        if normalized_reason not in SHELL_MANAGED_REASONS:
            return True
        handler = self._mark_member_shell_managed_handler
        if handler is None:
            logger.warning(
                "presence shell handler not bound, roomId=%s playerId=%s",
                room_id,
                player_id,
            )
            return False
        return bool(await handler(room_id, player_id, normalized_reason))


room_presence_service = RoomPresenceService()
