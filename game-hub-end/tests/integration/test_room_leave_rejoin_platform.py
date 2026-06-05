"""房间离开 / 重新加入平台语义集成测试（uno、gomoku 共用，无游戏特判）。"""

import asyncio
from typing import Any, Dict, List, Tuple

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

_PLATFORM_GAMES: List[Tuple[str, str]] = [
    ("uno", "classic"),
    ("gomoku", "standard"),
]


def _create_two_player_playing_room(
    client: TestClient,
    game_code: str,
    mode: str,
) -> Tuple[str, str, str]:
    """
    创建双人房间并开局。

    :param client: 测试客户端。
    :param game_code: 游戏编码。
    :param mode: 玩法模式。
    :return: ``(room_id, owner_id, guest_id)``。
    """
    owner_id = create_test_user(client, nickname="{0}-房主".format(game_code))
    guest_id = create_test_user(client, nickname="{0}-客人".format(game_code))
    create_data = _assert_api_success(
        client.post(
            ROOMS_PATH,
            json={"gameCode": game_code, "mode": mode},
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
    return room_id, owner_id, guest_id


def _find_member(members: list, player_id: str) -> Dict[str, Any]:
    """
    在成员列表中查找玩家。

    :param members: 成员列表。
    :param player_id: 玩家 ID。
    :return: 成员对象。
    """
    for item in members:
        if str(item.get("playerId", "")).strip() == player_id:
            return item
    raise AssertionError("member not found: {0}".format(player_id))


@pytest.mark.parametrize("game_code,mode", _PLATFORM_GAMES)
def test_waiting_leave_removes_member(game_code: str, mode: str) -> None:
    """waiting 房间 leave 后成员从房间移除。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="等待离开房主")
        guest_id = create_test_user(client, nickname="等待离开客人")
        create_data = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": game_code, "mode": mode},
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
        leave_data = _assert_api_success(
            client.post(
                "{0}/{1}/leave".format(ROOMS_PATH, room_id),
                headers=_user_headers(guest_id),
            )
        )
        assert leave_data["dissolved"] is False
        room = leave_data["room"]
        assert _find_member(room["members"], owner_id) is not None
        assert all(
            str(item.get("playerId", "")).strip() != guest_id for item in room["members"]
        )
        assert _get_my_active(client, guest_id) is None


@pytest.mark.parametrize("game_code,mode", _PLATFORM_GAMES)
def test_waiting_last_member_leave_deletes_room(game_code: str, mode: str) -> None:
    """waiting 房间最后一人 leave 后房间删除。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="最后离开房主")
        create_data = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": game_code, "mode": mode},
                headers=_user_headers(owner_id),
            )
        )
        room_id = create_data["roomId"]
        leave_data = _assert_api_success(
            client.post(
                "{0}/{1}/leave".format(ROOMS_PATH, room_id),
                headers=_user_headers(owner_id),
            )
        )
        assert leave_data["dissolved"] is True
        assert leave_data["room"] is None
        get_resp = client.get("{0}/{1}".format(ROOMS_PATH, room_id))
        _assert_api_error(get_resp, ErrorCode.ROOM_NOT_FOUND.code)


@pytest.mark.parametrize("game_code,mode", _PLATFORM_GAMES)
def test_playing_leave_keeps_shell_member_and_seat(game_code: str, mode: str) -> None:
    """playing 房间 leave 后成员保留席位并进入 shell 托管。"""
    _require_redis()
    with TestClient(app) as client:
        room_id, owner_id, guest_id = _create_two_player_playing_room(client, game_code, mode)
        before_room = _assert_api_success(client.get("{0}/{1}".format(ROOMS_PATH, room_id)))
        guest_before = _find_member(before_room["members"], guest_id)
        joined_at = guest_before["joinedAt"]

        leave_data = _assert_api_success(
            client.post(
                "{0}/{1}/leave".format(ROOMS_PATH, room_id),
                headers=_user_headers(guest_id),
            )
        )
        assert leave_data["dissolved"] is False
        assert leave_data["room"]["status"] == "playing"
        guest_after = _find_member(leave_data["room"]["members"], guest_id)
        assert guest_after["joinedAt"] == joined_at
        assert guest_after["isManaged"] is True
        assert guest_after["managedMode"] == "shell"
        assert guest_after["managedReason"] == "leave"
        assert _get_my_active(client, guest_id) is None

        loop = asyncio.new_event_loop()
        try:
            shell_index = loop.run_until_complete(
                redis_client.get_string(RedisKeys.player_managed_shell_room(guest_id, game_code))
            )
        finally:
            loop.close()
        assert shell_index == room_id


@pytest.mark.parametrize("game_code,mode", _PLATFORM_GAMES)
def test_playing_join_rejected_for_new_player(game_code: str, mode: str) -> None:
    """playing 房间禁止新玩家 join。"""
    _require_redis()
    with TestClient(app) as client:
        room_id, _, _ = _create_two_player_playing_room(client, game_code, mode)
        stranger_id = create_test_user(client, nickname="中途加入者")
        join_resp = client.post(
            "{0}/{1}/join".format(ROOMS_PATH, room_id),
            headers=_user_headers(stranger_id),
        )
        _assert_api_error(join_resp, ErrorCode.ROOM_ALREADY_STARTED.code)


@pytest.mark.parametrize("game_code,mode", _PLATFORM_GAMES)
def test_playing_original_member_rejoin_clears_shell(game_code: str, mode: str) -> None:
    """playing 房间原成员 rejoin 成功并取消 shell 托管。"""
    _require_redis()
    with TestClient(app) as client:
        room_id, owner_id, guest_id = _create_two_player_playing_room(client, game_code, mode)
        _assert_api_success(
            client.post(
                "{0}/{1}/leave".format(ROOMS_PATH, room_id),
                headers=_user_headers(guest_id),
            )
        )
        rejoin_room = _assert_api_success(
            client.post(
                "{0}/{1}/rejoin".format(ROOMS_PATH, room_id),
                headers=_user_headers(guest_id),
            )
        )
        guest_member = _find_member(rejoin_room["members"], guest_id)
        assert guest_member["isManaged"] is False
        assert guest_member.get("managedMode") in (None, "")
        active = _get_my_active(client, guest_id)
        assert active is not None
        assert active["roomId"] == room_id
        view_resp = client.get(
            "{0}/{1}/view".format(ROOMS_PATH, room_id),
            headers=_user_headers(guest_id),
        )
        _assert_api_success(view_resp)


def _get_my_active(client: TestClient, user_id: str):
    """
    查询用户活跃房间。

    :param client: 测试客户端。
    :param user_id: 用户 ID。
    :return: 房间详情或 ``None``。
    """
    resp = client.get(ROOMS_PATH + "/my-active", headers=_user_headers(user_id))
    data = _assert_api_success(resp)
    return data.get("room")
