"""UNO 房间与对局链路集成测试（依赖 Redis）。"""

import asyncio
import time
from typing import Any, Dict, Tuple

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import RedisError

from app.core.redis.redis_client import redis_client
from app.core.redis.redis_keys import RedisKeys
from app.main import app
from tests.sync_helpers import create_test_user

API_PREFIX = "/api/game-hub"
RULE_DEFINITION_PATH = API_PREFIX + "/games/{game_code}/rule-definition"
ROOMS_PATH = API_PREFIX + "/rooms"


def _require_redis() -> None:
    """
    Redis 不可用时跳过本模块集成测试。

    :return: 无。
    """
    loop = asyncio.new_event_loop()
    try:
        try:
            available = loop.run_until_complete(redis_client.ping())
        except (RedisError, OSError, ConnectionError):
            available = False
    finally:
        loop.close()
    if not available:
        pytest.skip("Redis 不可用，跳过 UNO 房间链路测试")


def _assert_api_success(response) -> Dict[str, Any]:
    """
    断言 HTTP 200 且 ApiResponse 业务成功。

    :param response: TestClient 响应。
    :return: 响应 data 字段。
    """
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["message"] == "success"
    assert payload["success"] is True
    assert "timestamp" in payload
    return payload["data"]


def _assert_api_error(response, expected_code: int) -> Dict[str, Any]:
    """
    断言 ApiResponse 业务失败。

    :param response: TestClient 响应。
    :param expected_code: 期望错误码。
    :return: 完整响应 JSON。
    """
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["code"] == expected_code
    return payload


def _redis_exists_snapshot(room_id: str, game_code: str):
    """
    读取房间关键 Redis key 是否存在。

    :param room_id: 房间 ID。
    :param game_code: 游戏编码。
    :return: key 存在状态字典。
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_collect_room_key_exists(room_id, game_code))
    finally:
        loop.close()


async def _collect_room_key_exists(room_id: str, game_code: str) -> Dict[str, bool]:
    """
    异步收集房间核心 key 与模式 key 是否存在。

    :param room_id: 房间 ID。
    :param game_code: 游戏编码。
    :return: key 存在状态。
    """
    fixed_keys = {
        "meta": RedisKeys.room_meta(room_id),
        "players": RedisKeys.room_players(room_id),
        "runtime": RedisKeys.room_runtime(room_id),
        "public_state": RedisKeys.room_public_state(room_id),
        "events": RedisKeys.room_events(room_id),
        "version": RedisKeys.room_version(room_id),
        "lock": RedisKeys.room_lock(room_id),
        "game_rooms": RedisKeys.game_rooms(game_code),
    }
    result = {}
    for name, key in fixed_keys.items():
        result[name] = await redis_client.exists(key)
    private_keys = await redis_client.scan_keys(RedisKeys.room_private_state_pattern(room_id))
    legal_action_keys = await redis_client.scan_keys(RedisKeys.room_legal_actions_pattern(room_id))
    result["private_state_pattern"] = len(private_keys) > 0
    result["legal_actions_pattern"] = len(legal_action_keys) > 0
    return result


def _user_headers(user_id: str) -> Dict[str, str]:
    """
    构造房间接口所需的用户请求头。

    :param user_id: 用户 serverId。
    :return: 请求头字典。
    """
    return {"X-Game-Hub-User-Id": user_id}


def _pick_current_player_action(view: Dict[str, Any]) -> Tuple[str, str]:
    """
    从 GameView 中选取当前玩家的一条合法操作。

    :param view: 对局视图。
    :return: ``(actionType, actionId)``。
    """
    current_player_id = view.get("currentPlayerId")
    viewer_id = view.get("viewerPlayerId")
    assert current_player_id == viewer_id
    legal_actions = view.get("legalActions") or []
    assert len(legal_actions) > 0
    matched = None
    for item in legal_actions:
        if item.get("actionType") == "PLAY_CARD":
            matched = item
            break
    if matched is None:
        matched = legal_actions[0]
    action_type = matched["actionType"]
    action_id = matched.get("actionId")
    assert isinstance(action_id, str) and action_id.strip()
    return action_type, action_id.strip()


def _view_change_signature(view: Dict[str, Any]) -> Tuple[Any, ...]:
    """
    提取用于对比操作前后是否变化的视图摘要。

    :param view: 对局视图。
    :return: 可哈希摘要元组。
    """
    public_state = view.get("publicState") or {}
    private_state = view.get("privateState") or {}
    legal_action_ids = tuple(
        sorted(
            item.get("actionId", "")
            for item in (view.get("legalActions") or [])
            if isinstance(item, dict)
        )
    )
    return (
        view.get("currentPlayerId"),
        view.get("phase"),
        len(private_state.get("handCards") or []),
        public_state.get("discardTopCard"),
        public_state.get("drawPileCount"),
        public_state.get("pendingDraw"),
        legal_action_ids,
    )


def _assert_game_view_shape(view: Dict[str, Any]) -> None:
    """
    校验 GameView 联调必需字段。

    :param view: 对局视图。
    :return: 无。
    """
    assert "version" in view
    assert view.get("roomId")
    assert view.get("viewerPlayerId")
    public_state = view.get("publicState") or {}
    private_state = view.get("privateState") or {}
    assert "currentPlayerId" in public_state
    assert "currentColor" in public_state
    assert "playDirection" in public_state
    assert "discardTopCard" in public_state
    assert "players" in public_state
    assert "drawPileCount" in public_state
    assert "rankings" in public_state
    assert "pendingDraw" in public_state
    assert "handCards" in private_state
    assert isinstance(view.get("legalActions"), list)
    assert isinstance(view.get("events"), list)


def _assert_private_state_isolated(view: Dict[str, Any]) -> None:
    """
    校验 privateState 仅含视角玩家手牌，公开区不泄露他人手牌明细。

    :param view: 对局视图。
    :return: 无。
    """
    private_state = view.get("privateState") or {}
    hand_cards = private_state.get("handCards")
    assert isinstance(hand_cards, list)

    public_state = view.get("publicState") or {}
    assert "handCards" not in public_state
    players = public_state.get("players") or []
    assert isinstance(players, list)
    for summary in players:
        assert "handCards" not in summary
        assert "handCount" in summary


def test_uno_room_game_flow_end_to_end() -> None:
    """UNO：rule-definition → 建房 → 真人加入 → 开局 → 视图 → 提交 actionId → 新视图且私有态隔离。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="UNO房主")

        rule_resp = client.get(RULE_DEFINITION_PATH.format(game_code="uno"))
        rule_data = _assert_api_success(rule_resp)
        assert rule_data["gameCode"] == "uno"
        assert rule_data["runtimeType"] == "strategy-turn-multiplayer"
        assert rule_data["roomRule"]["minPlayers"] == 2
        assert rule_data["roomRule"]["maxAiCount"] == 9
        schema_map = {item["key"]: item for item in rule_data["roomConfigSchema"]}
        assert schema_map["allowDrawStacking"]["defaultValue"] is True
        assert schema_map["finishMode"]["defaultValue"] == "UNTIL_REAL_PLAYER_COUNT"
        deck_total = sum(item["countPerDeckSet"] for item in rule_data["cardDefinitions"])
        assert deck_total == 108

        create_resp = client.post(
            ROOMS_PATH,
            json={
                "gameCode": "uno",
                "mode": "classic",
            },
            headers=_user_headers(owner_id),
        )
        room_data = _assert_api_success(create_resp)
        room_id = room_data["roomId"]
        assert room_data["status"] == "waiting"
        assert room_data["gameCode"] == "uno"
        assert room_data["ownerPlayerId"] == owner_id

        guest_id = create_test_user(client, nickname="UNO玩家2")
        join_resp = client.post(
            "{0}/{1}/join".format(ROOMS_PATH, room_id),
            headers=_user_headers(guest_id),
        )
        join_room = _assert_api_success(join_resp)
        assert join_room["memberCount"] >= 2

        start_resp = client.post(
            "{0}/{1}/start".format(ROOMS_PATH, room_id),
            headers=_user_headers(owner_id),
        )
        start_view = _assert_api_success(start_resp)
        assert start_view["gameCode"] == "uno"
        assert start_view["roomId"] == room_id
        assert start_view["phase"] == "playing"
        assert start_view["isGameOver"] is False
        start_events = start_view.get("events") or []
        assert start_events == []
        _assert_game_view_shape(start_view)
        current_player_id = start_view["currentPlayerId"]
        assert current_player_id

        view_resp = client.get(
            "{0}/{1}/view".format(ROOMS_PATH, room_id),
            headers=_user_headers(current_player_id),
        )
        before_view = _assert_api_success(view_resp)
        _assert_game_view_shape(before_view)
        before_signature = _view_change_signature(before_view)
        _assert_private_state_isolated(before_view)

        action_type, action_id = _pick_current_player_action(before_view)
        assert action_type
        action_resp = client.post(
            "{0}/{1}/actions".format(ROOMS_PATH, room_id),
            headers=_user_headers(current_player_id),
            json={
                "actionId": action_id,
                "baseVersion": before_view["version"],
                "clientSeq": 1,
            },
        )
        after_view = _assert_api_success(action_resp)
        assert after_view["gameCode"] == "uno"
        assert after_view["viewerPlayerId"] == current_player_id
        _assert_game_view_shape(after_view)
        _assert_private_state_isolated(after_view)
        assert _view_change_signature(after_view) != before_signature

        non_current_headers = _user_headers(owner_id)
        if owner_id == current_player_id:
            non_current_headers = None
        if non_current_headers is not None:
            other_view_resp = client.get(
                "{0}/{1}/view".format(ROOMS_PATH, room_id),
                headers=non_current_headers,
            )
            other_view = _assert_api_success(other_view_resp)
            _assert_private_state_isolated(other_view)
            assert other_view.get("legalActions") == []


def test_room_leave_owner_transfer_and_dissolve_cleanup() -> None:
    """waiting 房间离开链路：房主转移、可开局、最终解散并清理 Redis。"""
    _require_redis()
    with TestClient(app) as client:
        owner_id = create_test_user(client, nickname="房主")
        player_a_id = create_test_user(client, nickname="玩家A")
        player_b_id = create_test_user(client, nickname="玩家B")

        create_data = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": "uno", "mode": "classic"},
                headers=_user_headers(owner_id),
            )
        )
        room_id = create_data["roomId"]

        time.sleep(0.01)
        join_a = _assert_api_success(
            client.post(
                "{0}/{1}/join".format(ROOMS_PATH, room_id),
                headers=_user_headers(player_a_id),
            )
        )
        assert join_a["memberCount"] == 2

        time.sleep(0.01)
        join_b = _assert_api_success(
            client.post(
                "{0}/{1}/join".format(ROOMS_PATH, room_id),
                headers=_user_headers(player_b_id),
            )
        )
        assert join_b["memberCount"] == 3

        leave_owner_data = _assert_api_success(
            client.post(
                "{0}/{1}/leave".format(ROOMS_PATH, room_id),
                headers=_user_headers(owner_id),
            )
        )
        assert leave_owner_data["dissolved"] is False
        assert leave_owner_data["room"] is not None
        assert leave_owner_data["room"]["ownerPlayerId"] == player_a_id
        assert leave_owner_data["room"]["ownerNickname"] == "玩家A"
        assert leave_owner_data["room"]["memberCount"] == 2

        start_resp = client.post(
            "{0}/{1}/start".format(ROOMS_PATH, room_id),
            headers=_user_headers(player_a_id),
        )
        start_data = _assert_api_success(start_resp)
        assert start_data["phase"] == "playing"

        leave_in_playing_data = _assert_api_success(
            client.post(
                "{0}/{1}/leave".format(ROOMS_PATH, room_id),
                headers=_user_headers(player_b_id),
            )
        )
        assert leave_in_playing_data["dissolved"] is False
        assert leave_in_playing_data["room"]["status"] == "playing"
        assert leave_in_playing_data["room"]["memberCount"] == 2
        assert leave_in_playing_data["room"]["ownerPlayerId"] == player_a_id

        # 重新创建等待房间，验证普通成员离开不影响房主 + 最后一人离开销毁。
        create_data_2 = _assert_api_success(
            client.post(
                ROOMS_PATH,
                json={"gameCode": "uno", "mode": "classic"},
                headers=_user_headers(owner_id),
            )
        )
        room_id_2 = create_data_2["roomId"]
        join_a_2 = _assert_api_success(
            client.post(
                "{0}/{1}/join".format(ROOMS_PATH, room_id_2),
                headers=_user_headers(player_a_id),
            )
        )
        assert join_a_2["memberCount"] == 2

        leave_member_data = _assert_api_success(
            client.post(
                "{0}/{1}/leave".format(ROOMS_PATH, room_id_2),
                headers=_user_headers(player_a_id),
            )
        )
        assert leave_member_data["dissolved"] is False
        assert leave_member_data["room"]["ownerPlayerId"] == owner_id
        assert leave_member_data["room"]["memberCount"] == 1

        leave_last_data = _assert_api_success(
            client.post(
                "{0}/{1}/leave".format(ROOMS_PATH, room_id_2),
                headers=_user_headers(owner_id),
            )
        )
        assert leave_last_data["dissolved"] is True
        assert leave_last_data["room"] is None
        assert leave_last_data["roomId"] == room_id_2
        assert leave_last_data["gameCode"] == "uno"

        get_deleted_resp = client.get("{0}/{1}".format(ROOMS_PATH, room_id_2))
        _assert_api_error(get_deleted_resp, 90001)

        room_list_data = _assert_api_success(client.get(ROOMS_PATH, params={"gameCode": "uno"}))
        assert all(item.get("roomId") != room_id_2 for item in room_list_data)

        key_snapshot = _redis_exists_snapshot(room_id_2, "uno")
        assert key_snapshot["meta"] is False
        assert key_snapshot["players"] is False
        assert key_snapshot["runtime"] is False
        assert key_snapshot["public_state"] is False
        assert key_snapshot["events"] is False
        assert key_snapshot["version"] is False
        assert key_snapshot["lock"] is False
        assert key_snapshot["private_state_pattern"] is False
        assert key_snapshot["legal_actions_pattern"] is False
