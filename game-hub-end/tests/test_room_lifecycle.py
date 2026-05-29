"""房间生命周期与活跃房间查询集成测试（依赖 Redis）。"""

import time
from typing import Any, Dict, Optional

import pytest
from fastapi.testclient import TestClient

from app.core.redis.redis_client import redis_client
from app.core.redis.redis_keys import RedisKeys
from app.main import app
from tests.sync_helpers import create_test_user
from tests.test_uno_room_flow import (
    ROOMS_PATH,
    _assert_api_error,
    _assert_api_success,
    _collect_room_key_exists,
    _pick_current_player_action,
    _require_redis,
    _user_headers,
)

MY_ACTIVE_PATH = ROOMS_PATH + "/my-active"


def _get_my_active(client: TestClient, user_id: str) -> Optional[Dict[str, Any]]:
    """
    查询当前用户活跃房间。

    :param client: 测试客户端。
    :param user_id: 用户 ID。
    :return: 活跃房间详情；无则 ``None``。
    """
    resp = client.get(MY_ACTIVE_PATH, headers=_user_headers(user_id))
    data = _assert_api_success(resp)
    return data.get("room")


def test_get_my_active_room_no_room() -> None:
    """无 player_room 索引时返回 room=null。"""
    _require_redis()
    with TestClient(app) as client:
        user_id = create_test_user(client, nickname="无房玩家")
        assert _get_my_active(client, user_id) is None


def test_get_my_active_room_waiting_and_playing() -> None:
    """玩家在 waiting / playing 房间时返回房间详情。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="活跃房主")
        guest_id = create_test_user(client, nickname="活跃客人")

        create_data = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": "uno", "mode": "classic"},
                headers=_user_headers(owner_id),
            )
        )
        room_id = create_data["roomId"]

        waiting_room = _get_my_active(client, owner_id)
        assert waiting_room is not None
        assert waiting_room["roomId"] == room_id
        assert waiting_room["status"] == "waiting"

        _assert_api_success(
            client.post(
                "{0}/{1}/join".format(ROOMS_PATH, room_id),
                headers=_user_headers(guest_id),
            )
        )
        guest_active = _get_my_active(client, guest_id)
        assert guest_active is not None
        assert guest_active["status"] == "waiting"

        _assert_api_success(
            client.post(
                "{0}/{1}/start".format(ROOMS_PATH, room_id),
                headers=_user_headers(owner_id),
            )
        )
        playing_room = _get_my_active(client, owner_id)
        assert playing_room is not None
        assert playing_room["status"] == "playing"


def test_get_my_active_room_cross_game_semantics() -> None:
    """活跃房间查询按跨游戏唯一语义返回。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="跨游戏房主")
        create_data = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": "uno", "mode": "classic"},
                headers=_user_headers(owner_id),
            )
        )
        room_id = create_data["roomId"]
        still_uno = _get_my_active(client, owner_id)
        assert still_uno is not None
        assert still_uno["roomId"] == room_id


def test_create_room_rejects_when_player_already_in_other_room() -> None:
    """已在活跃房间时创建新房间会被拒绝。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="已在房间玩家")
        _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": "uno", "mode": "classic"},
                headers=_user_headers(owner_id),
            )
        )
        second_create = client.post(
            ROOMS_PATH,
            json={"gameCode": "uno", "mode": "classic"},
            headers=_user_headers(owner_id),
        )
        _assert_api_error(second_create, 90006)


def test_get_my_active_room_cleans_stale_player_room_index() -> None:
    """房间不存在或用户不在成员中时清理脏 player_room 索引。"""
    _require_redis()
    with TestClient(app) as client:
        user_id = create_test_user(client, nickname="脏索引玩家")
        fake_room_id = "room-stale-{0}".format(int(time.time() * 1000))

        import asyncio

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(redis_client.set_string(RedisKeys.player_room(user_id), fake_room_id, 60))
        finally:
            loop.close()

        assert _get_my_active(client, user_id) is None

        loop = asyncio.new_event_loop()
        try:
            indexed = loop.run_until_complete(redis_client.get_string(RedisKeys.player_room(user_id)))
        finally:
            loop.close()
        assert indexed is None


def test_playing_leave_owner_transfer_and_dissolve() -> None:
    """playing 状态离开：房主转移、最后一人离开后房间删除。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="对局房主")
        player_a_id = create_test_user(client, nickname="对局玩家A")
        player_b_id = create_test_user(client, nickname="对局玩家B")

        create_data = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": "uno", "mode": "classic"},
                headers=_user_headers(owner_id),
            )
        )
        room_id = create_data["roomId"]

        time.sleep(0.01)
        _assert_api_success(
            client.post(
                "{0}/{1}/join".format(ROOMS_PATH, room_id),
                headers=_user_headers(player_a_id),
            )
        )
        time.sleep(0.01)
        _assert_api_success(
            client.post(
                "{0}/{1}/join".format(ROOMS_PATH, room_id),
                headers=_user_headers(player_b_id),
            )
        )
        _assert_api_success(
            client.post(
                "{0}/{1}/start".format(ROOMS_PATH, room_id),
                headers=_user_headers(owner_id),
            )
        )

        leave_owner = _assert_api_success(
            client.post(
                "{0}/{1}/leave".format(ROOMS_PATH, room_id),
                headers=_user_headers(owner_id),
            )
        )
        assert leave_owner["dissolved"] is False
        assert leave_owner["room"]["status"] == "playing"
        assert leave_owner["room"]["ownerPlayerId"] == player_a_id

        leave_b = _assert_api_success(
            client.post(
                "{0}/{1}/leave".format(ROOMS_PATH, room_id),
                headers=_user_headers(player_b_id),
            )
        )
        assert leave_b["dissolved"] is False
        assert leave_b["room"]["memberCount"] == 1

        leave_last = _assert_api_success(
            client.post(
                "{0}/{1}/leave".format(ROOMS_PATH, room_id),
                headers=_user_headers(player_a_id),
            )
        )
        assert leave_last["dissolved"] is True
        assert leave_last["room"] is None

        get_deleted = client.get("{0}/{1}".format(ROOMS_PATH, room_id))
        _assert_api_error(get_deleted, 90001)


def test_game_over_room_returns_to_waiting_and_can_restart() -> None:
    """对局结束后房间回到 waiting，可再次开局，且运行时 key 被清理。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="结算房主")
        guest_id = create_test_user(client, nickname="结算客人")

        create_data = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={
                    "gameCode": "uno",
                    "mode": "classic",
                    "roomConfig": {"finishMode": "FIRST_FINISH"},
                },
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
        start_view = _assert_api_success(
            client.post(
                "{0}/{1}/start".format(ROOMS_PATH, room_id),
                headers=_user_headers(owner_id),
            )
        )
        assert start_view["isGameOver"] is False

        view = start_view
        finished = False
        for seq in range(1, 301):
            if view.get("isGameOver"):
                finished = True
                break
            current_player_id = view.get("currentPlayerId")
            legal_actions = view.get("legalActions") or []
            if not current_player_id or not legal_actions:
                break
            _, action_id = _pick_current_player_action(view)
            view = _assert_api_success(
                client.post(
                    "{0}/{1}/actions".format(ROOMS_PATH, room_id),
                    headers=_user_headers(current_player_id),
                    json={
                        "actionId": action_id,
                        "baseVersion": view["version"],
                        "clientSeq": seq,
                    },
                )
            )

        assert finished is True
        assert view.get("isGameOver") is True

        room_after = _assert_api_success(client.get("{0}/{1}".format(ROOMS_PATH, room_id)))
        assert room_after["status"] == "waiting"

        import asyncio

        loop = asyncio.new_event_loop()
        try:
            key_snapshot = loop.run_until_complete(_collect_room_key_exists(room_id, "uno"))
        finally:
            loop.close()
        assert key_snapshot["runtime"] is False
        assert key_snapshot["public_state"] is False
        assert key_snapshot["events"] is False

        restart_view = _assert_api_success(
            client.post(
                "{0}/{1}/start".format(ROOMS_PATH, room_id),
                headers=_user_headers(owner_id),
            )
        )
        assert restart_view["phase"] == "playing"
        assert restart_view["isGameOver"] is False


def test_list_rooms_cleans_zero_member_room() -> None:
    """房间索引存在但成员为空时，list_rooms 会删除该房间。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="零成员房主")
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
                "{0}/{1}/leave".format(ROOMS_PATH, room_id),
                headers=_user_headers(owner_id),
            )
        )
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                redis_client.set_json(
                    RedisKeys.room_meta(room_id),
                    {
                        "roomId": room_id,
                        "roomName": "零成员房",
                        "gameCode": "uno",
                        "mode": "classic",
                        "ownerPlayerId": owner_id,
                        "ownerNickname": "零成员房主",
                        "maxPlayers": 4,
                        "aiCount": 0,
                        "status": "waiting",
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


def test_playing_rooms_set_add_and_remove() -> None:
    """房间开局加入 playing set，结算回 waiting 后移除。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="playing-set-owner")
        guest_id = create_test_user(client, nickname="playing-set-guest")
        room = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": "uno", "mode": "classic"},
                headers=_user_headers(owner_id),
            )
        )
        room_id = room["roomId"]
        _assert_api_success(client.post("{0}/{1}/join".format(ROOMS_PATH, room_id), headers=_user_headers(guest_id)))
        start_view = _assert_api_success(
            client.post("{0}/{1}/start".format(ROOMS_PATH, room_id), headers=_user_headers(owner_id))
        )
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            playing_ids = loop.run_until_complete(redis_client.smembers(RedisKeys.playing_rooms()))
        finally:
            loop.close()
        assert room_id in playing_ids

        view = start_view
        for seq in range(1, 301):
            if view.get("isGameOver"):
                break
            current_player_id = view.get("currentPlayerId")
            _, action_id = _pick_current_player_action(view)
            view = _assert_api_success(
                client.post(
                    "{0}/{1}/actions".format(ROOMS_PATH, room_id),
                    headers=_user_headers(current_player_id),
                    json={"actionId": action_id, "baseVersion": view["version"], "clientSeq": seq},
                )
            )
        assert view.get("isGameOver") is True

        loop = asyncio.new_event_loop()
        try:
            playing_ids = loop.run_until_complete(redis_client.smembers(RedisKeys.playing_rooms()))
        finally:
            loop.close()
        assert room_id not in playing_ids


def test_start_managed_mode_blocks_manual_action_and_triggers_delayed_submit() -> None:
    """当前行动玩家开启托管后，手动提交被拒绝，并在延迟后自动推进一手。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="托管房主")
        guest_id = create_test_user(client, nickname="托管客人")
        room = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": "uno", "mode": "classic"},
                headers=_user_headers(owner_id),
            )
        )
        room_id = room["roomId"]
        _assert_api_success(client.post("{0}/{1}/join".format(ROOMS_PATH, room_id), headers=_user_headers(guest_id)))
        start_view = _assert_api_success(
            client.post("{0}/{1}/start".format(ROOMS_PATH, room_id), headers=_user_headers(owner_id))
        )
        current_player_id = start_view["currentPlayerId"]
        managed_room = _assert_api_success(
            client.post(
                "{0}/{1}/managed/start".format(ROOMS_PATH, room_id),
                headers=_user_headers(current_player_id),
            )
        )
        current_member = next(item for item in managed_room["members"] if item["playerId"] == current_player_id)
        assert current_member["isManaged"] is True
        view_after_managed = _assert_api_success(
            client.get("{0}/{1}/view".format(ROOMS_PATH, room_id), headers=_user_headers(current_player_id))
        )
        _, action_id = _pick_current_player_action(view_after_managed)
        manual_action = client.post(
            "{0}/{1}/actions".format(ROOMS_PATH, room_id),
            headers=_user_headers(current_player_id),
            json={"actionId": action_id, "baseVersion": view_after_managed["version"], "clientSeq": 1},
        )
        _assert_api_error(manual_action, 90007)
        before_version = view_after_managed["version"]
        time.sleep(1.3)
        view_after_auto = _assert_api_success(
            client.get("{0}/{1}/view".format(ROOMS_PATH, room_id), headers=_user_headers(current_player_id))
        )
        assert view_after_auto["version"] > before_version
