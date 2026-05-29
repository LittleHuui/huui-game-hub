"""房间版本校验与 WebSocket 发送隔离测试。"""

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import WebSocket

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.websocket import message_dispatcher
from app.core.websocket.connection_manager import ConnectionManager
from app.core.websocket.message_types import MessageType
from app.modules.room.module_service import RoomModuleService
from app.modules.room.presence_service import RoomPresenceService
from app.modules.room.schemas import RoomActionRequest


class _FakeLock(object):
    """异步锁占位。"""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


def _build_room_service_for_version_check(get_version_value):
    service = RoomModuleService(
        repository=MagicMock(),
        lock_service=MagicMock(),
        game_service=MagicMock(),
        runtime_service=MagicMock(),
        account_service=MagicMock(),
        managed_task_service=MagicMock(),
        managed_action_selector=MagicMock(),
    )
    service._repository.get_version = AsyncMock(return_value=get_version_value)
    service._require_meta = AsyncMock(return_value={"status": "playing"})
    service._require_playing_room = MagicMock()
    service._repository.list_players = AsyncMock(
        return_value=[{"playerId": "u1", "isManaged": False}],
    )

    async def _fake_acquire(*_args, **_kwargs):
        return _FakeLock()

    service._acquire_user_room_lock = _fake_acquire
    return service


@pytest.mark.asyncio
async def test_base_version_lower_than_current_rejected() -> None:
    """baseVersion 小于当前版本被拒绝。"""
    service = _build_room_service_for_version_check(5)
    account = MagicMock()
    account.server_id = "u1"
    request = RoomActionRequest(actionId="draw", baseVersion=4, clientSeq=1)
    with pytest.raises(BizException) as exc_info:
        await service.apply_room_action(account, "room-1", request)
    assert exc_info.value.code == ErrorCode.GAME_VIEW_VERSION_CONFLICT.code


@pytest.mark.asyncio
async def test_base_version_higher_than_current_rejected() -> None:
    """baseVersion 大于当前版本被拒绝。"""
    service = _build_room_service_for_version_check(5)
    account = MagicMock()
    account.server_id = "u1"
    request = RoomActionRequest(actionId="draw", baseVersion=999999, clientSeq=1)
    with pytest.raises(BizException) as exc_info:
        await service.apply_room_action(account, "room-1", request)
    assert exc_info.value.code == ErrorCode.GAME_VIEW_VERSION_CONFLICT.code


@pytest.mark.asyncio
async def test_base_version_equal_current_allowed() -> None:
    """baseVersion 等于当前版本时进入提交流程。"""
    service = _build_room_service_for_version_check(5)
    service._submit_action_locked = AsyncMock(return_value={"version": 6})
    account = MagicMock()
    account.server_id = "u1"
    request = RoomActionRequest(actionId="draw", baseVersion=5, clientSeq=1)
    result = await service.apply_room_action(account, "room-1", request)
    assert result == {"version": 6}
    service._submit_action_locked.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_to_user_send_failure_returns_false() -> None:
    """send_json 异常返回 false，不向上传播。"""
    manager = ConnectionManager()
    websocket = MagicMock(spec=WebSocket)
    websocket.send_json = AsyncMock(side_effect=RuntimeError("connection closed"))
    manager._connections["u1"] = websocket
    sent = await manager.send_to_user("u1", MessageType.ROOM_UPDATED, {"roomId": "r1"})
    assert sent is False


@pytest.mark.asyncio
async def test_send_to_user_failure_only_removes_active_connection() -> None:
    """发送失败只清理当前活跃连接，不误删新连接。"""
    manager = ConnectionManager()
    old_socket = MagicMock(spec=WebSocket)
    new_socket = MagicMock(spec=WebSocket)
    old_socket.send_json = AsyncMock(side_effect=RuntimeError("stale"))
    new_socket.send_json = AsyncMock()
    manager._connections["u1"] = old_socket
    await manager.send_to_user("u1", MessageType.ROOM_UPDATED, {})
    manager._connections["u1"] = new_socket
    sent = await manager.send_to_user("u1", MessageType.ROOM_UPDATED, {})
    assert sent is True
    assert manager._connections["u1"] is new_socket


@pytest.mark.asyncio
async def test_broadcast_single_failure_does_not_block_others() -> None:
    """broadcast 单连接异常不影响其他连接。"""
    manager = ConnectionManager()
    bad_socket = MagicMock(spec=WebSocket)
    good_socket = MagicMock(spec=WebSocket)
    bad_socket.send_json = AsyncMock(side_effect=OSError("broken pipe"))
    good_socket.send_json = AsyncMock()
    manager._connections["u-bad"] = bad_socket
    manager._connections["u-good"] = good_socket
    await manager.broadcast(MessageType.ROOM_UPDATED, {"roomId": "r1"})
    good_socket.send_json.assert_awaited_once()
    assert "u-bad" not in manager._connections
    assert manager._connections["u-good"] is good_socket


@pytest.mark.asyncio
async def test_broadcast_failure_only_removes_active_connection() -> None:
    """broadcast 失败只清理当前活跃连接，不误删新连接。"""
    manager = ConnectionManager()
    old_socket = MagicMock(spec=WebSocket)
    new_socket = MagicMock(spec=WebSocket)
    old_socket.send_json = AsyncMock(side_effect=RuntimeError("stale"))
    new_socket.send_json = AsyncMock()
    manager._connections["u1"] = old_socket
    await manager.broadcast(MessageType.ROOM_UPDATED, {})
    manager._connections["u1"] = new_socket
    await manager.broadcast(MessageType.ROOM_UPDATED, {})
    assert manager._connections["u1"] is new_socket
    assert new_socket.send_json.await_count == 1


def test_realtime_websocket_disconnect_does_not_call_presence_shell() -> None:
    """WebSocket disconnect 不直接触发 presence shell。"""
    source = inspect.getsource(message_dispatcher.realtime_websocket)
    assert "handle_disconnect" not in source
    assert "mark_member_shell" not in source


@pytest.mark.asyncio
async def test_presence_timeout_marks_shell(monkeypatch) -> None:
    """presence 连续超时后才进入 shell。"""
    notified = []

    async def _handler(room_id, player_id, reason):
        notified.append((room_id, player_id, reason))
        return True

    service = RoomPresenceService()
    service.bind_mark_member_shell_managed_handler(_handler)
    service._repository = MagicMock()
    service._repository.list_playing_room_ids = AsyncMock(return_value=["room-1"])
    service._repository.get_meta = AsyncMock(
        return_value={"status": "playing", "gameCode": "uno"},
    )
    service._repository.list_players = AsyncMock(
        return_value=[{"playerId": "u1", "isAi": False, "managedMode": None}],
    )
    service._repository.get_presence_state = AsyncMock(return_value={"sequence": 0, "missedCount": 2})
    service._repository.save_presence_state = AsyncMock()
    service._repository.delete_presence_state = AsyncMock()
    monkeypatch.setattr(
        "app.modules.room.presence_service.connection_manager.send_to_user",
        AsyncMock(return_value=True),
    )
    await service._tick_room("room-1")
    assert notified == [("room-1", "u1", "timeout")]


@pytest.mark.asyncio
async def test_presence_pong_resets_missed_count() -> None:
    """重连并及时 pong 后不进入 shell。"""
    notified = []
    saved_states = []

    async def _handler(room_id, player_id, reason):
        notified.append((room_id, player_id, reason))
        return True

    service = RoomPresenceService()
    service.bind_mark_member_shell_managed_handler(_handler)
    service._repository = MagicMock()
    service._repository.get_meta = AsyncMock(
        return_value={"status": "playing", "gameCode": "uno"},
    )
    service._repository.get_presence_state = AsyncMock(
        return_value={"sequence": 3, "missedCount": 2},
    )

    async def _save_presence_state(room_id, player_id, state):
        saved_states.append(dict(state))

    service._repository.save_presence_state = _save_presence_state
    await service.accept_pong(
        "u1",
        {"roomId": "room-1", "gameCode": "uno", "sequence": 3},
    )
    assert notified == []
    assert saved_states[-1]["missedCount"] == 0
