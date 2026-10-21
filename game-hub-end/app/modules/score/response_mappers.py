"""成绩响应投影。"""
import json
from typing import Any, Dict, Optional
from app.common.exceptions import ValidationException
from app.modules.score.models import ScoreRecord
from app.modules.score.response_schemas import ScoreRecordResponse


def _parse_optional_json_dict(raw: Optional[str], *, strict: bool = True) -> Optional[Dict[str, Any]]:
    """
    将存库 JSON 文本解析为字典。

    :param raw: JSON 文本，可空。
    :param strict: 为 ``False`` 时解析失败返回 ``None`` 而不抛错。
    :return: 字典或 ``None``。
    :raises ValidationException: 严格模式下解析失败或类型非对象。
    """
    if raw is None or not str(raw).strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        if not strict:
            return None
        raise ValidationException(f"JSON 解析失败: {exc}") from exc
    if parsed is None:
        return None
    if not isinstance(parsed, dict):
        if not strict:
            return None
        raise ValidationException("JSON 必须为对象")
    return parsed

def to_score_record_response(record: ScoreRecord) -> ScoreRecordResponse:
    """
    将成绩记录 ORM 转为启动模块响应。

    :param record: 成绩记录实体。
    :return: ``ScoreRecordResponse``。
    """
    return ScoreRecordResponse(
        serverId=record.server_id,
        clientId=record.client_id,
        userId=record.user_id,
        deviceId=record.device_id,
        gameCode=record.game_code,
        mode=record.mode,
        difficultyCode=record.difficulty_code,
        result=record.result,
        score=record.score,
        durationMs=record.duration_ms,
        payload=_parse_optional_json_dict(record.payload_json, strict=False),
        syncedAt=record.synced_at,
        createdAt=record.created_at,
        updatedAt=record.updated_at,
        deletedAt=record.deleted_at,
    )
