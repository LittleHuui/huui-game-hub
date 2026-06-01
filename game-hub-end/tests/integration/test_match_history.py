"""历史对局 gameCode 写入与查询测试。"""

import uuid

from fastapi.testclient import TestClient

from app.main import app
from tests.sync_helpers import cloud_save, create_test_user, match_record_event


def test_sync_match_record_and_list_with_game_code_filter() -> None:
    """云存档写入对局后，历史接口应返回 gameCode 并支持按 gameCode 过滤。"""
    suffix = uuid.uuid4().hex[:10]
    game_a = f"game_a_{suffix}"
    game_b = f"game_b_{suffix}"
    with TestClient(app) as client:
        user_id = create_test_user(client)
        device_id = f"device_{suffix}"
        cloud_save(
            client,
            user_id=user_id,
            device_id=device_id,
            pending_events=[
                match_record_event(
                    f"match_a_{suffix}",
                    game_code=game_a,
                    mode="timed",
                    result="win",
                    score=100,
                ),
                match_record_event(
                    f"match_b_{suffix}",
                    game_code=game_b,
                    mode="endless",
                    result="lose",
                    score=50,
                ),
            ],
        )

        list_resp = client.get(f"/api/game-hub/users/{user_id}/matches")
        assert list_resp.status_code == 200
        body = list_resp.json()
        assert body["code"] == 0
        items = body["data"]["items"]
        assert len(items) >= 2
        codes = {item["gameCode"] for item in items}
        assert game_a in codes
        assert game_b in codes
        assert "game_code" not in items[0]

        filtered = client.get(
            f"/api/game-hub/users/{user_id}/matches",
            params={"gameCode": game_a},
        )
        assert filtered.status_code == 200
        filtered_items = filtered.json()["data"]["items"]
        assert len(filtered_items) >= 1
        assert all(item["gameCode"] == game_a for item in filtered_items)


def test_sync_match_record_prop_uses_array_and_payload_object() -> None:
    """对局同步应接受 propUses 数组与 payload 对象。"""
    suffix = uuid.uuid4().hex[:10]
    game_code = f"match_payload_{suffix}"
    client_id = f"match_payload_{suffix}"
    with TestClient(app) as client:
        user_id = create_test_user(client)
        device_id = f"device_{suffix}"
        snapshot = cloud_save(
            client,
            user_id=user_id,
            device_id=device_id,
            pending_events=[
                {
                    "clientId": client_id,
                    "eventType": "match_record",
                    "payload": {
                        "gameCode": game_code,
                        "mode": "single",
                        "result": "win",
                        "score": 10,
                        "propUses": [{"propCode": "hint", "quantity": 1}],
                        "payload": {"level": 3},
                    },
                },
            ],
        )
        match_rows = [row for row in snapshot["matchRecords"] if row["clientId"] == client_id]
        assert len(match_rows) == 1
        assert match_rows[0]["gameCode"] == game_code
        assert match_rows[0]["propUses"] == [{"propCode": "hint", "quantity": 1}]
        assert match_rows[0]["payload"] == {"level": 3}

        detail_resp = client.get(f"/api/game-hub/users/{user_id}/matches", params={"gameCode": game_code})
        items = detail_resp.json()["data"]["items"]
        row = next(item for item in items if item["clientId"] == client_id)
        assert row["propUses"] == [{"propCode": "hint", "quantity": 1}]
        assert row["payload"] == {"level": 3}


def test_sync_match_record_rejects_snake_case_payload_keys() -> None:
    """对局同步 payload 不再接受 snake_case 键名。"""
    import pytest

    from app.common.exceptions import ValidationException
    from app.modules.sync.entity_service import require_fields
    from app.modules.sync.schemas import PendingEvent

    event = PendingEvent(
        clientId="snake_case_test",
        eventType="match_record",
        createdAt=1,
        updatedAt=1,
        payload={
            "game_code": "demo",
            "mode": "single",
            "result": "win",
        },
    )
    with pytest.raises(ValidationException, match="gameCode"):
        require_fields(event.payload, ["gameCode", "mode", "result"], event)
