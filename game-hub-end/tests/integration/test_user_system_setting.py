"""用户系统设置接口测试。"""

import uuid

from fastapi.testclient import TestClient

from app.main import app


def _create_user(client: TestClient) -> str:
    """
    创建测试用户并返回 ``server_id``。

    :param client: 测试客户端。
    :return: 用户 ``server_id``。
    """
    suffix = uuid.uuid4().hex[:10]
    response = client.post(
        "/api/game-hub/users/",
        json={
            "clientId": f"client_{suffix}",
            "username": f"user_{suffix}",
            "nickname": "系统设置测试",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["serverId"]


def test_user_system_setting_get_and_put() -> None:
    """获取与更新用户系统设置应返回结构化 JSON。"""
    with TestClient(app) as client:
        user_id = _create_user(client)

        get_resp = client.get(f"/api/game-hub/users/{user_id}/system-setting")
        assert get_resp.status_code == 200
        get_payload = get_resp.json()
        assert get_payload["code"] == 0
        assert get_payload["data"]["userId"] == user_id
        assert get_payload["data"]["setting"]["dataMode"] == "auto"
        assert get_payload["data"]["setting"]["theme"] == "dark"
        assert get_payload["data"]["setting"]["language"] == "zh-CN"

        put_resp = client.put(
            f"/api/game-hub/users/{user_id}/system-setting",
            json={
                "setting": {
                    "dataMode": "remote",
                    "theme": "light",
                    "autoSync": False,
                    "language": "en-US",
                    "enableSound": False,
                    "enableAnimation": False,
                }
            },
        )
        assert put_resp.status_code == 200
        put_payload = put_resp.json()
        assert put_payload["code"] == 0
        assert put_payload["data"]["setting"]["dataMode"] == "remote"
        assert put_payload["data"]["setting"]["theme"] == "light"
        assert put_payload["data"]["setting"]["autoSync"] is False

        get_again = client.get(f"/api/game-hub/users/{user_id}/system-setting")
        assert get_again.status_code == 200
        again_data = get_again.json()["data"]["setting"]
        assert again_data["dataMode"] == "remote"
        assert again_data["theme"] == "light"
