"""房主更新 waiting 房间配置集成测试（依赖 Redis）。"""

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import RedisError

from app.common.error_code import ErrorCode
from app.main import app
from tests.sync_helpers import create_test_user
from tests.test_uno_room_flow import (
    ROOMS_PATH,
    _assert_api_error,
    _assert_api_success,
    _user_headers,
)


def _require_redis() -> None:
    """
    使用同步客户端探测 Redis，避免与 TestClient 生命周期争用异步事件循环。

    :return: 无。
    """
    try:
        import redis

        client = redis.Redis(host="127.0.0.1", port=6379, db=0)
        if not client.ping():
            pytest.skip("Redis 不可用，跳过房间配置更新测试")
    except (RedisError, OSError, ConnectionError, ImportError):
        pytest.skip("Redis 不可用，跳过房间配置更新测试")


def _patch_room_config(
    client: TestClient,
    owner_id: str,
    room_id: str,
    body: Dict[str, Any],
):
    """
    调用更新房间配置接口。

    :param client: 测试客户端。
    :param owner_id: 房主用户 ID。
    :param room_id: 房间 ID。
    :param body: 请求体。
    :return: TestClient 响应。
    """
    return client.patch(
        "{0}/{1}/config".format(ROOMS_PATH, room_id),
        json=body,
        headers=_user_headers(owner_id),
    )


def test_update_room_config_rejects_allow_ai_and_max_ai_count() -> None:
    """update_room_config 不再接受 allowAi / maxAiCount。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="配置房主")
        create_data = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": "uno", "mode": "classic"},
                headers=_user_headers(owner_id),
            )
        )
        room_id = create_data["roomId"]
        resp = _patch_room_config(
            client,
            owner_id,
            room_id,
            {"allowAi": False, "maxAiCount": 1},
        )
        _assert_api_error(resp, ErrorCode.PARAM_ERROR.code)


def test_update_room_config_can_merge_room_config() -> None:
    """update_room_config 可保存 roomConfig 覆盖项。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="玩法配置房主")
        create_data = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": "uno", "mode": "classic"},
                headers=_user_headers(owner_id),
            )
        )
        room_id = create_data["roomId"]
        updated = _assert_api_success(
            _patch_room_config(
                client,
                owner_id,
                room_id,
                {"roomConfig": {"initialHandCount": 5}},
            )
        )
        assert updated["roomConfig"]["initialHandCount"] == 5


def test_update_room_config_rejects_when_human_count_exceeds_max_players() -> None:
    """真人数超过新 maxPlayers 时报错。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="人数房主")
        guest_id = create_test_user(client, nickname="人数客人")
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
        resp = _patch_room_config(
            client,
            owner_id,
            room_id,
            {"maxPlayers": 1},
        )
        _assert_api_error(resp, ErrorCode.PARAM_ERROR.code)


def test_update_room_config_removes_excess_ai_when_lowering_max_players() -> None:
    """成员总数超过新 maxPlayers 时优先移除多余 AI。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="AI移除房主")
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
        _assert_api_success(
            client.post(
                "{0}/{1}/ai".format(ROOMS_PATH, room_id),
                headers=_user_headers(owner_id),
            )
        )
        before = _assert_api_success(
            client.get(
                "{0}/{1}".format(ROOMS_PATH, room_id),
                headers=_user_headers(owner_id),
            )
        )
        assert before["memberCount"] == 3
        assert before["aiCount"] == 2

        updated = _assert_api_success(
            _patch_room_config(
                client,
                owner_id,
                room_id,
                {"maxPlayers": 2},
            )
        )
        assert updated["maxPlayers"] == 2
        assert updated["memberCount"] == 2
        assert updated["aiCount"] == 1


def test_update_room_config_does_not_validate_game_specific_fields() -> None:
    """修改 roomConfig 不做游戏特殊验证。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="宽松配置房主")
        create_data = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": "uno", "mode": "classic"},
                headers=_user_headers(owner_id),
            )
        )
        room_id = create_data["roomId"]
        updated = _assert_api_success(
            _patch_room_config(
                client,
                owner_id,
                room_id,
                {"roomConfig": {"initialHandCount": 99}},
            )
        )
        assert updated["roomConfig"]["initialHandCount"] == 99
