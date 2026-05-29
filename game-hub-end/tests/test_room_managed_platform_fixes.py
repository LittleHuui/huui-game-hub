"""房间托管修复与 add_room_ai 平台能力测试。"""

import asyncio
import inspect
import json
from types import MethodType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.modules.room.repository import RoomRepository
from app.core.redis.redis_client import redis_client
from app.core.redis.redis_keys import RedisKeys
from app.core.websocket.message_types import MessageType
from app.main import app
from app.modules.room import realtime_service
from app.modules.room.managed_task_repository import ManagedTaskEnqueueResult, ManagedTaskRepository
from app.modules.room.managed_task_service import ManagedTurnTaskService
from app.modules.room.module_service import RoomModuleService
from app.modules.room.schemas import RoomMemberResponse, RoomResponse
from app.modules.strategy_turn.schemas import GameView, RuntimeSnapshot, StrategyTurnRuntimeRule
from tests.sync_helpers import create_test_user
from tests.test_room_background_and_managed_tasks import (
    MANAGED_TASK_VISIBILITY_TIMEOUT_MS,
    _FakeRedisClient,
    _sample_task,
)
from tests.test_uno_room_flow import (
    ROOMS_PATH,
    _assert_api_error,
    _assert_api_success,
    _require_redis,
    _user_headers,
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


def test_add_room_ai_waiting_owner_success() -> None:
    """房主在 waiting 房间可添加 AI，成员字段与 meta 正确。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="AI房主")
        guest_id = create_test_user(client, nickname="客人")
        create_data = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": "uno", "mode": "classic"},
                headers=_user_headers(owner_id),
            )
        )
        room_id = create_data["roomId"]
        _assert_api_success(
            client.post(
                "{0}/{1}/join".format(ROOMS_PATH, room_id),
                headers=_user_headers(guest_id),
            )
        )
        ai_data = _assert_api_success(
            client.post(
                "{0}/{1}/ai".format(ROOMS_PATH, room_id),
                headers=_user_headers(owner_id),
            )
        )
        ai_members = [item for item in ai_data["members"] if item.get("isAi")]
        assert len(ai_members) == 1
        ai_member = ai_members[0]
        assert ai_member["isManaged"] is True
        assert ai_member["managedMode"] == "active"
        assert ai_member["managedReason"] == "ai"
        assert ai_data["aiCount"] == 1
        assert ai_data["memberCount"] == 3
        ai_player_id = ai_member["playerId"]

        loop = asyncio.new_event_loop()
        try:
            meta = loop.run_until_complete(redis_client.get_json(RedisKeys.room_meta(room_id)))
            player_room = loop.run_until_complete(
                redis_client.get_string(RedisKeys.player_room(ai_player_id)),
            )
        finally:
            loop.close()
        assert isinstance(meta, dict)
        assert meta.get("roomConfig", {}).get("aiPlayerIds") == [ai_player_id]
        assert meta.get("aiCount") == 1
        assert player_room is None


def test_add_room_ai_rejects_non_owner() -> None:
    """非房主不能添加 AI。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="房主")
        guest_id = create_test_user(client, nickname="非房主")
        create_data = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": "uno", "mode": "classic"},
                headers=_user_headers(owner_id),
            )
        )
        room_id = create_data["roomId"]
        _assert_api_success(
            client.post(
                "{0}/{1}/join".format(ROOMS_PATH, room_id),
                headers=_user_headers(guest_id),
            )
        )
        resp = client.post(
            "{0}/{1}/ai".format(ROOMS_PATH, room_id),
            headers=_user_headers(guest_id),
        )
        _assert_api_error(resp, ErrorCode.PARAM_ERROR.code)


def test_add_room_ai_rejects_playing_room() -> None:
    """playing 房间不能添加 AI。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="对局房主")
        guest_id = create_test_user(client, nickname="对局客人")
        create_data = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": "uno", "mode": "classic"},
                headers=_user_headers(owner_id),
            )
        )
        room_id = create_data["roomId"]
        _assert_api_success(
            client.post(
                "{0}/{1}/join".format(ROOMS_PATH, room_id),
                headers=_user_headers(guest_id),
            )
        )
        _assert_api_success(
            client.post(
                "{0}/{1}/start".format(ROOMS_PATH, room_id),
                headers=_user_headers(owner_id),
            )
        )
        resp = client.post(
            "{0}/{1}/ai".format(ROOMS_PATH, room_id),
            headers=_user_headers(owner_id),
        )
        _assert_api_error(resp, ErrorCode.ROOM_ALREADY_STARTED.code)


def test_add_room_ai_rejects_when_full() -> None:
    """满员房间不能添加 AI。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="满员房主")
        create_data = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": "uno", "mode": "classic", "roomConfig": {}},
                headers=_user_headers(owner_id),
            )
        )
        room_id = create_data["roomId"]
        max_players = int(create_data["maxPlayers"])
        for index in range(max_players - 1):
            guest_id = create_test_user(client, nickname="客人{0}".format(index))
            _assert_api_success(
                client.post(
                    "{0}/{1}/join".format(ROOMS_PATH, room_id),
                    headers=_user_headers(guest_id),
                )
            )
        resp = client.post(
            "{0}/{1}/ai".format(ROOMS_PATH, room_id),
            headers=_user_headers(owner_id),
        )
        _assert_api_error(resp, ErrorCode.ROOM_FULL.code)


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


def test_add_room_ai_rejects_when_max_ai_count_reached() -> None:
    """AI 数量达到 maxAiCount 时不能再添加。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="AI上限房主")
        create_data = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": "uno", "mode": "classic"},
                headers=_user_headers(owner_id),
            )
        )
        room_id = create_data["roomId"]
        for _ in range(9):
            _assert_api_success(
                client.post(
                    "{0}/{1}/ai".format(ROOMS_PATH, room_id),
                    headers=_user_headers(owner_id),
                )
            )
        resp = client.post(
            "{0}/{1}/ai".format(ROOMS_PATH, room_id),
            headers=_user_headers(owner_id),
        )
        _assert_api_error(resp, ErrorCode.PARAM_ERROR.code)


def test_leave_room_dissolves_when_only_ai_remains() -> None:
    """真人全部离开后只剩 AI 时房间解散。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="AI房房主")
        create_data = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": "uno", "mode": "classic"},
                headers=_user_headers(owner_id),
            )
        )
        room_id = create_data["roomId"]
        _assert_api_success(
            client.post(
                "{0}/{1}/ai".format(ROOMS_PATH, room_id),
                headers=_user_headers(owner_id),
            )
        )
        leave_data = _assert_api_success(
            client.post(
                "{0}/{1}/leave".format(ROOMS_PATH, room_id),
                headers=_user_headers(owner_id),
            )
        )
        assert leave_data["dissolved"] is True
        assert leave_data["room"] is None


def test_leave_room_owner_transfers_to_human_not_ai() -> None:
    """房主离开时转移给最早真人，不转给 AI。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="转移房主")
        guest_id = create_test_user(client, nickname="转移客人")
        create_data = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": "uno", "mode": "classic"},
                headers=_user_headers(owner_id),
            )
        )
        room_id = create_data["roomId"]
        _assert_api_success(
            client.post(
                "{0}/{1}/join".format(ROOMS_PATH, room_id),
                headers=_user_headers(guest_id),
            )
        )
        _assert_api_success(
            client.post(
                "{0}/{1}/ai".format(ROOMS_PATH, room_id),
                headers=_user_headers(owner_id),
            )
        )
        _assert_api_success(
            client.post(
                "{0}/{1}/leave".format(ROOMS_PATH, room_id),
                headers=_user_headers(owner_id),
            )
        )
        detail = _assert_api_success(
            client.get(
                "{0}/{1}".format(ROOMS_PATH, room_id),
                headers=_user_headers(guest_id),
            )
        )
        assert detail["ownerPlayerId"] == guest_id


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


def test_list_rooms_deletes_ai_only_waiting_room() -> None:
    """waiting 房间只剩 AI 时 list_rooms 删除房间且不返回。"""
    import time

    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="AI残留房主")
        create_data = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": "uno", "mode": "classic"},
                headers=_user_headers(owner_id),
            )
        )
        room_id = create_data["roomId"]
        ai_data = _assert_api_success(
            client.post(
                "{0}/{1}/ai".format(ROOMS_PATH, room_id),
                headers=_user_headers(owner_id),
            )
        )
        ai_player_id = next(
            item["playerId"] for item in ai_data["members"] if item.get("isAi")
        )
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                redis_client.hdel(RedisKeys.room_players(room_id), owner_id)
            )
            loop.run_until_complete(
                redis_client.set_json(
                    RedisKeys.room_meta(room_id),
                    {
                        "roomId": room_id,
                        "roomName": "AI残留房",
                        "gameCode": "uno",
                        "mode": "classic",
                        "ownerPlayerId": owner_id,
                        "ownerNickname": "AI残留房主",
                        "maxPlayers": 4,
                        "aiCount": 1,
                        "status": "waiting",
                        "roomConfig": {"aiPlayerIds": [ai_player_id]},
                        "createdAt": int(time.time() * 1000),
                        "updatedAt": int(time.time() * 1000),
                    },
                    120,
                )
            )
            loop.run_until_complete(redis_client.sadd(RedisKeys.game_rooms("uno"), room_id, 120))
        finally:
            loop.close()

        room_list = _assert_api_success(client.get(ROOMS_PATH, params={"gameCode": "uno"}))
        assert all(item["roomId"] != room_id for item in room_list)
        loop = asyncio.new_event_loop()
        try:
            assert loop.run_until_complete(redis_client.get_json(RedisKeys.room_meta(room_id))) is None
        finally:
            loop.close()
