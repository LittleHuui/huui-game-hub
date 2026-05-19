"""钱包域接口与积分变动测试。"""

import uuid

from fastapi.testclient import TestClient

from app.main import app
from tests.sync_helpers import cloud_save, create_test_user, wallet_ledger_event


def test_wallet_get_or_create_and_gain_cost_via_sync() -> None:
    """获取钱包、经云存档同步入账扣款后余额与流水应正确。"""
    suffix = uuid.uuid4().hex[:10]
    with TestClient(app) as client:
        user_id = create_test_user(client, nickname="钱包测试")

        wallet_resp = client.get(f"/api/game-hub/users/{user_id}/wallet")
        assert wallet_resp.status_code == 200
        wallet = wallet_resp.json()["data"]
        assert wallet["userId"] == user_id
        assert wallet["balance"] == 0
        assert wallet["totalEarned"] == 0

        snapshot = cloud_save(
            client,
            user_id=user_id,
            device_id=f"device_{suffix}",
            pending_events=[
                wallet_ledger_event(
                    f"gain_{suffix}",
                    change_type="gain",
                    reason="game_win",
                    amount=100,
                ),
                wallet_ledger_event(
                    f"cost_{suffix}",
                    change_type="cost",
                    reason="buy_prop",
                    amount=30,
                ),
            ],
        )
        assert snapshot["wallet"]["balance"] == 70
        assert snapshot["wallet"]["totalEarned"] == 100

        wallet_resp = client.get(f"/api/game-hub/users/{user_id}/wallet")
        wallet = wallet_resp.json()["data"]
        assert wallet["balance"] == 70
        assert wallet["totalEarned"] == 100

        ledgers_resp = client.get(f"/api/game-hub/users/{user_id}/wallet/ledgers")
        assert ledgers_resp.status_code == 200
        page = ledgers_resp.json()["data"]
        assert page["pageNum"] == 1
        assert page["pageSize"] == 20
        assert page["total"] == 2
        items = page["items"]
        assert len(items) == 2
        assert {x["changeType"] for x in items} == {"gain", "cost"}
