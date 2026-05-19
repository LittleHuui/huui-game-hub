"""背包域 ORM 与 API 响应转换。"""

import json
from typing import Any, Dict, Optional

from app.modules.boot.schemas import PropUsageRecordResponse, UserPropBagResponse
from app.modules.inventory.models import PropUsageRecord, UserPropBag


def _parse_optional_json_dict(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    将存库 JSON 文本解析为字典；解析失败时返回 ``None``。

    :param raw: JSON 文本，可空。
    :return: 字典或 ``None``。
    """
    if raw is None or not str(raw).strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if parsed is None:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def to_user_prop_bag_response(row: UserPropBag) -> UserPropBagResponse:
    """
    将背包行 ORM 转为 API 响应。

    :param row: 背包实体。
    :return: ``UserPropBagResponse``。
    """
    return UserPropBagResponse(
        serverId=row.server_id,
        userId=row.user_id,
        gameCode=row.game_code,
        propCode=row.prop_code,
        quantity=row.quantity,
        createdAt=row.created_at,
        updatedAt=row.updated_at,
        deletedAt=row.deleted_at,
    )


def to_prop_usage_record_response(record: PropUsageRecord) -> PropUsageRecordResponse:
    """
    将道具使用记录 ORM 转为 API 响应。

    :param record: 使用记录实体。
    :return: ``PropUsageRecordResponse``。
    """
    return PropUsageRecordResponse(
        serverId=record.server_id,
        clientId=record.client_id,
        userId=record.user_id,
        deviceId=record.device_id,
        gameCode=record.game_code,
        matchId=record.match_id,
        propCode=record.prop_code,
        quantity=record.quantity,
        useReason=record.use_reason,
        payload=_parse_optional_json_dict(record.payload_json),
        syncedAt=record.synced_at,
        createdAt=record.created_at,
        updatedAt=record.updated_at,
        deletedAt=record.deleted_at,
    )
