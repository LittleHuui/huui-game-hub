"""健康检查接口测试。"""

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_unified_envelope() -> None:
    """健康检查应返回统一 JSON 结构且包含服务器时间与状态。"""
    with TestClient(app) as client:
        response = client.get("/api/game-hub/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["message"] == "success"
    assert isinstance(payload["data"]["serverTime"], int)
    assert payload["data"]["status"] == "ok"
