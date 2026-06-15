"""RoomModuleService 离开 / 重连等平台通用行为测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.modules.room.module_service import RoomModuleService
from tests.test_room_review_fixes import _build_service


def _build_leave_service() -> RoomModuleService:
    service = _build_service()
    service._repository.delete_room_cascade = AsyncMock()
    service._clear_managed_shell_indexes = AsyncMock()
    return service


def _playing_meta(owner_id: str = "owner-1") -> dict:
    return {
        "status": "playing",
        "gameCode": "uno",
        "ownerPlayerId": owner_id,
        "ownerNickname": owner_id,
    }


def _shell_human(player_id: str, joined_at: int = 2) -> dict:
    return {
        "playerId": player_id,
        "nickname": player_id,
        "joinedAt": joined_at,
        "isAi": False,
        "isManaged": True,
        "managedMode": "shell",
        "managedReason": "leave",
    }


@pytest.mark.asyncio
async def test_playing_human_ai_leave_keeps_room_and_shell_member() -> None:
    """playing 真人 + AI：真人离开后房间保留且进入 shell 托管。"""
    service = _build_leave_service()
    service._require_meta = AsyncMock(return_value=_playing_meta("owner-1"))
    guest_id = "guest-1"
    service._repository.list_players = AsyncMock(
        side_effect=[
            [
                {"playerId": "owner-1", "joinedAt": 1, "isAi": False, "nickname": "房主"},
                {"playerId": guest_id, "joinedAt": 2, "isAi": False, "nickname": "客人"},
                {"playerId": "ai-1", "joinedAt": 3, "isAi": True, "nickname": "AI"},
            ],
            [
                {"playerId": "owner-1", "joinedAt": 1, "isAi": False, "nickname": "房主"},
                _shell_human(guest_id),
                {"playerId": "ai-1", "joinedAt": 3, "isAi": True, "nickname": "AI"},
            ],
        ],
    )
    account = MagicMock()
    account.server_id = guest_id
    with patch("app.modules.room.module_service.push_room_updated", new=AsyncMock()), patch(
        "app.modules.room.module_service.push_room_list_updated",
        new=AsyncMock(),
    ), patch(
        "app.modules.room.module_service.push_game_view_updated",
        new=AsyncMock(),
    ):
        result = await service.leave_room(account, "room-1")
    assert result.dissolved is False
    service._repository.delete_room_cascade.assert_not_called()
    service._repository.save_player.assert_awaited()
    save_args = service._repository.save_player.await_args
    saved_member = save_args.args[2]
    assert saved_member["managedMode"] == "shell"
    assert saved_member["managedReason"] == "leave"
    assert saved_member["onlineState"] == "managed"
    assert saved_member["playerId"] == guest_id
    service._repository.delete_player_room.assert_awaited_once_with(guest_id)
    service._repository.save_managed_shell_room_index.assert_awaited_once_with(
        guest_id,
        "uno",
        "room-1",
    )


@pytest.mark.asyncio
async def test_playing_leave_shell_human_can_rejoin() -> None:
    """playing 真人 leave 为 shell 后可 rejoin 并清除托管标记。"""
    service = _build_leave_service()
    service._require_meta = AsyncMock(return_value=_playing_meta("owner-1"))
    guest_id = "guest-1"
    shell_member = _shell_human(guest_id)
    shell_member["seat"] = 2
    service._repository.list_players = AsyncMock(
        return_value=[
            {"playerId": "owner-1", "joinedAt": 1, "isAi": False},
            dict(shell_member),
            {"playerId": "ai-1", "joinedAt": 3, "isAi": True},
        ],
    )
    service._repository.get_player_room = AsyncMock(return_value=None)
    account = MagicMock()
    account.server_id = guest_id
    with patch("app.modules.room.module_service.push_room_updated", new=AsyncMock()), patch(
        "app.modules.room.module_service.push_room_list_updated",
        new=AsyncMock(),
    ), patch(
        "app.modules.room.module_service.push_game_view_updated",
        new=AsyncMock(),
    ):
        room = await service.rejoin_managed_room(account, "room-1")
    assert room is not None
    save_args = service._repository.save_player.await_args
    restored = save_args.args[2]
    assert restored["managedMode"] is None
    assert restored["isManaged"] is False
    assert restored["playerId"] == guest_id
    assert restored.get("seat") == 2


@pytest.mark.asyncio
async def test_playing_leave_only_ai_remaining_dissolves_room() -> None:
    """playing 无真人且无 shell 真人时仍解散房间。"""
    service = _build_leave_service()
    service._require_meta = AsyncMock(return_value=_playing_meta("owner-1"))
    service._repository.list_players = AsyncMock(
        side_effect=[
            [{"playerId": "owner-1", "joinedAt": 1, "isAi": False}],
            [{"playerId": "ai-1", "joinedAt": 2, "isAi": True}],
        ],
    )
    account = MagicMock()
    account.server_id = "owner-1"
    with patch("app.modules.room.module_service.push_room_list_updated", new=AsyncMock()):
        result = await service.leave_room(account, "room-1")
    assert result.dissolved is True
    assert result.room is None
    service._repository.delete_room_cascade.assert_awaited_once()


@pytest.mark.asyncio
async def test_waiting_leave_removes_member_and_keeps_room() -> None:
    """waiting 房间 leave 移除成员且不删除房间（仍有其他真人）。"""
    service = _build_leave_service()
    service._require_meta = AsyncMock(
        return_value={
            "status": "waiting",
            "gameCode": "uno",
            "ownerPlayerId": "owner-1",
            "ownerNickname": "房主",
        },
    )
    service._repository.list_players = AsyncMock(
        return_value=[
            {"playerId": "owner-1", "joinedAt": 1, "isAi": False},
            {"playerId": "guest-1", "joinedAt": 2, "isAi": False},
        ],
    )
    service._repository.delete_player = AsyncMock(return_value=True)
    account = MagicMock()
    account.server_id = "guest-1"
    with patch("app.modules.room.module_service.push_room_updated", new=AsyncMock()), patch(
        "app.modules.room.module_service.push_room_list_updated",
        new=AsyncMock(),
    ):
        result = await service.leave_room(account, "room-1")
    assert result.dissolved is False
    service._repository.delete_player.assert_awaited_once_with("room-1", "guest-1")
    service._repository.delete_room_cascade.assert_not_called()
    service._repository.save_managed_shell_room_index.assert_not_called()
    save_player_calls = service._repository.save_player.await_args_list
    for call in save_player_calls:
        saved_member = call.args[2]
        assert saved_member.get("managedMode") != "shell"


@pytest.mark.asyncio
async def test_waiting_last_human_leave_dissolves_room() -> None:
    """waiting 最后一名真人离开后解散房间。"""
    service = _build_leave_service()
    service._require_meta = AsyncMock(
        return_value={
            "status": "waiting",
            "gameCode": "uno",
            "ownerPlayerId": "owner-1",
            "ownerNickname": "房主",
        },
    )
    service._repository.list_players = AsyncMock(
        return_value=[{"playerId": "owner-1", "joinedAt": 1, "isAi": False}],
    )
    service._repository.delete_player = AsyncMock(return_value=True)
    account = MagicMock()
    account.server_id = "owner-1"
    with patch("app.modules.room.module_service.push_room_list_updated", new=AsyncMock()):
        result = await service.leave_room(account, "room-1")
    assert result.dissolved is True
    service._repository.delete_room_cascade.assert_awaited_once()


@pytest.mark.asyncio
async def test_playing_owner_leave_shell_only_ai_keeps_room() -> None:
    """playing 房主离开仅剩 shell 自己与 AI 时不解散、不触发房主转移异常。"""
    service = _build_leave_service()
    service._require_meta = AsyncMock(return_value=_playing_meta("owner-1"))
    owner_id = "owner-1"
    service._repository.list_players = AsyncMock(
        side_effect=[
            [
                {"playerId": owner_id, "joinedAt": 1, "isAi": False},
                {"playerId": "ai-1", "joinedAt": 2, "isAi": True},
            ],
            [
                _shell_human(owner_id, joined_at=1),
                {"playerId": "ai-1", "joinedAt": 2, "isAi": True},
            ],
        ],
    )
    account = MagicMock()
    account.server_id = owner_id
    with patch("app.modules.room.module_service.push_room_updated", new=AsyncMock()), patch(
        "app.modules.room.module_service.push_room_list_updated",
        new=AsyncMock(),
    ), patch(
        "app.modules.room.module_service.push_game_view_updated",
        new=AsyncMock(),
    ):
        result = await service.leave_room(account, "room-1")
    assert result.dissolved is False
    service._repository.delete_room_cascade.assert_not_called()


@pytest.mark.asyncio
async def test_playing_human_ai_presence_timeout_keeps_room_and_shell_member() -> None:
    """playing 真人 + AI：presenceTimeout 后房间保留且进入 shell 托管。"""
    service = _build_leave_service()
    service._repository.get_meta = AsyncMock(return_value=_playing_meta("owner-1"))
    guest_id = "guest-1"
    service._repository.list_players = AsyncMock(
        side_effect=[
            [
                {"playerId": "owner-1", "joinedAt": 1, "isAi": False},
                {"playerId": guest_id, "joinedAt": 2, "isAi": False},
                {"playerId": "ai-1", "joinedAt": 3, "isAi": True},
            ],
            [
                {"playerId": "owner-1", "joinedAt": 1, "isAi": False},
                {
                    "playerId": guest_id,
                    "joinedAt": 2,
                    "isAi": False,
                    "isManaged": True,
                    "managedMode": "shell",
                    "managedReason": "presenceTimeout",
                    "onlineState": "managed",
                },
                {"playerId": "ai-1", "joinedAt": 3, "isAi": True},
            ],
        ],
    )
    with patch("app.modules.room.module_service.push_room_updated", new=AsyncMock()), patch(
        "app.modules.room.module_service.push_room_list_updated",
        new=AsyncMock(),
    ), patch(
        "app.modules.room.module_service.push_game_view_updated",
        new=AsyncMock(),
    ):
        ok = await service.mark_member_shell_managed("room-1", guest_id, "presenceTimeout")
    assert ok is True
    service._repository.delete_room_cascade.assert_not_called()
    save_args = service._repository.save_player.await_args
    saved_member = save_args.args[2]
    assert saved_member["managedMode"] == "shell"
    assert saved_member["managedReason"] == "presenceTimeout"
    assert saved_member["onlineState"] == "managed"
    service._repository.delete_player_room.assert_awaited_once_with(guest_id)
    service._repository.save_managed_shell_room_index.assert_awaited_once_with(
        guest_id,
        "uno",
        "room-1",
    )


@pytest.mark.asyncio
async def test_mark_shell_managed_skips_ai_and_does_not_write_shell_index() -> None:
    """playing 仅 AI 时不对 AI 转 shell，也不写入 shell 索引。"""
    service = _build_leave_service()
    service._repository.get_meta = AsyncMock(return_value=_playing_meta("owner-1"))
    service._repository.list_players = AsyncMock(
        return_value=[{"playerId": "ai-1", "joinedAt": 1, "isAi": True}],
    )
    ok = await service.mark_member_shell_managed("room-1", "ai-1", "presenceTimeout")
    assert ok is True
    service._repository.save_managed_shell_room_index.assert_not_called()
    service._repository.save_player.assert_not_awaited()


@pytest.mark.asyncio
async def test_mark_shell_managed_locked_shell_index_failure_raises() -> None:
    """shell index 写入失败时抛异常、回滚 member，且不删除 player_room。"""
    service = _build_leave_service()
    service._repository.save_managed_shell_room_index = AsyncMock(return_value=False)
    meta = _playing_meta("owner-1")
    original_member = {
        "playerId": "guest-1",
        "joinedAt": 1,
        "isAi": False,
        "nickname": "客人",
        "isManaged": False,
        "managedMode": None,
    }
    members = [dict(original_member)]
    with pytest.raises(BizException) as exc_info:
        await service._mark_shell_managed_locked(
            "room-1",
            meta,
            members,
            "guest-1",
            "leave",
            1000,
        )
    assert exc_info.value.code == ErrorCode.SYSTEM_ERROR.code
    assert "托管房间索引写入失败" in str(exc_info.value.message)
    service._repository.delete_player_room.assert_not_awaited()
    assert service._repository.save_player.await_count == 2
    rollback_args = service._repository.save_player.await_args_list[1]
    rolled_back = rollback_args.args[2]
    assert rolled_back["isManaged"] is False
    assert rolled_back.get("managedMode") is None
    assert rolled_back["playerId"] == "guest-1"


@pytest.mark.asyncio
async def test_mark_shell_managed_locked_delete_player_room_failure_rolls_back() -> None:
    """delete_player_room 失败时抛异常、回滚 member 并清理 shell index。"""
    service = _build_leave_service()
    service._repository.save_managed_shell_room_index = AsyncMock(return_value=True)
    service._repository.delete_player_room = AsyncMock(return_value=False)
    meta = _playing_meta("owner-1")
    original_member = {
        "playerId": "guest-1",
        "joinedAt": 1,
        "isAi": False,
        "nickname": "客人",
        "isManaged": False,
        "managedMode": None,
    }
    members = [dict(original_member)]
    with pytest.raises(BizException) as exc_info:
        await service._mark_shell_managed_locked(
            "room-1",
            meta,
            members,
            "guest-1",
            "leave",
            1000,
        )
    assert exc_info.value.code == ErrorCode.SYSTEM_ERROR.code
    assert "玩家房间索引删除失败" in str(exc_info.value.message)
    service._repository.delete_managed_shell_room_index.assert_awaited_once_with(
        "guest-1",
        "uno",
    )
    assert service._repository.save_player.await_count == 2
    rollback_args = service._repository.save_player.await_args_list[1]
    rolled_back = rollback_args.args[2]
    assert rolled_back["isManaged"] is False
    assert rolled_back.get("managedMode") is None


@pytest.mark.asyncio
async def test_mark_member_shell_managed_save_meta_failure_no_bump_no_push() -> None:
    """mark_member_shell_managed 在 save_meta 失败时不 bump version、不推送房间更新。"""
    service = _build_leave_service()
    service._repository.get_meta = AsyncMock(return_value=_playing_meta("owner-1"))
    guest_id = "guest-1"
    service._repository.list_players = AsyncMock(
        return_value=[
            {"playerId": "owner-1", "joinedAt": 1, "isAi": False},
            {"playerId": guest_id, "joinedAt": 2, "isAi": False},
        ],
    )
    service._repository.save_meta = AsyncMock(return_value=False)
    with patch("app.modules.room.module_service.push_room_updated", new=AsyncMock()) as push_room, patch(
        "app.modules.room.module_service.push_room_list_updated",
        new=AsyncMock(),
    ) as push_list, patch(
        "app.modules.room.module_service.push_game_view_updated",
        new=AsyncMock(),
    ):
        with pytest.raises(BizException) as exc_info:
            await service.mark_member_shell_managed("room-1", guest_id, "presenceTimeout")
    assert exc_info.value.code == ErrorCode.SYSTEM_ERROR.code
    assert "房间元信息更新失败" in str(exc_info.value.message)
    service._bump_version.assert_not_awaited()
    push_room.assert_not_awaited()
    push_list.assert_not_awaited()


@pytest.mark.asyncio
async def test_leave_room_bumps_version_once() -> None:
    """playing leave 成功路径只 bump 一次 version。"""
    service = _build_leave_service()
    service._require_meta = AsyncMock(return_value=_playing_meta("owner-1"))
    guest_id = "guest-1"
    service._repository.list_players = AsyncMock(
        side_effect=[
            [
                {"playerId": "owner-1", "joinedAt": 1, "isAi": False, "nickname": "房主"},
                {"playerId": guest_id, "joinedAt": 2, "isAi": False, "nickname": "客人"},
            ],
            [
                {"playerId": "owner-1", "joinedAt": 1, "isAi": False, "nickname": "房主"},
                _shell_human(guest_id),
            ],
        ],
    )
    service._repository.delete_player_room = AsyncMock(return_value=True)
    account = MagicMock()
    account.server_id = guest_id
    with patch("app.modules.room.module_service.push_room_updated", new=AsyncMock()), patch(
        "app.modules.room.module_service.push_room_list_updated",
        new=AsyncMock(),
    ), patch(
        "app.modules.room.module_service.push_game_view_updated",
        new=AsyncMock(),
    ):
        result = await service.leave_room(account, "room-1")
    assert result.dissolved is False
    service._bump_version.assert_awaited_once_with("room-1")


@pytest.mark.asyncio
async def test_playing_leave_shell_index_failure_raises() -> None:
    """playing leave 时 shell index 写入失败抛异常且不返回成功离开。"""
    service = _build_leave_service()
    service._require_meta = AsyncMock(return_value=_playing_meta("owner-1"))
    service._repository.save_managed_shell_room_index = AsyncMock(return_value=False)
    service._repository.list_players = AsyncMock(
        side_effect=[
            [
                {"playerId": "owner-1", "joinedAt": 1, "isAi": False},
                {"playerId": "guest-1", "joinedAt": 2, "isAi": False},
            ],
            [
                {"playerId": "owner-1", "joinedAt": 1, "isAi": False},
                _shell_human("guest-1"),
            ],
        ],
    )
    account = MagicMock()
    account.server_id = "guest-1"
    with pytest.raises(BizException) as exc_info:
        await service.leave_room(account, "room-1")
    assert exc_info.value.code == ErrorCode.SYSTEM_ERROR.code
    service._repository.delete_room_cascade.assert_not_called()
    service._repository.delete_player_room.assert_not_awaited()


def test_should_cleanup_playing_room() -> None:
    """_should_cleanup_playing_room 在无真人且无 shell 真人时为 True。"""
    service = RoomModuleService(
        repository=MagicMock(),
        lock_service=MagicMock(),
        game_service=MagicMock(),
        runtime_service=MagicMock(),
        account_service=MagicMock(),
        managed_task_service=MagicMock(),
        managed_action_selector=MagicMock(),
    )
    assert service._should_cleanup_playing_room([{"playerId": "ai-1", "isAi": True}]) is True
    assert service._should_cleanup_playing_room([_shell_human("human-1")]) is False
    assert service._should_cleanup_playing_room(
        [{"playerId": "u1", "isAi": False, "isManaged": False}],
    ) is False


def test_has_rejoinable_shell_human_member() -> None:
    """_has_rejoinable_shell_human_member 识别非 AI 的 shell 成员。"""
    service = RoomModuleService(
        repository=MagicMock(),
        lock_service=MagicMock(),
        game_service=MagicMock(),
        runtime_service=MagicMock(),
        account_service=MagicMock(),
        managed_task_service=MagicMock(),
        managed_action_selector=MagicMock(),
    )
    members = [
        {"playerId": "ai-1", "isAi": True, "isManaged": True, "managedMode": "shell"},
        _shell_human("human-1"),
    ]
    assert service._has_rejoinable_shell_human_member(members) is True
    assert service._has_rejoinable_shell_human_member([{"playerId": "ai-1", "isAi": True}]) is False
