"""同步域校验、sync_log 写入与 payload 解析辅助。"""

import json
from typing import Any, Dict, List, Optional

from app.core.database import new_entity_ids
from app.common.exceptions import ValidationException
from app.core.time_utils import now_ms
from app.modules.sync.models import SyncLog
from app.modules.sync.repository import SyncLogRepository
from app.modules.sync.schemas import PendingEvent


class SyncLogEntityService:
    """同步日志实体：云存档批次结束后追加审计记录。"""

    def __init__(self, repository: SyncLogRepository) -> None:
        self._repository = repository

    def append_cloud_save(
        self,
        *,
        user_id: str,
        device_id: str,
        sync_result: str,
        pending_count: int,
        success_count: int,
        fail_count: int,
        error_message: Optional[str],
        payload_json: Optional[str] = None,
        duplicate_count: int = 0,
        start_time: Optional[int] = None,
        finish_time: Optional[int] = None,
        client_snapshot_version: Optional[int] = None,
        processed_client_ids: Optional[List[str]] = None,
    ) -> SyncLog:
        """
        写入一条云存档同步审计日志（含同步开始/结束元数据）。

        :param user_id: 用户主键。
        :param device_id: 设备 ID。
        :param sync_result: ``success`` / ``partial`` / ``failed``。
        :param pending_count: 本批收到事件数（receivedCount）。
        :param success_count: 新写入成功数（不含 duplicate）。
        :param fail_count: 失败数。
        :param error_message: 聚合错误信息，可空。
        :param payload_json: 附加 JSON；未传时由审计字段自动组装。
        :param duplicate_count: 幂等重复数。
        :param start_time: 同步开始时间（毫秒），可空则用当前时间。
        :param finish_time: 同步结束时间（毫秒），可空则用当前时间。
        :param client_snapshot_version: 客户端快照版本，可空。
        :param processed_client_ids: 本批 clientId 列表，可空。
        :return: 新日志实体。
        """
        sync_start = start_time if start_time is not None else now_ms()
        sync_finish = finish_time if finish_time is not None else now_ms()
        audit_payload: Dict[str, Any] = {
            "userId": user_id,
            "deviceId": device_id,
            "startTime": sync_start,
            "finishTime": sync_finish,
            "receivedCount": pending_count,
            "successCount": success_count,
            "duplicateCount": duplicate_count,
            "failCount": fail_count,
            "clientSnapshotVersion": client_snapshot_version,
            "processedClientIds": processed_client_ids or [],
        }
        if payload_json is not None and str(payload_json).strip():
            try:
                extra = json.loads(payload_json)
                if isinstance(extra, dict):
                    audit_payload.update(extra)
            except json.JSONDecodeError:
                audit_payload["rawPayload"] = payload_json
        merged_payload = json.dumps(audit_payload, ensure_ascii=False, separators=(",", ":"))
        server_id, created_at, updated_at = new_entity_ids("sync_log")
        entity = SyncLog(
            server_id=server_id,
            user_id=user_id,
            device_id=device_id,
            sync_type="cloud_save",
            sync_result=sync_result,
            pending_count=pending_count,
            success_count=success_count,
            fail_count=fail_count,
            error_message=error_message,
            payload_json=merged_payload,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity)


def payload_get(payload: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    从事件 payload 中读取 camelCase 字段。

    :param payload: 事件载荷。
    :param key: 字段名（camelCase）。
    :param default: 未命中时的默认值。
    :return: 字段值或默认值。
    """
    return payload.get(key, default)


def payload_str(payload: Dict[str, Any], key: str, default: Optional[str] = None) -> Optional[str]:
    """
    读取字符串字段。

    :param payload: 事件载荷。
    :param key: camelCase 字段名。
    :param default: 默认值。
    :return: 字符串或默认值。
    """
    value = payload_get(payload, key, default=default)
    if value is None:
        return default
    return str(value)


def payload_int(payload: Dict[str, Any], key: str, default: Optional[int] = None) -> Optional[int]:
    """
    读取整数字段。

    :param payload: 事件载荷。
    :param key: camelCase 字段名。
    :param default: 默认值。
    :return: 整数或默认值。
    """
    value = payload_get(payload, key, default=default)
    if value is None:
        return default
    return int(value)


def payload_bool(payload: Dict[str, Any], key: str, default: bool = False) -> bool:
    """
    读取布尔字段。

    :param payload: 事件载荷。
    :param key: camelCase 字段名。
    :param default: 默认值。
    :return: 布尔值。
    """
    value = payload_get(payload, key, default=default)
    if isinstance(value, bool):
        return value
    if value in (1, "1", "true", "True"):
        return True
    if value in (0, "0", "false", "False"):
        return False
    return default


def payload_object(payload: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
    """
    读取对象字段（必须为 JSON 对象）。

    :param payload: 事件载荷。
    :param key: camelCase 字段名。
    :return: 字典或 ``None``。
    :raises ValidationException: 字段存在但类型非对象。
    """
    value = payload_get(payload, key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValidationException(f"payload.{key} 必须为对象")
    return value


def payload_array(payload: Dict[str, Any], key: str) -> Optional[List[Any]]:
    """
    读取数组字段（必须为 JSON 数组）。

    :param payload: 事件载荷。
    :param key: camelCase 字段名。
    :return: 列表或 ``None``。
    :raises ValidationException: 字段存在但类型非数组。
    """
    value = payload_get(payload, key)
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValidationException(f"payload.{key} 必须为数组")
    return value


def require_fields(payload: Dict[str, Any], fields: List[str], event: PendingEvent) -> None:
    """
    校验 payload 必填字段（仅 camelCase）。

    :param payload: 事件载荷。
    :param fields: camelCase 字段名列表。
    :param event: 当前事件（用于错误信息）。
    :raises ValidationException: 缺少必填字段。
    """
    for field in fields:
        if field in payload:
            continue
        raise ValidationException(
            f"事件 payload 缺少字段 {field}: eventType={event.eventType}, clientId={event.clientId}"
        )


def as_optional_str(value: Any) -> Optional[str]:
    """
    将值转为可选字符串。

    :param value: 原始值。
    :return: 字符串或 ``None``。
    """
    if value is None:
        return None
    return str(value)


def as_required_str(value: Any, field_name: str) -> str:
    """
    将值转为非空字符串。

    :param value: 原始值。
    :param field_name: 字段名（错误信息用）。
    :return: 非空字符串。
    :raises ValidationException: 值为空。
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValidationException(f"字段 {field_name} 不能为空")
    return str(value)


def merge_setting_with_sync_meta(
    setting: Optional[Dict[str, Any]],
    event_client_id: str,
) -> Dict[str, Any]:
    """
    在设置 JSON 中记录已处理的同步事件 clientId（用于无独立流水表时的幂等）。

    :param setting: 原设置字典，可为空。
    :param event_client_id: 事件 clientId。
    :return: 合并后的设置字典。
    """
    base: Dict[str, Any] = dict(setting) if setting else {}
    sync_meta = dict(base.get("_sync") or {})
    processed = list(sync_meta.get("processedClientIds") or [])
    if event_client_id not in processed:
        processed.append(event_client_id)
    sync_meta["processedClientIds"] = processed
    base["_sync"] = sync_meta
    return base


def is_event_client_processed(setting: Optional[Dict[str, Any]], event_client_id: str) -> bool:
    """
    判断游戏/系统设置 JSON 中是否已记录该事件 clientId。

    :param setting: 设置字典。
    :param event_client_id: 事件 clientId。
    :return: 是否已处理。
    """
    if not setting:
        return False
    sync_meta = setting.get("_sync") or {}
    processed = sync_meta.get("processedClientIds") or []
    return event_client_id in processed
