"""审查项修复回归测试。"""

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.lock.distributed_lock import LockAcquireError
from app.core.redis.redis_keys import RedisKeys
from app.core.websocket.message_types import MessageType
from app.modules.room.managed_task_repository import ManagedTaskRepository
from app.modules.room.managed_task_service import (
    MANAGED_TASK_PERMANENT_SKIP_REASONS,
    MANAGED_TASK_TEMPORARY_FAILURE_REASONS,
    ManagedTaskSubmitResult,
    ManagedTurnTask,
    ManagedTurnTaskService,
)
from app.modules.room.module_service import RoomModuleService
from app.modules.room.presence_service import RoomPresenceService
from app.modules.room.schemas import RoomMemberResponse, RoomResponse
from app.modules.strategy_turn.schemas import GameView, RuntimeSnapshot, StrategyTurnRuntimeRule


class _FakeLock(object):
    """异步锁占位。"""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


def _runtime_snapshot(current_player_id: str = "u1") -> RuntimeSnapshot:
    return RuntimeSnapshot(
        gameCode="uno",
        roomId="room-1",
        runtimeRule=StrategyTurnRuntimeRule(
            gameCode="uno",
            mode="classic",
            playerIds=["u1", "u2"],
            config={},
        ),
        state={"currentPlayerId": current_player_id},
        eventLog=[],
        eventSequence=0,
        startedAt=1,
        updatedAt=1,
        isGameOver=False,
    )


def _sample_room_response(version: int = 7) -> RoomResponse:
    return RoomResponse(
        roomId="room-1",
        roomName="房间-1",
        gameCode="uno",
        mode="classic",
        ownerPlayerId="u2",
        ownerNickname="u2",
        maxPlayers=4,
        aiCount=0,
        version=version,
        status="playing",
        memberCount=1,
        members=[
            RoomMemberResponse(
                playerId="u2",
                nickname="u2",
                joinedAt=2,
                isAi=False,
                isManaged=False,
                managedMode=None,
            ),
        ],
        createdAt=1,
        updatedAt=2,
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
    service._bump_version = AsyncMock(return_value=7)
    service._repository.refresh_room_ttl = AsyncMock()
    service._repository.save_player = AsyncMock(return_value=True)
    service._repository.save_meta = AsyncMock(return_value=True)
    service._repository.delete_player_room = AsyncMock()
    service._load_runtime_snapshot = AsyncMock(return_value=_runtime_snapshot())
    service._extract_current_player_id = MagicMock(return_value="u1")
    service.create_managed_turn_task = AsyncMock()
    service.create_current_player_managed_task_if_needed = AsyncMock()
    service._build_room_response = MagicMock(side_effect=lambda meta, members, version: _sample_room_response(version))
    service._repository.get_player_room = AsyncMock(return_value=None)
    service._repository.save_player_room = AsyncMock(return_value=True)
    def _enrich_game_view(snapshot, player_id, version, events):
        del snapshot, events
        return GameView(
            gameCode="uno",
            roomId="room-1",
            viewerPlayerId=player_id,
            phase="turn",
            version=version,
            publicState={},
            privateState={},
            legalActions=[],
            events=[],
        )

    service._enrich_game_view = _enrich_game_view
    return service


@pytest.mark.parametrize(
    "method_name,setup",
    [
        ("start_managed_mode", {"_require_playing_room": MagicMock()}),
        ("stop_managed_mode", {"_require_playing_room": MagicMock()}),
        ("rejoin_managed_room", {}),
    ],
)
@pytest.mark.asyncio
async def test_non_action_bump_pushes_game_view_updated(method_name, setup) -> None:
    """托管状态变更 bump version 后推送 gameViewUpdated。"""
    service = _build_service()
    for attr, value in setup.items():
        setattr(service, attr, value)
    service._require_meta = AsyncMock(
        return_value={
            "status": "playing",
            "gameCode": "uno",
            "ownerPlayerId": "u2",
            "ownerNickname": "u2",
        },
    )
    members = [
        {
            "playerId": "u1",
            "nickname": "u1",
            "joinedAt": 1,
            "isAi": False,
            "isManaged": method_name == "stop_managed_mode",
            "managedMode": "active" if method_name == "stop_managed_mode" else None,
        },
        {
            "playerId": "u2",
            "nickname": "u2",
            "joinedAt": 2,
            "isAi": False,
            "isManaged": False,
            "managedMode": None,
        },
    ]
    service._repository.list_players = AsyncMock(return_value=members)
    pushed_views = []

    async def _capture_push(room_id, views, members):
        del room_id, members
        pushed_views.append(views)

    with patch(
        "app.modules.room.module_service.push_room_updated",
        new=AsyncMock(),
    ), patch(
        "app.modules.room.module_service.push_room_list_updated",
        new=AsyncMock(),
    ), patch(
        "app.modules.room.module_service.push_game_view_updated",
        side_effect=_capture_push,
    ), patch(
        "app.modules.room.module_service.collect_human_player_ids",
        return_value=["u2"],
    ), patch(
        "app.modules.room.module_service.build_views_for_members",
        side_effect=lambda enrich, snapshot, version, events, player_ids: {
            pid: enrich(snapshot, pid, version, events) for pid in player_ids
        },
    ):
        account = MagicMock()
        account.server_id = "u1"
        if method_name == "start_managed_mode":
            await service.start_managed_mode(account, "room-1")
        elif method_name == "stop_managed_mode":
            await service.stop_managed_mode(account, "room-1")
        else:
            service._repository.list_players = AsyncMock(
                return_value=[
                    {
                        "playerId": "u1",
                        "joinedAt": 1,
                        "isAi": False,
                        "isManaged": True,
                        "managedMode": "shell",
                    },
                ],
            )
            await service.rejoin_managed_room(account, "room-1")

    assert pushed_views
    view = list(pushed_views[0].values())[0]
    assert view.version == 7


@pytest.mark.asyncio
async def test_mark_member_shell_managed_pushes_game_view_updated() -> None:
    """mark_member_shell_managed bump version 后推送 gameViewUpdated。"""
    service = _build_service()
    service._repository.get_meta = AsyncMock(
        return_value={"status": "playing", "gameCode": "uno", "ownerPlayerId": "u2"},
    )
    service._repository.list_players = AsyncMock(
        return_value=[
            {
                "playerId": "u1",
                "nickname": "u1",
                "joinedAt": 1,
                "isAi": False,
                "isManaged": False,
                "managedMode": None,
            },
            {
                "playerId": "u2",
                "nickname": "u2",
                "joinedAt": 2,
                "isAi": False,
                "isManaged": False,
                "managedMode": None,
            },
        ],
    )
    service._repository.save_player = AsyncMock(return_value=True)
    service._repository.get_runtime = AsyncMock(
        return_value={"runtimeState": {"currentPlayerId": "u2"}},
    )
    pushed_versions = []

    async def _capture_push(room_id, views, members):
        del room_id, members
        for view in views.values():
            pushed_versions.append(view.version)

    with patch(
        "app.modules.room.module_service.push_room_updated",
        new=AsyncMock(),
    ), patch(
        "app.modules.room.module_service.push_room_list_updated",
        new=AsyncMock(),
    ), patch(
        "app.modules.room.module_service.push_game_view_updated",
        side_effect=_capture_push,
    ), patch(
        "app.modules.room.module_service.collect_human_player_ids",
        return_value=["u2"],
    ), patch(
        "app.modules.room.module_service.build_views_for_members",
        side_effect=lambda enrich, snapshot, version, events, player_ids: {
            pid: enrich(snapshot, pid, version, events) for pid in player_ids
        },
    ):
        result = await service.mark_member_shell_managed("room-1", "u1", "timeout")

    assert result is True
    assert pushed_versions == [7]


@pytest.mark.asyncio
async def test_playing_leave_current_player_creates_managed_task() -> None:
    """playing 当前玩家离开时创建托管任务。"""
    service = _build_service()
    service._require_meta = AsyncMock(
        return_value={
            "status": "playing",
            "gameCode": "uno",
            "ownerPlayerId": "u1",
        },
    )
    service._repository.list_players = AsyncMock(
        side_effect=[
            [
                {"playerId": "u1", "joinedAt": 1, "isAi": False},
                {"playerId": "u2", "joinedAt": 2, "isAi": False},
            ],
            [
                {
                    "playerId": "u1",
                    "joinedAt": 1,
                    "isAi": False,
                    "isManaged": True,
                    "managedMode": "shell",
                },
                {"playerId": "u2", "joinedAt": 2, "isAi": False},
            ],
        ],
    )
    service._extract_current_player_id = MagicMock(return_value="u1")
    account = MagicMock()
    account.server_id = "u1"
    with patch("app.modules.room.module_service.push_room_updated", new=AsyncMock()), patch(
        "app.modules.room.module_service.push_room_list_updated",
        new=AsyncMock(),
    ), patch(
        "app.modules.room.module_service.push_game_view_updated",
        new=AsyncMock(),
    ):
        await service.leave_room(account, "room-1")
    service.create_current_player_managed_task_if_needed.assert_awaited_once_with(
        "room-1",
        "leave",
    )


@pytest.mark.asyncio
async def test_playing_leave_non_current_player_skips_managed_task() -> None:
    """playing 非当前玩家离开时不创建托管任务。"""
    service = _build_service()
    service._require_meta = AsyncMock(
        return_value={
            "status": "playing",
            "gameCode": "uno",
            "ownerPlayerId": "u1",
        },
    )
    service._repository.list_players = AsyncMock(
        side_effect=[
            [
                {"playerId": "u1", "joinedAt": 1, "isAi": False},
                {"playerId": "u2", "joinedAt": 2, "isAi": False},
            ],
            [
                {
                    "playerId": "u2",
                    "joinedAt": 2,
                    "isAi": False,
                    "isManaged": True,
                    "managedMode": "shell",
                },
                {"playerId": "u1", "joinedAt": 1, "isAi": False},
            ],
        ],
    )
    service._extract_current_player_id = MagicMock(return_value="u1")
    account = MagicMock()
    account.server_id = "u2"
    with patch("app.modules.room.module_service.push_room_updated", new=AsyncMock()), patch(
        "app.modules.room.module_service.push_room_list_updated",
        new=AsyncMock(),
    ), patch(
        "app.modules.room.module_service.push_game_view_updated",
        new=AsyncMock(),
    ):
        await service.leave_room(account, "room-1")
    service.create_managed_turn_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_mark_shell_lock_conflict_returns_false() -> None:
    """mark_member_shell_managed 锁冲突返回 False。"""
    service = _build_service()
    service._lock_service.acquire = AsyncMock(side_effect=LockAcquireError("busy"))
    result = await service.mark_member_shell_managed("room-1", "u1", "timeout")
    assert result is False


@pytest.mark.asyncio
async def test_presence_shell_success_deletes_state() -> None:
    """shell 标记成功后删除 presence state。"""
    presence = RoomPresenceService()
    presence.bind_mark_member_shell_managed_handler(AsyncMock(return_value=True))
    presence._repository = MagicMock()
    presence._repository.get_meta = AsyncMock(
        return_value={"status": "playing", "gameCode": "uno"},
    )
    presence._repository.list_players = AsyncMock(
        return_value=[{"playerId": "u1", "isAi": False, "managedMode": None}],
    )
    presence._repository.get_presence_state = AsyncMock(
        return_value={"sequence": 1, "missedCount": 2},
    )
    presence._repository.save_presence_state = AsyncMock()
    presence._repository.delete_presence_state = AsyncMock()
    with patch(
        "app.modules.room.presence_service.connection_manager.send_to_user",
        new=AsyncMock(return_value=True),
    ):
        await presence._tick_room("room-1")
    presence._repository.delete_presence_state.assert_awaited_once_with("room-1", "u1")


@pytest.mark.asyncio
async def test_presence_shell_failure_keeps_state() -> None:
    """shell 标记失败时保留 presence state。"""
    presence = RoomPresenceService()
    presence.bind_mark_member_shell_managed_handler(AsyncMock(return_value=False))
    presence._repository = MagicMock()
    presence._repository.get_meta = AsyncMock(
        return_value={"status": "playing", "gameCode": "uno"},
    )
    presence._repository.list_players = AsyncMock(
        return_value=[{"playerId": "u1", "isAi": False, "managedMode": None}],
    )
    presence._repository.get_presence_state = AsyncMock(
        return_value={"sequence": 1, "missedCount": 2},
    )
    presence._repository.save_presence_state = AsyncMock()
    presence._repository.delete_presence_state = AsyncMock()
    with patch(
        "app.modules.room.presence_service.connection_manager.send_to_user",
        new=AsyncMock(return_value=True),
    ):
        await presence._tick_room("room-1")
    presence._repository.delete_presence_state.assert_not_awaited()


def test_shell_managed_reasons_exclude_disconnect() -> None:
    """SHELL_MANAGED_REASONS 不含 disconnect。"""
    assert "disconnect" not in RoomModuleService.SHELL_MANAGED_REASONS


def test_managed_task_repository_has_no_legacy_enqueue_helpers() -> None:
    """托管仓库不再暴露 mark_task_running / add_due_task / list_room_tasks。"""
    assert not hasattr(ManagedTaskRepository, "mark_task_running")
    assert not hasattr(ManagedTaskRepository, "add_due_task")
    assert not hasattr(ManagedTaskRepository, "list_room_tasks")


def test_managed_task_service_has_no_list_room_tasks() -> None:
    """托管服务不再暴露 list_room_tasks。"""
    service = ManagedTurnTaskService()
    assert not hasattr(service, "list_room_tasks")


@pytest.mark.asyncio
async def test_temporary_failure_releases_dedupe() -> None:
    """临时失败任务释放 dedupe。"""
    fake_redis = MagicMock()
    fake_redis.eval = AsyncMock(return_value=1)
    repository = ManagedTaskRepository(fake_redis)
    service = ManagedTurnTaskService(repository=repository)
    task = ManagedTurnTask(
        taskId="task-temp",
        roomId="room-1",
        gameCode="uno",
        playerId="u1",
        expectedVersion=3,
        expectedCurrentPlayerId="u1",
        executeAfterMs=0,
        status="running",
        createdAt=1,
        reason="test",
        dedupeKey=RedisKeys.managed_task_dedupe("room-1", "u1", 3),
    )
    repository.get_task = AsyncMock(return_value=task.model_dump())
    repository.finalize_task = AsyncMock(return_value=True)
    for reason in MANAGED_TASK_TEMPORARY_FAILURE_REASONS:
        fake_redis.eval.reset_mock()
        await service._finish_task(task, "failed", reason)
        fake_redis.eval.assert_awaited()
    for reason in MANAGED_TASK_PERMANENT_SKIP_REASONS:
        fake_redis.eval.reset_mock()
        await service._finish_task(task, "skipped", reason)
        fake_redis.eval.assert_not_awaited()


def test_release_dedupe_only_when_owner_matches() -> None:
    """仅当 dedupe 仍指向当前 taskId 时释放。"""
    dedupe_key = RedisKeys.managed_task_dedupe("room-1", "u1", 1)
    store = {dedupe_key: "other-task"}

    class _Redis(object):
        async def eval(self, script, num_keys, keys, args):
            del script, num_keys
            key = keys[0]
            if store.get(key) == args[0]:
                store.pop(key, None)
                return 1
            return 0

    repository = ManagedTaskRepository(_Redis())

    async def _run():
        released = await repository.release_dedupe_if_owner(dedupe_key, "task-a")
        assert released is False
        assert dedupe_key in store
        store[dedupe_key] = "task-a"
        released = await repository.release_dedupe_if_owner(dedupe_key, "task-a")
        assert released is True
        assert dedupe_key not in store

    asyncio.run(_run())
