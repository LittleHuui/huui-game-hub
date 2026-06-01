"""用户域创建账号接口测试。"""

import uuid

from fastapi.testclient import TestClient

from app.main import app


def test_create_user_account() -> None:
    """创建用户应返回统一 JSON 结构。"""
    suffix = uuid.uuid4().hex[:10]
    with TestClient(app) as client:
        response = client.post(
            "/api/game-hub/users/",
            json={
                "clientId": f"client_{suffix}",
                "username": f"user_{suffix}",
                "nickname": "测试昵称",
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["data"]["username"] == f"user_{suffix}"
    assert payload["data"]["status"] == "normal"
    assert isinstance(payload["data"]["createdAt"], int)
