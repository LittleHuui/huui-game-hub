"""user_system_setting_update 云同步 LWW 测试。"""

from typing import Any, Dict, List

from fastapi.testclient import TestClient

from app.main import app
from tests.sync_helpers import cloud_save, create_test_user


def _system_setting_event(
    client_id: str,
    data_mode: str,
    updated_at: int,
) -> Dict[str, Any]:
    """
    构造 user_system_setting_update 同步事件。

    :param client_id: 事件幂等键。
    :param data_mode: dataMode 取值。
    :param updated_at: 事件 updatedAt（毫秒）。
    :return: pendingEvents 单条元素。
    """
    return {
        "clientId": client_id,
        "eventType": "user_system_setting_update",
        "createdAt": updated_at,
        "updatedAt": updated_at,
        "payload": {"setting": {"dataMode": data_mode}},
    }


def _read_data_mode(client: TestClient, user_id: str) -> str:
    """
    读取用户系统设置 dataMode。

    :param client: 测试客户端。
    :param user_id: 用户主键。
    :return: dataMode 字符串。
    """
    response = client.get(f"/api/game-hub/users/{user_id}/system-setting")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    return body["data"]["setting"]["dataMode"]


def _boot_context_data_mode(client: TestClient, user_id: str, device_id: str) -> str:
    """
    通过 boot/context 读取 systemSetting.dataMode。

    :param client: 测试客户端。
    :param user_id: 用户主键。
    :param device_id: 设备 ID。
    :return: dataMode 字符串。
    """
    response = client.post(
        "/api/game-hub/boot/context",
        json={
            "userId": user_id,
            "deviceId": device_id,
            "clientTime": 1730000000000,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["userExists"] is True
    return body["data"]["systemSetting"]["setting"]["dataMode"]


def _sync_modes(
    client: TestClient,
    user_id: str,
    device_id: str,
    events: List[Dict[str, Any]],
) -> str:
    """
    云存档同步后读取 dataMode。

    :param client: 测试客户端。
    :param user_id: 用户主键。
    :param device_id: 设备 ID。
    :param events: pendingEvents。
    :return: 同步后 dataMode。
    """
    snapshot = cloud_save(
        client,
        user_id=user_id,
        device_id=device_id,
        pending_events=events,
    )
    return snapshot["systemSetting"]["setting"]["dataMode"]


def test_lww_local_then_auto_by_updated_at() -> None:
    """场景一：local@100、auto@101，最终为 auto。"""
    with TestClient(app) as client:
        user_id = create_test_user(client)
        device_id = "device_lww_1"
        data_mode = _sync_modes(
            client,
            user_id,
            device_id,
            [
                _system_setting_event("evt_local_100", "local", 100),
                _system_setting_event("evt_auto_101", "auto", 101),
            ],
        )
        assert data_mode == "auto"
        assert _read_data_mode(client, user_id) == "auto"


def test_lww_auto_then_local_by_updated_at() -> None:
    """场景二：auto@100、local@101，最终为 local。"""
    with TestClient(app) as client:
        user_id = create_test_user(client)
        device_id = "device_lww_2"
        data_mode = _sync_modes(
            client,
            user_id,
            device_id,
            [
                _system_setting_event("evt_auto_100", "auto", 100),
                _system_setting_event("evt_local_101", "local", 101),
            ],
        )
        assert data_mode == "local"
        assert _read_data_mode(client, user_id) == "local"


def test_lww_same_updated_at_later_client_id_wins() -> None:
    """场景三：同 updatedAt@100，clientId 较大者后处理并覆盖。"""
    with TestClient(app) as client:
        user_id = create_test_user(client)
        device_id = "device_lww_3"
        data_mode = _sync_modes(
            client,
            user_id,
            device_id,
            [
                _system_setting_event("evt_a_local", "local", 100),
                _system_setting_event("evt_b_auto", "auto", 100),
            ],
        )
        assert data_mode == "auto"


def test_boot_context_after_local_then_auto() -> None:
    """场景四：切 local 再切 auto 同步后，boot/context 返回 auto。"""
    with TestClient(app) as client:
        user_id = create_test_user(client)
        device_id = "device_lww_4"
        _sync_modes(
            client,
            user_id,
            device_id,
            [
                _system_setting_event("evt_local_boot", "local", 200),
                _system_setting_event("evt_auto_boot", "auto", 201),
            ],
        )
        assert _boot_context_data_mode(client, user_id, device_id) == "auto"
