"""房间托管修复与 add_room_ai 平台能力测试。"""

import asyncio
import inspect
import json
from types import MethodType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.redis.redis_keys import RedisKeys
from app.core.websocket.message_types import MessageType
from app.modules.room import realtime_service
from app.modules.room.managed_task_repository import ManagedTaskEnqueueResult, ManagedTaskRepository
from app.modules.room.managed_task_service import ManagedTurnTaskService
from app.modules.room.module_service import RoomModuleService
from app.modules.room.schemas import RoomMemberResponse, RoomResponse
from app.modules.strategy_turn.schemas import GameView, RuntimeSnapshot, StrategyTurnRuntimeRule
from tests.test_room_background_and_managed_tasks import (
    MANAGED_TASK_VISIBILITY_TIMEOUT_MS,
    _FakeRedisClient,
    _sample_task,
)


class _FakeLock(object):
    """异步锁占位。"""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


def _runtime_snapshot(current_player_id: str = "ai-1", player_ids=None):
    if player_ids is None:
        player_ids = ["u1", "ai-1"]
    return RuntimeSnapshot(
        gameCode="uno",
        roomId="room-1",
        runtimeRule=StrategyTurnRuntimeRule(
            gameCode="uno",
            mode="classic",
            playerIds=player_ids,
            config={},
        ),
        state={"currentPlayerId": current_player_id},
        eventLog=[],
        eventSequence=0,
        startedAt=1,
        updatedAt=1,
        isGameOver=False,
    )


def _build_service() -> RoomModuleService:
    service = RoomModuleService(
        repository=MagicMock(),
        lock_service=MagicMock(),
        game_service=MagicMock(),
        runtime_service=MagicMock(),
        account_service=MagicMock(),
        managed_task_service=MagicMock(),
        managed_action_selector=MagicMock(),
    )
    service._acquire_user_room_lock = AsyncMock(return_value=_FakeLock())
    service._lock_service.acquire = AsyncMock(return_value=_FakeLock())
    service._bump_version = AsyncMock(return_value=8)
    service._repository.refresh_room_ttl = AsyncMock()
    service._repository.save_player = AsyncMock(return_value=True)
    service._repository.save_meta = AsyncMock(return_value=True)
    service._repository.delete_player_room = AsyncMock()
    service._repository.delete_managed_shell_room_index = AsyncMock(return_value=True)
    service._repository.save_player_room = AsyncMock(return_value=True)
    service._managed_task_service.enqueue_task = AsyncMock(
        return_value=ManagedTaskEnqueueResult(created=True),
    )
    service._load_runtime_snapshot = AsyncMock(return_value=_runtime_snapshot())
    service._extract_current_player_id = MagicMock(return_value="ai-1")
    service.create_managed_turn_task = AsyncMock(return_value=None)
    service._build_room_response = MagicMock(
        side_effect=lambda meta, members, version: RoomResponse(
            roomId="room-1",
            roomName="房间",
            gameCode="uno",
            mode="classic",
            ownerPlayerId="u1",
            ownerNickname="u1",
            maxPlayers=4,
            aiCount=0,
            version=version,
            status=str(meta.get("status", "playing")),
            memberCount=len(members),
            members=[],
            createdAt=1,
            updatedAt=2,
        ),
    )
    return service


@pytest.mark.asyncio
async def test_stop_managed_mode_bumps_version_creates_managed_task_for_current_player() -> None:
    """stopManagedMode 非 action bump 后为当前托管/AI 玩家创建任务。"""
    service = _build_service()
    playing_meta = {"status": "playing", "gameCode": "uno", "ownerPlayerId": "u1"}
    service._require_meta = AsyncMock(return_value=playing_meta)
    service._repository.get_meta = AsyncMock(return_value=playing_meta)
    service._require_playing_room = MagicMock()
    service._repository.list_players = AsyncMock(
        return_value=[
            {
                "playerId": "u1",
                "isManaged": True,
                "managedMode": "active",
                "managedReason": "manual",
                "isAi": False,
            },
            {
                "playerId": "ai-1",
                "isManaged": True,
                "managedMode": "active",
                "managedReason": "ai",
                "isAi": True,
            },
        ],
    )
    service._extract_current_player_id = MagicMock(return_value="ai-1")
    account = MagicMock()
    account.server_id = "u1"
    with patch("app.modules.room.module_service.push_room_updated", new=AsyncMock()), patch(
        "app.modules.room.module_service.push_room_list_updated",
        new=AsyncMock(),
    ), patch(
        "app.modules.room.module_service.push_game_view_updated",
        new=AsyncMock(),
    ):
        await service.stop_managed_mode(account, "room-1")
    service.create_managed_turn_task.assert_awaited_once_with("room-1", "ai-1", "managedModeStopped")


@pytest.mark.asyncio
async def test_mark_shell_already_shell_compensates_managed_task() -> None:
    """目标已是 shell 时仍补偿创建当前玩家托管任务。"""
    service = _build_service()
    service._repository.get_meta = AsyncMock(
        return_value={"status": "playing", "gameCode": "uno", "ownerPlayerId": "u2"},
    )
    service._repository.list_players = AsyncMock(
        return_value=[
            {
                "playerId": "u1",
                "isManaged": True,
                "managedMode": "shell",
                "managedReason": "leave",
                "isAi": False,
            },
        ],
    )
    service._extract_current_player_id = MagicMock(return_value="u1")
    result = await service.mark_member_shell_managed("room-1", "u1", "leave")
    assert result is True
    service._repository.save_player.assert_not_awaited()
    service.create_managed_turn_task.assert_awaited_once_with("room-1", "u1", "leave")


def test_finalize_task_atomic_updates_data_and_removes_processing_and_due() -> None:
    """finalize_task 原子写入终态并清理 processing 与 due。"""
    fake_redis = _FakeRedisClient()
    repository = ManagedTaskRepository(fake_redis)
    task_data = _sample_task(taskId="task-final").model_dump()

    async def _run():
        await repository.enqueue_task("room-1", "p1", 1, task_data)
        await repository.claim_due_task(100, MANAGED_TASK_VISIBILITY_TIMEOUT_MS)
        fake_redis._zsets.setdefault(RedisKeys.managed_task_due(), {})["task-final"] = 50.0
        task_data["status"] = "skipped"
        task_data["skipReason"] = "versionChanged"
        assert await repository.finalize_task("task-final", task_data) is True
        assert "task-final" not in fake_redis._zsets.get(RedisKeys.managed_task_processing(), {})
        assert "task-final" not in fake_redis._zsets.get(RedisKeys.managed_task_due(), {})
        stored = await repository.get_task("task-final")
        assert stored["status"] == "skipped"
        assert stored["skipReason"] == "versionChanged"
        assert stored.get("updatedAt") is not None

    asyncio.run(_run())


def test_release_to_due_forces_pending_status() -> None:
    """release_to_due 在仓库层强制 status=pending。"""
    fake_redis = _FakeRedisClient()
    repository = ManagedTaskRepository(fake_redis)
    task_data = _sample_task(taskId="task-pending", status="running").model_dump()

    async def _run():
        await repository.enqueue_task("room-1", "p1", 1, task_data)
        await repository.claim_due_task(100, MANAGED_TASK_VISIBILITY_TIMEOUT_MS)
        task_data["status"] = "running"
        assert await repository.release_to_due("task-pending", 600, task_data) is True
        stored = await repository.get_task("task-pending")
        assert stored["status"] == "pending"

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_push_room_updated_does_not_push_room_list_updated() -> None:
    """push_room_updated 仅推 ROOM_UPDATED，不隐式推列表。"""
    room = RoomResponse(
        roomId="room-1",
        roomName="房间",
        gameCode="uno",
        mode="classic",
        ownerPlayerId="u1",
        ownerNickname="u1",
        maxPlayers=4,
        aiCount=0,
        version=1,
        status="waiting",
        memberCount=1,
        members=[
            RoomMemberResponse(
                playerId="u1",
                nickname="u1",
                joinedAt=1,
                isAi=False,
                isManaged=False,
                managedMode=None,
            ),
        ],
        createdAt=1,
        updatedAt=2,
    )
    with patch(
        "app.modules.room.realtime_service.send_to_user",
        new=AsyncMock(return_value=True),
    ) as send_mock, patch(
        "app.modules.room.realtime_service.push_room_list_updated",
        new=AsyncMock(),
    ) as list_mock:
        await realtime_service.push_room_updated(room)
    send_mock.assert_awaited_once()
    assert send_mock.await_args[0][1] == MessageType.ROOM_UPDATED
    list_mock.assert_not_awaited()


def test_managed_task_service_has_no_run_room_task() -> None:
    """托管服务已删除 _run_room_task 空实现。"""
    assert not hasattr(ManagedTurnTaskService, "_run_room_task")


def test_finalize_task_does_not_call_update_task_plus_remove() -> None:
    """finalize_task 实现为单 Lua，不再分步 update + remove。"""
    source = inspect.getsource(ManagedTaskRepository.finalize_task)
    assert "update_task" not in source
    assert "remove_from_processing" not in source
    assert "_FINALIZE_TASK_SCRIPT" in source


def test_cleanup_orphan_task_uses_lua() -> None:
    """_cleanup_orphan_task 通过 Lua 原子清理 processing 与 due。"""
    source = inspect.getsource(ManagedTaskRepository._cleanup_orphan_task)
    assert "_CLEANUP_ORPHAN_TASK_SCRIPT" in source
    assert "remove_from_processing" not in source


@pytest.mark.asyncio
async def test_add_room_ai_rejects_when_allow_ai_false() -> None:
    """allowAi=false 时不能添加 AI。"""
    from app.modules.game_seed.schemas import RoomRule

    service = _build_service()
    service._require_meta = AsyncMock(
        return_value={
            "status": "waiting",
            "gameCode": "uno",
            "ownerPlayerId": "u1",
            "maxPlayers": 4,
        }
    )
    service._require_waiting_room = MagicMock()
    service._require_room_owner = MagicMock()
    service._repository.list_players = AsyncMock(return_value=[])
    mock_definition = MagicMock()
    mock_definition.roomRule = RoomRule(
        minPlayers=2,
        maxPlayers=4,
        allowAi=False,
        minAiCount=0,
        maxAiCount=2,
        defaultExpireSeconds=86400,
    )
    service._game_service = MagicMock()
    service._game_service.get_game_rule_definition = MagicMock(return_value=mock_definition)
    account = MagicMock()
    account.server_id = "u1"
    with pytest.raises(BizException) as exc_info:
        await service.add_room_ai(account, "room-1")
    assert exc_info.value.code == ErrorCode.PARAM_ERROR.code


@pytest.mark.asyncio
async def test_managed_shell_room_uses_index() -> None:
    """get_my_managed_shell_room 通过索引定位房间。"""
    service = _build_service()
    service._game_service.get_game_rule_definition = MagicMock()
    service._repository.get_managed_shell_room_index = AsyncMock(return_value="room-shell-1")
    service._repository.get_meta = AsyncMock(
        return_value={
            "roomId": "room-shell-1",
            "gameCode": "uno",
            "status": "playing",
            "ownerPlayerId": "u2",
            "maxPlayers": 4,
            "mode": "classic",
            "roomName": "房间",
            "ownerNickname": "u2",
            "aiCount": 0,
            "createdAt": 1,
            "updatedAt": 2,
        }
    )
    service._repository.list_players = AsyncMock(
        return_value=[
            {
                "playerId": "u-shell",
                "nickname": "shell",
                "joinedAt": 1,
                "isManaged": True,
                "managedMode": "shell",
                "managedReason": "leave",
                "isAi": False,
            },
        ]
    )
    service._repository.get_version = AsyncMock(return_value=3)
    service._build_room_response = MagicMock(
        side_effect=lambda meta, members, version: RoomResponse(
            roomId=str(meta.get("roomId", "")),
            roomName="房间",
            gameCode="uno",
            mode="classic",
            ownerPlayerId="u2",
            ownerNickname="u2",
            maxPlayers=4,
            aiCount=0,
            version=version,
            status="playing",
            memberCount=len(members),
            members=[],
            createdAt=1,
            updatedAt=2,
        ),
    )
    account = MagicMock()
    account.server_id = "u-shell"
    result = await service.get_my_managed_shell_room(account, "uno")
    assert result.room is not None
    assert result.room.roomId == "room-shell-1"


@pytest.mark.asyncio
async def test_rejoin_managed_room_clears_stale_same_room_player_room_index() -> None:
    """indexed_room_id 与当前房间相同时先清理脏 player_room 索引再恢复。"""
    service = _build_service()
    service._require_meta = AsyncMock(
        return_value={
            "roomId": "room-1",
            "gameCode": "uno",
            "status": "playing",
            "ownerPlayerId": "u1",
            "maxPlayers": 4,
            "mode": "classic",
        }
    )
    service._repository.list_players = AsyncMock(
        return_value=[
            {
                "playerId": "u1",
                "nickname": "u1",
                "joinedAt": 1,
                "isManaged": True,
                "managedMode": "shell",
                "managedReason": "leave",
                "isAi": False,
            },
        ]
    )
    service._repository.get_player_room = AsyncMock(return_value="room-1")
    service.push_current_game_view_if_playing = AsyncMock()
    service.create_current_player_managed_task_if_needed = AsyncMock()
    account = MagicMock()
    account.server_id = "u1"
    await service.rejoin_managed_room(account, "room-1")
    service._repository.delete_player_room.assert_awaited_with("u1")
    service._repository.save_player_room.assert_awaited_with("u1", "room-1")


@pytest.mark.asyncio
async def test_rejoin_managed_room_deletes_shell_index() -> None:
    """rejoinManagedRoom 成功后删除 shell 索引。"""
    service = _build_service()
    service._require_meta = AsyncMock(
        return_value={
            "roomId": "room-1",
            "gameCode": "uno",
            "status": "playing",
            "ownerPlayerId": "u1",
            "maxPlayers": 4,
            "mode": "classic",
        }
    )
    service._repository.list_players = AsyncMock(
        return_value=[
            {
                "playerId": "u1",
                "nickname": "u1",
                "joinedAt": 1,
                "isManaged": True,
                "managedMode": "shell",
                "managedReason": "leave",
                "isAi": False,
            },
        ]
    )
    service._repository.get_player_room = AsyncMock(return_value=None)
    service.push_current_game_view_if_playing = AsyncMock()
    service.create_current_player_managed_task_if_needed = AsyncMock()
    account = MagicMock()
    account.server_id = "u1"
    await service.rejoin_managed_room(account, "room-1")
    service._repository.delete_managed_shell_room_index.assert_awaited_once_with("u1", "uno")


@pytest.mark.asyncio
async def test_create_managed_turn_task_dedupe_does_not_warn() -> None:
    """dedupe 命中时不打印 warning，仅 debug。"""
    service = _build_service()
    service._repository.get_meta = AsyncMock(return_value={"status": "playing", "gameCode": "uno"})
    service._load_runtime_snapshot = AsyncMock(return_value=_runtime_snapshot())
    service._repository.list_players = AsyncMock(
        return_value=[{"playerId": "ai-1", "isAi": True, "isManaged": True}]
    )
    service._repository.get_version = AsyncMock(return_value=3)
    duplicate_result = ManagedTaskEnqueueResult(duplicated=True)
    service._managed_task_service.enqueue_task = AsyncMock(return_value=duplicate_result)
    service.create_managed_turn_task = MethodType(RoomModuleService.create_managed_turn_task, service)
    with patch("app.modules.room.module_service.logger") as logger_mock:
        result = await service.create_managed_turn_task("room-1", "ai-1", "afterAction")
        assert result is None
        logger_mock.warning.assert_not_called()
        logger_mock.debug.assert_called_once()


@pytest.mark.asyncio
async def test_create_managed_turn_task_failure_logs_warning() -> None:
    """入队失败时打印 warning。"""
    service = _build_service()
    service._repository.get_meta = AsyncMock(return_value={"status": "playing", "gameCode": "uno"})
    service._load_runtime_snapshot = AsyncMock(return_value=_runtime_snapshot())
    service._repository.list_players = AsyncMock(
        return_value=[{"playerId": "ai-1", "isAi": True, "isManaged": True}]
    )
    service._repository.get_version = AsyncMock(return_value=3)
    failed_result = ManagedTaskEnqueueResult(failed=True)
    service._managed_task_service.enqueue_task = AsyncMock(return_value=failed_result)
    service.create_managed_turn_task = MethodType(RoomModuleService.create_managed_turn_task, service)
    with patch("app.modules.room.module_service.logger") as logger_mock:
        result = await service.create_managed_turn_task("room-1", "ai-1", "afterAction")
        assert result is None
        logger_mock.warning.assert_called_once()


@pytest.mark.asyncio
async def test_start_room_game_saves_runtime_before_bump_version() -> None:
    """start_room_game 先保存 runtime 再 bump version。"""
    call_order = []
    service = _build_service()
    service._require_meta = AsyncMock(
        return_value={
            "status": "waiting",
            "gameCode": "uno",
            "mode": "classic",
            "ownerPlayerId": "u1",
            "maxPlayers": 4,
            "roomConfig": {},
        }
    )
    service._require_waiting_room = MagicMock()
    service._require_room_owner = MagicMock()
    service._repository.list_players = AsyncMock(
        return_value=[
            {"playerId": "u1", "joinedAt": 1, "isAi": False},
            {"playerId": "u2", "joinedAt": 2, "isAi": False},
        ]
    )
    service._require_member = MagicMock()
    mock_definition = MagicMock()
    mock_definition.roomRule.minPlayers = 2
    service._game_service = MagicMock()
    service._game_service.get_game_rule_definition = MagicMock(return_value=mock_definition)
    runtime_rule = StrategyTurnRuntimeRule(
        gameCode="uno",
        mode="classic",
        playerIds=["u1", "u2"],
        config={},
    )
    service._build_runtime_rule = MagicMock(return_value=runtime_rule)
    snapshot = _runtime_snapshot("u1", ["u1", "u2"])
    start_result = MagicMock()
    start_result.snapshot = snapshot
    start_result.newEvents = []
    service._runtime_service.start_game = MagicMock(return_value=start_result)

    async def _save_runtime(room_id, snap):
        call_order.append("save_runtime")
        return None

    async def _bump(room_id):
        call_order.append("bump_version")
        return 5

    service._save_runtime_snapshot = AsyncMock(side_effect=_save_runtime)
    service._bump_version = AsyncMock(side_effect=_bump)
    service._repository.save_meta = AsyncMock(return_value=True)
    service._repository.add_playing_room = AsyncMock()
    service._enrich_game_view = MagicMock(return_value=MagicMock())
    service._build_room_response = MagicMock(return_value=MagicMock(members=[]))
    service.create_current_player_managed_task_if_needed = AsyncMock()
    account = MagicMock()
    account.server_id = "u1"
    with patch("app.modules.room.module_service.push_room_updated", new=AsyncMock()), patch(
        "app.modules.room.module_service.push_room_list_updated",
        new=AsyncMock(),
    ), patch(
        "app.modules.room.module_service.push_game_view_updated",
        new=AsyncMock(),
    ), patch(
        "app.modules.room.module_service.build_views_for_members",
        return_value=[],
    ), patch(
        "app.modules.room.module_service.collect_human_player_ids",
        return_value=[],
    ):
        await service.start_room_game(account, "room-1")
    assert call_order.index("save_runtime") < call_order.index("bump_version")


@pytest.mark.asyncio
async def test_submit_action_locked_saves_runtime_before_bump_version() -> None:
    """_submit_action_locked 未结束时先保存 runtime 再 bump version。"""
    call_order = []
    service = _build_service()
    service._require_meta = AsyncMock(return_value={"status": "playing", "gameCode": "uno"})
    service._require_playing_room = MagicMock()
    service._repository.list_players = AsyncMock(
        return_value=[{"playerId": "u1", "joinedAt": 1, "isAi": False}]
    )
    service._load_runtime_snapshot = AsyncMock(return_value=_runtime_snapshot("u1"))
    apply_result = MagicMock()
    apply_result.snapshot = _runtime_snapshot("u2")
    apply_result.newEvents = []
    service._runtime_service.apply_player_action = MagicMock(return_value=apply_result)

    async def _save_runtime(room_id, snap):
        call_order.append("save_runtime")
        return None

    async def _bump(room_id):
        call_order.append("bump_version")
        return 6

    service._save_runtime_snapshot = AsyncMock(side_effect=_save_runtime)
    service._bump_version = AsyncMock(side_effect=_bump)
    service._repository.save_meta = AsyncMock(return_value=True)
    service._enrich_game_view = MagicMock(return_value=MagicMock())
    service._build_room_response = MagicMock(return_value=MagicMock(members=[]))
    service.create_managed_turn_task = AsyncMock()
    with patch("app.modules.room.module_service.push_room_updated", new=AsyncMock()), patch(
        "app.modules.room.module_service.push_game_view_updated",
        new=AsyncMock(),
    ), patch(
        "app.modules.room.module_service.build_views_for_members",
        return_value=[],
    ), patch(
        "app.modules.room.module_service.collect_human_player_ids",
        return_value=[],
    ):
        await service._submit_action_locked("room-1", "u1", "draw", None)
    assert call_order.index("save_runtime") < call_order.index("bump_version")


@pytest.mark.asyncio
async def test_submit_action_game_over_pushes_game_view_before_room_updated() -> None:
    """对局结束时先推 gameViewUpdated，再推 roomUpdated 与 roomListUpdated。"""
    service = _build_service()
    service._require_meta = AsyncMock(
        return_value={
            "status": "playing",
            "gameCode": "uno",
            "ownerPlayerId": "u1",
        },
    )
    service._require_playing_room = MagicMock()
    service._repository.list_players = AsyncMock(
        return_value=[
            {
                "playerId": "u1",
                "joinedAt": 1,
                "isAi": False,
                "isManaged": False,
            },
            {
                "playerId": "u2",
                "joinedAt": 2,
                "isAi": False,
                "isManaged": False,
            },
        ],
    )
    game_over_snapshot = _runtime_snapshot("u1", ["u1", "u2"]).model_copy(update={"isGameOver": True})
    service._load_runtime_snapshot = AsyncMock(return_value=game_over_snapshot)
    service._runtime_service.apply_player_action = MagicMock(
        return_value=MagicMock(snapshot=game_over_snapshot, newEvents=[]),
    )
    service._repository.clear_match_runtime = AsyncMock()
    service._repository.remove_playing_room = AsyncMock()
    service._repository.save_meta = AsyncMock(return_value=True)
    service._bump_version = AsyncMock(return_value=8)
    service._repository.refresh_room_ttl = AsyncMock()
    service._enrich_game_view = MagicMock(return_value=MagicMock())
    service._build_room_response = MagicMock(return_value=MagicMock(members=[]))
    push_order = []

    async def _track_game_view(*args, **kwargs):
        del args, kwargs
        push_order.append("game_view")

    async def _track_room_updated(*args, **kwargs):
        del args, kwargs
        push_order.append("room_updated")

    async def _track_room_list(*game_code):
        del game_code
        push_order.append("room_list")

    with patch(
        "app.modules.room.module_service.push_game_view_updated",
        new=AsyncMock(side_effect=_track_game_view),
    ), patch(
        "app.modules.room.module_service.push_room_updated",
        new=AsyncMock(side_effect=_track_room_updated),
    ), patch(
        "app.modules.room.module_service.push_room_list_updated",
        new=AsyncMock(side_effect=_track_room_list),
    ), patch(
        "app.modules.room.module_service.build_views_for_members",
        return_value={},
    ), patch(
        "app.modules.room.module_service.collect_human_player_ids",
        return_value=["u1", "u2"],
    ):
        await service._submit_action_locked("room-1", "u1", "draw", None)
    assert push_order == ["game_view", "room_updated", "room_list"]


@pytest.mark.asyncio
async def test_start_room_game_resets_human_managed_state() -> None:
    """start_room_game 开局前重置真人托管状态，保留 AI 托管。"""
    service = _build_service()
    service._require_meta = AsyncMock(
        return_value={
            "status": "waiting",
            "gameCode": "uno",
            "mode": "classic",
            "ownerPlayerId": "u1",
            "maxPlayers": 4,
            "roomConfig": {},
        }
    )
    service._require_waiting_room = MagicMock()
    service._require_room_owner = MagicMock()
    human_member = {
        "playerId": "u1",
        "joinedAt": 1,
        "isAi": False,
        "isManaged": True,
        "managedMode": "active",
        "managedReason": "manual",
        "managedAt": 100,
    }
    ai_member = {
        "playerId": "ai-1",
        "joinedAt": 2,
        "isAi": True,
        "isManaged": True,
        "managedMode": "active",
        "managedReason": "ai",
        "managedAt": 200,
    }
    service._repository.list_players = AsyncMock(return_value=[human_member, ai_member])
    service._require_member = MagicMock()
    mock_definition = MagicMock()
    mock_definition.roomRule.minPlayers = 2
    service._game_service = MagicMock()
    service._game_service.get_game_rule_definition = MagicMock(return_value=mock_definition)
    runtime_rule = StrategyTurnRuntimeRule(
        gameCode="uno",
        mode="classic",
        playerIds=["u1", "ai-1"],
        config={},
    )
    service._build_runtime_rule = MagicMock(return_value=runtime_rule)
    snapshot = _runtime_snapshot("u1", ["u1", "ai-1"])
    start_result = MagicMock()
    start_result.snapshot = snapshot
    start_result.newEvents = []
    service._runtime_service.start_game = MagicMock(return_value=start_result)
    service._save_runtime_snapshot = AsyncMock()
    service._bump_version = AsyncMock(return_value=5)
    service._repository.save_meta = AsyncMock(return_value=True)
    service._repository.add_playing_room = AsyncMock()
    service._enrich_game_view = MagicMock(return_value=MagicMock())
    service._build_room_response = MagicMock(return_value=MagicMock(members=[]))
    service.create_current_player_managed_task_if_needed = AsyncMock()
    saved_players = []

    async def _save_player(room_id, player_id, member):
        saved_players.append((room_id, player_id, dict(member)))
        return True

    service._repository.save_player = AsyncMock(side_effect=_save_player)
    account = MagicMock()
    account.server_id = "u1"
    with patch("app.modules.room.module_service.push_room_updated", new=AsyncMock()), patch(
        "app.modules.room.module_service.push_room_list_updated",
        new=AsyncMock(),
    ), patch(
        "app.modules.room.module_service.push_game_view_updated",
        new=AsyncMock(),
    ), patch(
        "app.modules.room.module_service.build_views_for_members",
        return_value=[],
    ), patch(
        "app.modules.room.module_service.collect_human_player_ids",
        return_value=[],
    ):
        await service.start_room_game(account, "room-1")
    assert len(saved_players) == 1
    assert saved_players[0][1] == "u1"
    assert saved_players[0][2]["isManaged"] is False
    assert saved_players[0][2]["managedMode"] is None
    assert saved_players[0][2]["managedReason"] is None
    assert saved_players[0][2]["managedAt"] is None
    runtime_call = service._runtime_service.start_game.call_args
    assert runtime_call is not None
    player_ids = list(runtime_call.args[0].runtimeRule.playerIds)
    assert "u1" in player_ids
    assert "ai-1" in player_ids
    build_rule_members = service._build_runtime_rule.call_args.args[1]
    human_in_rule = next(item for item in build_rule_members if item.get("playerId") == "u1")
    assert human_in_rule["isManaged"] is False
    assert human_in_rule["managedMode"] is None
    ai_in_rule = next(item for item in build_rule_members if item.get("playerId") == "ai-1")
    assert ai_in_rule["isManaged"] is True
    assert ai_in_rule["managedMode"] == "active"


@pytest.mark.asyncio
async def test_append_ai_players_rolls_back_on_meta_save_failure() -> None:
    """meta 保存失败时回滚新增 AI member 并还原 aiCount / aiPlayerIds / updatedAt。"""
    service = _build_service()
    meta = {"aiCount": 0, "updatedAt": 100, "roomConfig": {"aiPlayerIds": []}}
    members = [{"playerId": "u1", "isAi": False}]
    deleted_player_ids = []

    async def _delete_player(room_id, player_id):
        deleted_player_ids.append(player_id)
        return True

    save_meta_attempts = 0

    async def _save_meta(room_id, payload, *args):
        del room_id, payload, args
        nonlocal save_meta_attempts
        save_meta_attempts += 1
        if save_meta_attempts == 1:
            return False
        return True

    service._repository.save_player = AsyncMock(return_value=True)
    service._repository.delete_player = AsyncMock(side_effect=_delete_player)
    service._repository.save_meta = AsyncMock(side_effect=_save_meta)
    with pytest.raises(BizException) as exc_info:
        await service._append_ai_players("room-1", meta, members, 1)
    assert exc_info.value.code == ErrorCode.SYSTEM_ERROR.code
    assert len(deleted_player_ids) == 1
    assert meta["aiCount"] == 0
    assert meta["roomConfig"]["aiPlayerIds"] == []
    assert meta["updatedAt"] == 100


@pytest.mark.asyncio
async def test_start_managed_mode_does_not_push_room_list_updated() -> None:
    """startManagedMode 仅改托管状态，不推 roomListUpdated。"""
    service = _build_service()
    playing_meta = {"status": "playing", "gameCode": "uno", "ownerPlayerId": "u1"}
    service._require_meta = AsyncMock(return_value=playing_meta)
    service._require_playing_room = MagicMock()
    service._repository.list_players = AsyncMock(
        return_value=[
            {
                "playerId": "u1",
                "isManaged": False,
                "managedMode": None,
                "isAi": False,
            },
        ],
    )
    service.push_current_game_view_if_playing = AsyncMock()
    service.create_current_player_managed_task_if_needed = AsyncMock()
    account = MagicMock()
    account.server_id = "u1"
    with patch("app.modules.room.module_service.push_room_updated", new=AsyncMock()) as room_mock, patch(
        "app.modules.room.module_service.push_room_list_updated",
        new=AsyncMock(),
    ) as list_mock:
        await service.start_managed_mode(account, "room-1")
    room_mock.assert_awaited_once()
    list_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_stop_managed_mode_does_not_push_room_list_updated() -> None:
    """stopManagedMode 仅改托管状态，不推 roomListUpdated。"""
    service = _build_service()
    playing_meta = {"status": "playing", "gameCode": "uno", "ownerPlayerId": "u1"}
    service._require_meta = AsyncMock(return_value=playing_meta)
    service._require_playing_room = MagicMock()
    service._repository.list_players = AsyncMock(
        return_value=[
            {
                "playerId": "u1",
                "isManaged": True,
                "managedMode": "active",
                "managedReason": "manual",
                "isAi": False,
            },
        ],
    )
    service.push_current_game_view_if_playing = AsyncMock()
    service.create_current_player_managed_task_if_needed = AsyncMock()
    account = MagicMock()
    account.server_id = "u1"
    with patch("app.modules.room.module_service.push_room_updated", new=AsyncMock()) as room_mock, patch(
        "app.modules.room.module_service.push_room_list_updated",
        new=AsyncMock(),
    ) as list_mock:
        await service.stop_managed_mode(account, "room-1")
    room_mock.assert_awaited_once()
    list_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_submit_action_game_over_delete_uses_bumped_version_not_redis() -> None:
    """对局结束删除房间时最后 GameView version 来自 bump，删除后不再读 Redis version。"""
    service = _build_service()
    service._require_meta = AsyncMock(
        return_value={
            "status": "playing",
            "gameCode": "uno",
            "ownerPlayerId": "ai-1",
        },
    )
    service._require_playing_room = MagicMock()
    service._repository.list_players = AsyncMock(
        return_value=[
            {"playerId": "ai-1", "isAi": True, "isManaged": False},
            {"playerId": "ai-2", "isAi": True, "isManaged": False},
        ],
    )
    game_over_snapshot = _runtime_snapshot(player_ids=["ai-1", "ai-2"])
    game_over_snapshot = game_over_snapshot.model_copy(update={"isGameOver": True})
    service._load_runtime_snapshot = AsyncMock(return_value=game_over_snapshot)
    service._runtime_service.apply_player_action = MagicMock(
        return_value=MagicMock(snapshot=game_over_snapshot, newEvents=[]),
    )
    service._repository.clear_match_runtime = AsyncMock()
    service._repository.remove_playing_room = AsyncMock()
    service._clear_managed_shell_indexes = AsyncMock()
    service._repository.delete_room_cascade = AsyncMock()
    service._repository.get_version = AsyncMock(return_value=0)
    service._bump_version = AsyncMock(return_value=11)
    captured_versions = []

    def _enrich(snapshot, player_id, version, events):
        del snapshot, player_id, events
        captured_versions.append(version)
        return GameView(
            gameCode="uno",
            roomId="room-1",
            viewerPlayerId="ai-1",
            phase="play",
            version=version,
            isGameOver=True,
        )

    service._enrich_game_view = MagicMock(side_effect=_enrich)
    list_mock = AsyncMock()
    with patch("app.modules.room.module_service.push_room_list_updated", new=list_mock):
        await service._submit_action_locked("room-1", "ai-1", "draw", None)
    service._repository.get_version.assert_not_awaited()
    service._bump_version.assert_awaited_once()
    list_mock.assert_awaited_once_with("uno")
    assert captured_versions == [11]


@pytest.mark.asyncio
async def test_list_rooms_waiting_shell_cleanup_deletes_managed_shell_index() -> None:
    """list_rooms 清理 waiting shell 成员时同步删除 managed shell 索引。"""
    service = _build_service()
    service._game_service = MagicMock()
    service._game_service.get_game_rule_definition = MagicMock()
    service._repository.list_game_room_ids = AsyncMock(return_value=["room-shell-wait"])
    service._repository.get_meta = AsyncMock(
        return_value={
            "roomId": "room-shell-wait",
            "roomName": "房间",
            "gameCode": "uno",
            "mode": "classic",
            "ownerPlayerId": "u1",
            "ownerNickname": "u1",
            "maxPlayers": 4,
            "aiCount": 0,
            "status": "waiting",
            "createdAt": 1,
            "updatedAt": 2,
        }
    )
    service._repository.list_players = AsyncMock(
        return_value=[
            {
                "playerId": "u1",
                "nickname": "u1",
                "joinedAt": 1,
                "isAi": False,
                "isManaged": False,
            },
            {
                "playerId": "shell-u",
                "nickname": "shell",
                "joinedAt": 2,
                "isAi": False,
                "isManaged": True,
                "managedMode": "shell",
            },
        ]
    )
    service._cleanup_invalid_player_room_indexes = AsyncMock()
    service._bump_version = AsyncMock(return_value=2)
    service._repository.delete_player = AsyncMock(return_value=True)
    service._repository.delete_player_room = AsyncMock(return_value=True)
    service._repository.save_meta = AsyncMock(return_value=True)
    service._build_room_list_item = MagicMock()
    service._build_room_response = MagicMock(return_value=MagicMock())
    with patch("app.modules.room.module_service.push_room_updated", new=AsyncMock()) as room_mock, patch(
        "app.modules.room.module_service.push_room_list_updated",
        new=AsyncMock(),
    ) as list_mock:
        await service.list_rooms("uno")
    service._repository.delete_managed_shell_room_index.assert_awaited_once_with(
        "shell-u",
        "uno",
    )
    room_mock.assert_awaited_once()
    list_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_rooms_waiting_shell_cleanup_delete_room_pushes_list_only() -> None:
    """list_rooms 清理后无真人时删除房间，仅推 roomListUpdated。"""
    service = _build_service()
    service._game_service = MagicMock()
    service._game_service.get_game_rule_definition = MagicMock()
    service._repository.list_game_room_ids = AsyncMock(return_value=["room-ai-only"])
    service._repository.get_meta = AsyncMock(
        return_value={
            "roomId": "room-ai-only",
            "gameCode": "uno",
            "status": "waiting",
            "createdAt": 1,
            "updatedAt": 2,
        }
    )
    service._repository.list_players = AsyncMock(
        return_value=[
            {
                "playerId": "ai-1",
                "isAi": True,
                "isManaged": False,
            },
            {
                "playerId": "shell-u",
                "isAi": False,
                "isManaged": True,
                "managedMode": "shell",
            },
        ]
    )
    service._cleanup_invalid_player_room_indexes = AsyncMock()
    service._bump_version = AsyncMock(return_value=3)
    service._repository.delete_player = AsyncMock(return_value=True)
    service._repository.delete_player_room = AsyncMock(return_value=True)
    service._repository.save_meta = AsyncMock(return_value=True)
    service._clear_managed_shell_indexes = AsyncMock()
    service._repository.delete_room_cascade = AsyncMock()
    with patch("app.modules.room.module_service.push_room_updated", new=AsyncMock()) as room_mock, patch(
        "app.modules.room.module_service.push_room_list_updated",
        new=AsyncMock(),
    ) as list_mock:
        result = await service.list_rooms("uno")
    assert result == []
    list_mock.assert_awaited_once_with("uno")
    room_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_managed_task_service_enqueue_dedupe_logs_debug_not_warning() -> None:
    """enqueue_task dedupe 命中仅 debug，不 warning。"""
    repository = MagicMock()
    repository.enqueue_task = AsyncMock(return_value=ManagedTaskEnqueueResult(duplicated=True))
    task_service = ManagedTurnTaskService(repository)
    task = _sample_task()
    with patch("app.modules.room.managed_task_service.logger") as logger_mock:
        result = await task_service.enqueue_task(task)
        assert result.duplicated is True
        logger_mock.debug.assert_called_once()
        logger_mock.warning.assert_not_called()


