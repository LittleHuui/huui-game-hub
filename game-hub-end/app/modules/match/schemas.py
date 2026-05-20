"""对局域 Pydantic 模型。"""

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.boot.schemas import MatchRecordResponse
from app.modules.match.models import MatchRecord


def object_to_json_text(value: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    将对象序列化为存库 JSON 文本。

    :param value: 字典，可空。
    :return: JSON 文本或 ``None``。
    """
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def array_to_json_text(value: Optional[List[Any]]) -> Optional[str]:
    """
    将数组序列化为存库 JSON 文本。

    :param value: 列表，可空。
    :return: JSON 文本或 ``None``。
    """
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def parse_optional_json_object(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    将存库 JSON 文本解析为对象；解析失败或非对象时返回 ``None``。

    :param raw: JSON 文本，可空。
    :return: 字典或 ``None``。
    """
    if raw is None or not str(raw).strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def parse_optional_json_array(raw: Optional[str]) -> Optional[List[Any]]:
    """
    将存库 JSON 文本解析为数组；解析失败或非数组时返回 ``None``。

    :param raw: JSON 文本，可空。
    :return: 列表或 ``None``。
    """
    if raw is None or not str(raw).strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    return parsed


def to_match_record_response(record: MatchRecord) -> MatchRecordResponse:
    """
    将对局 ORM 转为 API 响应模型。

    :param record: 对局记录实体。
    :return: ``MatchRecordResponse``。
    """
    return MatchRecordResponse(
        serverId=record.server_id,
        clientId=record.client_id,
        userId=record.user_id,
        deviceId=record.device_id,
        gameCode=record.game_code.strip(),
        mode=record.mode,
        result=record.result,
        difficultyCode=record.difficulty_code,
        durationMs=record.duration_ms,
        score=record.score,
        propUses=parse_optional_json_array(record.prop_uses_json),
        payload=parse_optional_json_object(record.payload_json),
        syncedAt=record.synced_at,
        createdAt=record.created_at,
        updatedAt=record.updated_at,
        deletedAt=record.deleted_at,
    )


class MatchRecordCreate(BaseModel):
    """创建对局记录请求体（camelCase）。"""

    model_config = ConfigDict(extra="forbid")

    clientId: str = Field(min_length=1)
    userId: str = Field(min_length=1)
    deviceId: Optional[str] = None
    gameCode: str = Field(min_length=1)
    mode: str = Field(min_length=1)
    result: str = Field(min_length=1)
    difficultyCode: Optional[str] = None
    durationMs: Optional[int] = Field(default=None, ge=0)
    score: int = 0
    propUses: Optional[List[Any]] = None
    payload: Optional[Dict[str, Any]] = None


class MatchActionRecordCreate(BaseModel):
    """创建单条对局操作记录请求体（camelCase）。"""

    model_config = ConfigDict(extra="forbid")

    clientId: str = Field(min_length=1)
    matchId: str = Field(min_length=1)
    userId: str = Field(min_length=1)
    deviceId: Optional[str] = None
    gameCode: str = Field(min_length=1)
    actionType: str = Field(min_length=1)
    actionSeq: int = Field(ge=0)
    actionTimeMs: int = Field(ge=0)
    payload: Optional[Dict[str, Any]] = None


class MatchActionBatchCreate(BaseModel):
    """批量创建对局操作记录请求体。"""

    model_config = ConfigDict(extra="forbid")

    items: List[MatchActionRecordCreate] = Field(min_length=1)


class MatchActionBatchResult(BaseModel):
    """批量创建对局操作结果。"""

    model_config = ConfigDict(extra="forbid")

    createdCount: int


class ScoreRecordCreate(BaseModel):
    """创建成绩记录请求体（camelCase）。"""

    model_config = ConfigDict(extra="forbid")

    clientId: str = Field(min_length=1)
    userId: str = Field(min_length=1)
    deviceId: Optional[str] = None
    gameCode: str = Field(min_length=1)
    mode: str = Field(min_length=1)
    difficultyCode: Optional[str] = None
    result: str = Field(min_length=1)
    score: int
    durationMs: Optional[int] = Field(default=None, ge=0)
    payload: Optional[Dict[str, Any]] = None

