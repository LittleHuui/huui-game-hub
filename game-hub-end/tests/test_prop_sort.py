"""游戏道具规则 sort_no / sortNo 排序测试。"""

import uuid

from fastapi.testclient import TestClient

from app.core.database import init_db
from app.main import app


def test_prop_rules_sorted_by_seed_sort_no() -> None:
    """import 时写入 propRules.sortNo 至 sort_no；列表按 sort_no 升序（同序 tie-break prop_code），与数组顺序无关。"""
    init_db()

    suffix = uuid.uuid4().hex[:8]
    game_code = f"sort_test_{suffix}"
    prop_z = f"z_prop_{suffix}"
    prop_a = f"a_prop_{suffix}"
    prop_m = f"m_prop_{suffix}"

    seed_body = {
        "props": [
            {
                "propCode": prop_z,
                "propName": "Z 道具",
                "basePrice": 10,
                "enabled": True,
            },
            {
                "propCode": prop_a,
                "propName": "A 道具",
                "basePrice": 20,
                "enabled": True,
            },
            {
                "propCode": prop_m,
                "propName": "M 道具",
                "basePrice": 30,
                "enabled": True,
            },
        ],
        "games": [
            {
                "gameCode": game_code,
                "gameName": "排序测试游戏",
                "supportOnline": False,
                "enabled": True,
                "sortNo": 99,
                "config": {},
                "propRules": [
                    {
                        "propCode": prop_m,
                        "sortNo": 30,
                        "price": 300,
                        "enabled": True,
                        "rule": {},
                    },
                    {
                        "propCode": prop_z,
                        "sortNo": 10,
                        "price": 100,
                        "enabled": True,
                        "rule": {},
                    },
                    {
                        "propCode": prop_a,
                        "sortNo": 20,
                        "price": 200,
                        "enabled": True,
                        "rule": {},
                    },
                ],
            }
        ],
    }

    with TestClient(app) as client:
        import_resp = client.post("/api/game-hub/admin/config/import-game-seed", json=seed_body)
        assert import_resp.status_code == 200

        props_resp = client.get(f"/api/game-hub/games/{game_code}/props")
        assert props_resp.status_code == 200
        props_items = props_resp.json()["data"]
        assert [item["propCode"] for item in props_items] == [prop_z, prop_a, prop_m]
        assert [item["sortNo"] for item in props_items] == [10, 20, 30]

        config_resp = client.get(f"/api/game-hub/games/{game_code}/config")
        assert config_resp.status_code == 200
        config_props = config_resp.json()["data"]["props"]
        assert [item["propCode"] for item in config_props] == [prop_z, prop_a, prop_m]
        assert [item["sortNo"] for item in config_props] == [10, 20, 30]
