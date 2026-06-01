"""Room managed platform Redis / TestClient integration tests."""

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from app.common.error_code import ErrorCode
from app.core.redis.redis_client import redis_client
from app.core.redis.redis_keys import RedisKeys
from app.main import app
from tests.sync_helpers import create_test_user
from tests.integration.test_uno_room_flow import (
    ROOMS_PATH,
    _assert_api_error,
    _assert_api_success,
    _require_redis,
    _user_headers,
)

pytestmark = pytest.mark.integration


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
