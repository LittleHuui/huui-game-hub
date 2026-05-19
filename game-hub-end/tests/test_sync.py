"""同步域云存档接口测试。"""

import time
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, init_db
from app.main import app
from app.modules.sync.models import SyncLog
from tests.sync_helpers import (
    cloud_save,
    create_test_user,
    score_record_event,
    wallet_ledger_event,
)


def test_cloud_save_wallet_gain_cost_and_idempotent() -> None:
    """钱包流水同步应正确入账扣款，重复 clientId 不重复记账。"""
    suffix = uuid.uuid4().hex[:10]
    device_id = f"device_{suffix}"
    gain_id = f"gain_{suffix}"
    cost_id = f"cost_{suffix}"
    with TestClient(app) as client:
        user_id = create_test_user(client)
        snapshot = cloud_save(
            client,
            user_id=user_id,
            device_id=device_id,
            pending_events=[
                wallet_ledger_event(gain_id, change_type="gain", reason="game_win", amount=100),
                wallet_ledger_event(cost_id, change_type="cost", reason="buy_prop", amount=30),
            ],
        )
        assert snapshot["wallet"]["balance"] == 70
        assert snapshot["wallet"]["totalEarned"] == 100
        assert len(snapshot["walletLedgers"]) == 2

        snapshot_repeat = cloud_save(
            client,
            user_id=user_id,
            device_id=device_id,
            pending_events=[
                wallet_ledger_event(gain_id, change_type="gain", reason="game_win", amount=100),
                wallet_ledger_event(cost_id, change_type="cost", reason="buy_prop", amount=30),
            ],
        )
        assert snapshot_repeat["wallet"]["balance"] == 70
        assert len(snapshot_repeat["walletLedgers"]) == 2

        wallet_resp = client.get(f"/api/game-hub/users/{user_id}/wallet")
        wallet = wallet_resp.json()["data"]
        assert wallet["balance"] == 70
        assert wallet["totalEarned"] == 100


def test_cloud_save_empty_events_returns_snapshot() -> None:
    """无 pending 事件时应返回当前云存档且版本号有效。"""
    suffix = uuid.uuid4().hex[:10]
    with TestClient(app) as client:
        user_id = create_test_user(client)
        snapshot = cloud_save(
            client,
            user_id=user_id,
            device_id=f"device_{suffix}",
            pending_events=[],
            client_snapshot_version=3,
        )
        assert snapshot["user"]["serverId"] == user_id
        assert snapshot["wallet"]["balance"] == 0
        assert snapshot["cloudSnapshotVersion"] == 3
        assert isinstance(snapshot["serverTime"], int)


def test_cloud_save_duplicate_client_id_in_batch_rejected() -> None:
    """同一批次内重复 clientId 应校验失败。"""
    suffix = uuid.uuid4().hex[:10]
    dup_id = f"dup_{suffix}"
    with TestClient(app) as client:
        user_id = create_test_user(client)
        response = client.post(
            "/api/game-hub/sync/cloud-save",
            json={
                "userId": user_id,
                "deviceId": f"device_{suffix}",
                "clientSnapshotVersion": 1,
                "clientTime": int(time.time() * 1000),
                "pendingEvents": [
                    wallet_ledger_event(dup_id, change_type="gain", reason="game_win", amount=10),
                    wallet_ledger_event(dup_id, change_type="gain", reason="game_win", amount=10),
                ],
                "localSnapshot": {},
            },
        )
        assert response.status_code == 200
        assert response.json()["code"] != 0


def test_cloud_save_writes_sync_log() -> None:
    """同步结束后应写入 sync_log 审计记录。"""
    init_db()
    suffix = uuid.uuid4().hex[:10]
    with TestClient(app) as client:
        user_id = create_test_user(client)
        before = _count_sync_logs_for_user(user_id)
        cloud_save(
            client,
            user_id=user_id,
            device_id=f"device_{suffix}",
            pending_events=[
                wallet_ledger_event(
                    f"log_{suffix}",
                    change_type="gain",
                    reason="game_win",
                    amount=5,
                ),
            ],
        )
        after = _count_sync_logs_for_user(user_id)
        assert after == before + 1


def test_cloud_save_score_record_for_ranking() -> None:
    """经云存档写入成绩后排行榜应能查询到。"""
    suffix = uuid.uuid4().hex[:10]
    difficulty_code = f"hard_{suffix}"
    with TestClient(app) as client:
        user_id = create_test_user(client, nickname="排行玩家")
        cloud_save(
            client,
            user_id=user_id,
            device_id=f"device_{suffix}",
            pending_events=[
                score_record_event(
                    f"score_{suffix}",
                    difficulty_code=difficulty_code,
                    result="win",
                    score=800,
                    duration_ms=50000,
                ),
            ],
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
        items = response.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["userId"] == user_id
        assert items[0]["score"] == 800


def _count_sync_logs_for_user(user_id: str) -> int:
    """
    统计某用户的 sync_log 条数。

    :param user_id: 用户主键。
    :return: 日志条数。
    """
    with SessionLocal() as session:
        stmt = select(SyncLog).where(SyncLog.user_id == user_id, SyncLog.deleted_at.is_(None))
        return len(list(session.scalars(stmt).all()))
