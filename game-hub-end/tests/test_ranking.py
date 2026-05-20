"""排行榜域接口测试。"""

import uuid

from fastapi.testclient import TestClient

from app.main import app
from tests.sync_helpers import cloud_save, create_test_user, score_record_event


def _push_score(
    client: TestClient,
    user_id: str,
    client_id: str,
    *,
    difficulty_code: str,
    score: int,
    duration_ms: int,
    result: str = "win",
) -> None:
    """
    通过云存档同步接口写入一条成绩记录。

    :param client: 测试客户端。
    :param user_id: 用户主键。
    :param client_id: 客户端幂等键。
    :param difficulty_code: 难度编码（测试隔离用）。
    :param score: 分数。
    :param duration_ms: 用时（毫秒）。
    :param result: 对局结果。
    """
    cloud_save(
        client,
        user_id=user_id,
        device_id=f"device_{client_id}",
        pending_events=[
            score_record_event(
                client_id,
                difficulty_code=difficulty_code,
                result=result,
                score=score,
                duration_ms=duration_ms,
            ),
        ],
    )


def test_rankings_minesweeper_sort_and_response_shape() -> None:
    """扫雷排行榜应按用时升序、分数降序、创建时间升序排列。"""
    suffix = uuid.uuid4().hex[:10]
    difficulty_code = f"hard_{suffix}"
    with TestClient(app) as client:
        user_fast = create_test_user(client, nickname="玩家快")
        user_slow = create_test_user(client, nickname="玩家慢")
        user_lose = create_test_user(client, nickname="玩家败")

        _push_score(
            client,
            user_fast,
            f"score_fast_{suffix}",
            difficulty_code=difficulty_code,
            score=900,
            duration_ms=60000,
        )
        _push_score(
            client,
            user_slow,
            f"score_slow_{suffix}",
            difficulty_code=difficulty_code,
            score=1000,
            duration_ms=90000,
        )
        _push_score(
            client,
            user_lose,
            f"score_lose_{suffix}",
            difficulty_code=difficulty_code,
            score=2000,
            duration_ms=10000,
            result="lose",
        )

        response = client.get(
            "/api/game-hub/rankings",
            params={
                "gameCode": "minesweeper",
                "mode": "single",
                "difficultyCode": difficulty_code,
                "limit": 10,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 0
        data = payload["data"]
        assert data["gameCode"] == "minesweeper"
        assert data["mode"] == "single"
        assert data["difficultyCode"] == difficulty_code
        assert len(data["items"]) == 2

        first = data["items"][0]
        assert first["rank"] == 1
        assert first["userId"] == user_fast
        assert first["nickname"] == "玩家快"
        assert first["score"] == 900
        assert first["durationMs"] == 60000
        assert isinstance(first["createdAt"], int)

        second = data["items"][1]
        assert second["rank"] == 2
        assert second["userId"] == user_slow
        assert second["nickname"] == "玩家慢"


def test_rankings_match3_timed_sort_by_combo_and_duration() -> None:
    """match3 timed 应按配置：分数、comboMax、用时排序。"""
    suffix = uuid.uuid4().hex[:10]
    difficulty_code = f"normal_{suffix}"
    with TestClient(app) as client:
        user_high_combo = create_test_user(client, nickname="连击高")
        user_fast = create_test_user(client, nickname="用时短")

        for user_id, client_key, combo, duration in (
            (user_high_combo, f"m3_combo_{suffix}", 10, 120000),
            (user_fast, f"m3_fast_{suffix}", 5, 60000),
        ):
            cloud_save(
                client,
                user_id=user_id,
                device_id=f"device_{client_key}",
                pending_events=[
                    score_record_event(
                        client_key,
                        game_code="match3",
                        mode="timed",
                        difficulty_code=difficulty_code,
                        result="win",
                        score=5000,
                        duration_ms=duration,
                        payload={"comboMax": combo, "moves": 40},
                    ),
                ],
            )

        response = client.get(
            "/api/game-hub/rankings",
            params={
                "gameCode": "match3",
                "mode": "timed",
                "difficultyCode": difficulty_code,
                "limit": 10,
            },
        )
        assert response.status_code == 200
        items = response.json()["data"]["items"]
        assert len(items) == 2
        assert items[0]["userId"] == user_high_combo
        assert items[1]["userId"] == user_fast


def test_rankings_rejects_invalid_limit() -> None:
    """limit 超出范围时应返回统一校验错误码。"""
    with TestClient(app) as client:
        response = client.get(
            "/api/game-hub/rankings",
            params={
                "gameCode": "minesweeper",
                "mode": "single",
                "difficultyCode": "hard",
                "limit": 0,
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 10002
    assert payload["success"] is False
    assert "timestamp" in payload
