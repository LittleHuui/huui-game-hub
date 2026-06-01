"""import-game-seed 导入模式（merge / full）与删除模式测试。"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, init_db
from app.main import app
from app.modules.game.models import GameDefinition
from app.modules.prop.models import GamePropRule, PropDefinition

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPORTED_SEED_PATH = REPO_ROOT / "game-hub" / "dist" / "game-seed.json"
IMPORT_PATH = "/api/game-hub/admin/config/import-game-seed"


def _minimal_seed() -> dict:
    """最小可导入种子，便于构造孤儿数据场景。"""
    return {
        "props": [
            {
                "propCode": "test_prop_keep",
                "propName": "保留道具",
                "basePrice": 1,
                "enabled": True,
            }
        ],
        "games": [
            {
                "gameCode": "test_game_keep",
                "gameName": "保留游戏",
                "supportOnline": False,
                "enabled": True,
                "sortNo": 99,
                "config": {},
                "difficulties": [
                    {
                        "difficultyCode": "easy",
                        "difficultyName": "简单",
                        "enabled": True,
                        "sortNo": 1,
                        "config": {},
                    }
                ],
                "clientConfigs": [],
                "propRules": [],
            }
        ],
    }


@pytest.fixture()
def client() -> TestClient:
    """提供已建表的测试客户端。"""
    init_db()
    with TestClient(app) as test_client:
        yield test_client


def test_import_invalid_import_mode_returns_param_error(client: TestClient) -> None:
    """非法 importMode 返回参数错误。"""
    resp = client.post(
        IMPORT_PATH,
        params={"importMode": "invalid"},
        json=_minimal_seed(),
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["code"] == 10002
    assert "importMode" in body["message"]


def test_import_invalid_delete_mode_returns_param_error(client: TestClient) -> None:
    """非法 deleteMode 返回参数错误。"""
    resp = client.post(
        IMPORT_PATH,
        params={"importMode": "full", "deleteMode": "wipe"},
        json=_minimal_seed(),
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["code"] == 10002
    assert "deleteMode" in body["message"]


def test_merge_mode_does_not_remove_orphan_game(client: TestClient) -> None:
    """merge 模式不删除种子未提及的库内游戏。"""
    orphan_code = "test_game_orphan_merge"
    seed_first = _minimal_seed()
    seed_first["games"].append(
        {
            "gameCode": orphan_code,
            "gameName": "孤儿游戏",
            "supportOnline": False,
            "enabled": True,
            "sortNo": 100,
            "config": {},
            "difficulties": [],
            "clientConfigs": [],
            "propRules": [],
        }
    )
    assert client.post(IMPORT_PATH, params={"importMode": "merge"}, json=seed_first).json()["code"] == 0

    seed_second = _minimal_seed()
    assert client.post(IMPORT_PATH, params={"importMode": "merge"}, json=seed_second).json()["code"] == 0

    with SessionLocal() as session:
        orphan = session.scalar(
            select(GameDefinition).where(GameDefinition.game_code == orphan_code)
        )
        assert orphan is not None
        assert orphan.deleted_at is None


def test_full_logical_disables_orphan_game(client: TestClient) -> None:
    """full + logical 软删并禁用种子未提及的游戏。"""
    orphan_code = "test_game_orphan_logical"
    seed_first = _minimal_seed()
    seed_first["games"].append(
        {
            "gameCode": orphan_code,
            "gameName": "待逻辑删除",
            "supportOnline": False,
            "enabled": True,
            "sortNo": 101,
            "config": {},
            "difficulties": [],
            "clientConfigs": [],
            "propRules": [],
        }
    )
    assert (
        client.post(
            IMPORT_PATH,
            params={"importMode": "merge"},
            json=seed_first,
        ).json()["code"]
        == 0
    )

    assert (
        client.post(
            IMPORT_PATH,
            params={"importMode": "full", "deleteMode": "logical"},
            json=_minimal_seed(),
        ).json()["code"]
        == 0
    )

    with SessionLocal() as session:
        orphan = session.scalar(
            select(GameDefinition).where(GameDefinition.game_code == orphan_code)
        )
        assert orphan is not None
        assert orphan.deleted_at is not None
        assert orphan.enabled == 0


def test_full_physical_removes_orphan_game(client: TestClient) -> None:
    """full + physical 物理删除种子未提及的游戏。"""
    orphan_code = "test_game_orphan_physical"
    seed_first = _minimal_seed()
    seed_first["games"].append(
        {
            "gameCode": orphan_code,
            "gameName": "待物理删除",
            "supportOnline": False,
            "enabled": True,
            "sortNo": 102,
            "config": {},
            "difficulties": [],
            "clientConfigs": [],
            "propRules": [],
        }
    )
    assert client.post(IMPORT_PATH, params={"importMode": "merge"}, json=seed_first).json()["code"] == 0
    assert (
        client.post(
            IMPORT_PATH,
            params={"importMode": "full", "deleteMode": "physical"},
            json=_minimal_seed(),
        ).json()["code"]
        == 0
    )

    with SessionLocal() as session:
        orphan = session.scalar(
            select(GameDefinition).where(GameDefinition.game_code == orphan_code)
        )
        assert orphan is None


def test_full_physical_removes_orphan_prop_after_rules(client: TestClient) -> None:
    """物理删除道具前先清理关联 game_prop_rule。"""
    orphan_prop = "test_prop_orphan_physical"
    seed_first = _minimal_seed()
    seed_first["props"].append(
        {
            "propCode": orphan_prop,
            "propName": "待删道具",
            "basePrice": 2,
            "enabled": True,
        }
    )
    seed_first["games"][0]["propRules"] = [
        {
            "propCode": orphan_prop,
            "sortNo": 1,
            "price": 1,
            "enabled": True,
            "rule": {},
        }
    ]
    assert client.post(IMPORT_PATH, params={"importMode": "merge"}, json=seed_first).json()["code"] == 0

    assert (
        client.post(
            IMPORT_PATH,
            params={"importMode": "full", "deleteMode": "physical"},
            json=_minimal_seed(),
        ).json()["code"]
        == 0
    )

    with SessionLocal() as session:
        prop = session.scalar(
            select(PropDefinition).where(PropDefinition.prop_code == orphan_prop)
        )
        rules = list(
            session.scalars(
                select(GamePropRule).where(GamePropRule.prop_code == orphan_prop)
            ).all()
        )
        assert prop is None
        assert rules == []


@pytest.mark.skipif(
    not EXPORTED_SEED_PATH.is_file(),
    reason="请先在 game-hub 目录执行 npm run export:seed",
)
def test_merge_import_exported_seed_default_params(client: TestClient) -> None:
    """默认 query 为 merge + logical，可导入完整 game-seed.json。"""
    payload = json.loads(EXPORTED_SEED_PATH.read_text(encoding="utf-8"))
    resp = client.post(IMPORT_PATH, json=payload)
    body = resp.json()
    assert resp.status_code == 200
    assert body["code"] == 0
    assert body["data"]["importMode"] == "merge"
    assert body["data"]["deleteMode"] == "logical"
