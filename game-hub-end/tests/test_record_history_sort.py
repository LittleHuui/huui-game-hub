"""道具使用 / 购买记录按时间倒序测试。"""

import time
import uuid

from fastapi.testclient import TestClient

from app.core.database import init_db
from app.main import app
from tests.sync_helpers import cloud_save, create_test_user, wallet_ledger_event


def _record_timestamp(row: dict) -> int:
    """取记录排序用时间戳（与历史对局一致：优先 updatedAt）。"""
    updated = row.get("updatedAt")
    created = row.get("createdAt")
    if isinstance(updated, int) and updated > 0:
        return updated
    if isinstance(created, int) and created > 0:
        return created
    return 0


def _prop_usage_event(
    client_id: str,
    *,
    game_code: str,
    prop_code: str,
    created_at: int,
    updated_at: int,
) -> dict:
    """构造道具使用同步事件。"""
    return {
        "clientId": client_id,
        "eventType": "prop_usage",
        "createdAt": created_at,
        "updatedAt": updated_at,
        "payload": {
            "gameCode": game_code,
            "propCode": prop_code,
            "quantity": 1,
            "consumeFromBag": False,
        },
    }


def _prop_purchase_event(
    client_id: str,
    *,
    game_code: str,
    prop_code: str,
    created_at: int,
    updated_at: int,
    unit_price: int = 10,
    total_price: int = 10,
) -> dict:
    """构造道具购买同步事件。"""
    return {
        "clientId": client_id,
        "eventType": "prop_purchase",
        "createdAt": created_at,
        "updatedAt": updated_at,
        "payload": {
            "gameCode": game_code,
            "propCode": prop_code,
            "quantity": 1,
            "unitPrice": unit_price,
            "totalPrice": total_price,
            "walletClientId": f"{client_id}:wallet",
        },
    }


def _import_game_with_prop(client: TestClient, game_code: str, prop_code: str) -> None:
    """导入单道具游戏规则。"""
    seed_body = {
        "props": [
            {
                "propCode": prop_code,
                "propName": "测试道具",
                "basePrice": 10,
                "enabled": True,
            }
        ],
        "games": [
            {
                "gameCode": game_code,
                "gameName": "排序测试",
                "supportOnline": False,
                "enabled": True,
                "sortNo": 1,
                "config": {},
                "propRules": [
                    {
                        "propCode": prop_code,
                        "price": 10,
                        "enabled": True,
                        "rule": {},
                    }
                ],
            }
        ],
    }
    resp = client.post("/api/game-hub/admin/config/import-game-seed", json=seed_body)
    assert resp.status_code == 200


def test_prop_usage_records_sorted_newest_first() -> None:
    """使用记录 API 应按 updatedAt/createdAt 倒序，混合游戏不按 gameCode 分组。"""
    init_db()
    suffix = uuid.uuid4().hex[:8]
    game_a = f"usage_a_{suffix}"
    game_b = f"usage_b_{suffix}"
    prop = f"prop_{suffix}"
    now = int(time.time() * 1000)

    with TestClient(app) as client:
        _import_game_with_prop(client, game_a, prop)
        _import_game_with_prop(client, game_b, prop)
        user_id = create_test_user(client)
        device_id = f"device_{suffix}"

        cloud_save(
            client,
            user_id=user_id,
            device_id=device_id,
            pending_events=[
                _prop_usage_event(
                    f"usage_old_{suffix}",
                    game_code=game_a,
                    prop_code=prop,
                    created_at=now - 2000,
                    updated_at=now - 2000,
                ),
                _prop_usage_event(
                    f"usage_new_{suffix}",
                    game_code=game_b,
                    prop_code=prop,
                    created_at=now - 500,
                    updated_at=now - 500,
                ),
            ],
        )

        resp = client.get(f"/api/game-hub/users/{user_id}/inventory/usage-records")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) >= 2
        stamps = [_record_timestamp(row) for row in items]
        assert stamps == sorted(stamps, reverse=True)
        assert items[0]["clientId"] == f"usage_new_{suffix}"
        assert items[0]["gameCode"] == game_b


def test_purchase_records_sorted_newest_first() -> None:
    """购买记录 API 应按 updatedAt/createdAt 倒序，混合游戏不按 gameCode 分组。"""
    init_db()
    suffix = uuid.uuid4().hex[:8]
    game_a = f"purchase_a_{suffix}"
    game_b = f"purchase_b_{suffix}"
    prop = f"prop_{suffix}"
    now = int(time.time() * 1000)

    with TestClient(app) as client:
        _import_game_with_prop(client, game_a, prop)
        _import_game_with_prop(client, game_b, prop)
        user_id = create_test_user(client)
        device_id = f"device_{suffix}"

        cloud_save(
            client,
            user_id=user_id,
            device_id=device_id,
            pending_events=[wallet_ledger_event(f"wallet_{suffix}", change_type="gain", reason="test", amount=1000)],
        )
        cloud_save(
            client,
            user_id=user_id,
            device_id=device_id,
            pending_events=[
                _prop_purchase_event(
                    f"purchase_old_{suffix}",
                    game_code=game_a,
                    prop_code=prop,
                    created_at=now - 2000,
                    updated_at=now - 2000,
                ),
                _prop_purchase_event(
                    f"purchase_new_{suffix}",
                    game_code=game_b,
                    prop_code=prop,
                    created_at=now - 500,
                    updated_at=now - 500,
                ),
            ],
        )

        resp = client.get(f"/api/game-hub/users/{user_id}/purchases")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) >= 2
        stamps = [_record_timestamp(row) for row in items]
        assert stamps == sorted(stamps, reverse=True)
        assert items[0]["clientId"] == f"purchase_new_{suffix}"
        assert items[0]["gameCode"] == game_b
