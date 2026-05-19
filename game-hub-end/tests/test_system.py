"""系统域配置接口测试。"""

import uuid

from fastapi.testclient import TestClient

from app.main import app


def test_list_and_upsert_system_configs() -> None:
    """列出配置、按 key 写入并再次列出应包含该配置。"""
    suffix = uuid.uuid4().hex[:10]
    config_key = f"test.feature.{suffix}"
    with TestClient(app) as client:
        put_resp = client.put(
            f"/api/game-hub/system/configs/{config_key}",
            json={
                "config_value": "on",
                "description": "测试开关",
                "enabled": 1,
            },
        )
        assert put_resp.status_code == 200
        saved = put_resp.json()["data"]
        assert saved["configKey"] == config_key
        assert saved["configValue"] == "on"
        assert saved["description"] == "测试开关"
        assert saved["enabled"] == 1
        assert saved["serverId"].startswith("system_config_")

        update_resp = client.put(
            f"/api/game-hub/system/configs/{config_key}",
            json={"config_value": "off", "enabled": 0},
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()["data"]
        assert updated["configValue"] == "off"
        assert updated["enabled"] == 0
        assert updated["serverId"] == saved["serverId"]

        list_resp = client.get("/api/game-hub/system/configs")
        assert list_resp.status_code == 200
        keys = [item["configKey"] for item in list_resp.json()["data"]["items"]]
        assert config_key in keys
