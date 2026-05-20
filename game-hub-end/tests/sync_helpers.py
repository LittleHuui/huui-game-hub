"""同步接口测试辅助。"""

import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi.testclient import TestClient


def _now_ms() -> int:
    """返回当前毫秒时间戳。"""
    return int(time.time() * 1000)


def create_test_user(client: TestClient, *, nickname: str = "测试用户") -> str:
    """
    创建测试用户并返回 server_id。

    :param client: 测试客户端。
    :param nickname: 昵称。
    :return: 用户主键。
    """
    suffix = uuid.uuid4().hex[:10]
    response = client.post(
        "/api/game-hub/users/",
        json={
            "clientId": f"client_{suffix}",
            "username": f"user_{suffix}",
            "nickname": nickname,
        },
    )
    assert response.status_code == 200
    assert response.json()["code"] == 0
    return response.json()["data"]["serverId"]


def cloud_save(
    client: TestClient,
    *,
    user_id: str,
    device_id: str,
    pending_events: List[Dict[str, Any]],
    client_snapshot_version: int = 1,
    local_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    调用云存档同步接口并断言成功。

    :param client: 测试客户端。
    :param user_id: 用户主键。
    :param device_id: 设备 ID。
    :param pending_events: pendingEvents 列表（camelCase 键）。
    :param client_snapshot_version: 客户端快照版本。
    :param local_snapshot: 本地快照，可空。
    :return: 响应 data 字段（云存档快照）。
    """
    now = _now_ms()
    events: List[Dict[str, Any]] = []
    for item in pending_events:
        event = dict(item)
        event.setdefault("createdAt", now)
        event.setdefault("updatedAt", now)
        events.append(event)
    response = client.post(
        "/api/game-hub/sync/cloud-save",
        json={
            "userId": user_id,
            "deviceId": device_id,
            "clientSnapshotVersion": client_snapshot_version,
            "clientTime": now,
            "pendingEvents": events,
            "localSnapshot": local_snapshot or {},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0, body
    return body["data"]


def wallet_ledger_event(
    client_id: str,
    *,
    change_type: str,
    reason: str,
    amount: int,
    game_code: str = "minesweeper",
) -> Dict[str, Any]:
    """
    构造 wallet_ledger 同步事件。

    :param client_id: 事件幂等键。
    :param change_type: gain / cost。
    :param reason: 业务原因。
    :param amount: 变动量。
    :param game_code: 游戏编码。
    :return: pendingEvents 单条元素。
    """
    return {
        "clientId": client_id,
        "eventType": "wallet_ledger",
        "payload": {
            "changeType": change_type,
            "reason": reason,
            "amount": amount,
            "gameCode": game_code,
        },
    }


def match_record_event(
    client_id: str,
    *,
    game_code: str,
    mode: str = "single",
    result: str = "win",
    difficulty_code: Optional[str] = None,
    score: int = 0,
    duration_ms: Optional[int] = None,
) -> Dict[str, Any]:
    """
    构造 match_record 同步事件。

    :param client_id: 事件幂等键。
    :param game_code: 游戏编码。
    :param mode: 玩法模式。
    :param result: 对局结果。
    :param difficulty_code: 难度编码，可空。
    :param score: 得分。
    :param duration_ms: 用时（毫秒），可空。
    :return: pendingEvents 单条元素。
    """
    payload: Dict[str, Any] = {
        "gameCode": game_code,
        "mode": mode,
        "result": result,
        "score": score,
    }
    if difficulty_code is not None:
        payload["difficultyCode"] = difficulty_code
    if duration_ms is not None:
        payload["durationMs"] = duration_ms
    return {
        "clientId": client_id,
        "eventType": "match_record",
        "payload": payload,
    }


def score_record_event(
    client_id: str,
    *,
    game_code: str = "minesweeper",
    mode: str = "single",
    difficulty_code: str,
    result: str,
    score: int,
    duration_ms: int,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    构造 score_record 同步事件。

    :param client_id: 事件幂等键。
    :param game_code: 游戏编码。
    :param mode: 模式。
    :param difficulty_code: 难度编码。
    :param result: 对局结果。
    :param score: 分数。
    :param duration_ms: 用时（毫秒）。
    :param payload: 扩展 payload 对象，可空。
    :return: pendingEvents 单条元素。
    """
    event_payload: Dict[str, Any] = {
        "gameCode": game_code,
        "mode": mode,
        "difficultyCode": difficulty_code,
        "result": result,
        "score": score,
        "durationMs": duration_ms,
    }
    if payload is not None:
        event_payload["payload"] = payload
    return {
        "clientId": client_id,
        "eventType": "score_record",
        "payload": event_payload,
    }
