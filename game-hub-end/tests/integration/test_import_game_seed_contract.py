"""当前导出 game-seed.json 与 import-game-seed 契约一致性测试。"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, init_db
from app.main import app
from app.modules.prop.models import GamePropRule

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPORTED_SEED_PATH = REPO_ROOT / "game-hub" / "dist" / "game-seed.json"


@pytest.mark.skipif(
    not EXPORTED_SEED_PATH.is_file(),
    reason="请先在 game-hub 目录执行 npm run export:seed 生成 dist/game-seed.json",
)
def test_import_exported_game_seed_full_contract() -> None:
    """导入 dist/game-seed.json，校验 propRules.sortNo 落库及 props/config 与难度内 propUseLimits 结构。"""
    init_db()
    payload = json.loads(EXPORTED_SEED_PATH.read_text(encoding="utf-8"))

    with TestClient(app) as client:
        resp = client.post("/api/game-hub/admin/config/import-game-seed", json=payload)
        assert resp.status_code == 200, resp.text

        ms_props = client.get("/api/game-hub/games/minesweeper/props").json()["data"]
        assert [row["propCode"] for row in ms_props] == ["hint_card", "revive_card"]
        assert [row["sortNo"] for row in ms_props] == [1, 2]

        m3_props = client.get("/api/game-hub/games/match3/props").json()["data"]
        assert [row["propCode"] for row in m3_props] == ["match3_shuffle", "match3_bomb"]
        assert [row["sortNo"] for row in m3_props] == [1, 2]

        m3_cfg = client.get("/api/game-hub/games/match3/config").json()["data"]
        assert m3_cfg["game"]["gameCode"] == "match3"
        diff_normal = next(d for d in m3_cfg["difficulties"] if d["difficultyCode"] == "normal")
        modes = diff_normal["config"]["modes"]
        assert isinstance(modes["timed"]["propUseLimits"], list)
        assert modes["timed"]["propUseLimits"][0] == {
            "propCode": "match3_shuffle",
            "maxUse": 2,
        }
        assert isinstance(modes["endless"]["propUseLimits"], list)

        cfg_props = m3_cfg["props"]
        assert [p["sortNo"] for p in cfg_props] == [1, 2]

        ms_cfg = client.get("/api/game-hub/games/minesweeper/config").json()["data"]
        assert ms_cfg["game"]["gameCode"] == "minesweeper"
        assert len(ms_cfg["difficulties"]) >= 1
        assert [p["sortNo"] for p in ms_cfg["props"]] == [1, 2]

    with SessionLocal() as session:
        ms_rules = list(
            session.scalars(
                select(GamePropRule).where(
                    GamePropRule.game_code == "minesweeper",
                    GamePropRule.enabled == 1,
                    GamePropRule.deleted_at.is_(None),
                )
            ).all()
        )
        by_prop = {r.prop_code: r.sort_no for r in ms_rules}
        assert by_prop.get("hint_card") == 1
        assert by_prop.get("revive_card") == 2

        m3_rules = list(
            session.scalars(
                select(GamePropRule).where(
                    GamePropRule.game_code == "match3",
                    GamePropRule.enabled == 1,
                    GamePropRule.deleted_at.is_(None),
                )
            ).all()
        )
        by_prop_m3 = {r.prop_code: r.sort_no for r in m3_rules}
        assert by_prop_m3.get("match3_shuffle") == 1
        assert by_prop_m3.get("match3_bomb") == 2
