"""对局域 Pydantic 模型。"""

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.common.camel_schema import CAMEL_MODEL_CONFIG, camel_field
from app.modules.boot.schemas import MatchRecordResponse
from app.modules.match.models import MatchRecord


def parse_optional_json_dict(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    将存库 JSON 文本解析为字典；解析失败或非对象时返回 ``None``。

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
        gameCode=record.game_code,
        mode=record.mode,
        result=record.result,
        difficultyCode=record.difficulty_code,
        durationMs=record.duration_ms,
        score=record.score,
        propUses=parse_optional_json_dict(record.prop_uses_json),
        payload=parse_optional_json_dict(record.payload_json),
        syncedAt=record.synced_at,
        createdAt=record.created_at,
        updatedAt=record.updated_at,
        deletedAt=record.deleted_at,
    )


class MatchRecordCreate(BaseModel):
    """创建对局记录请求体。"""

    model_config = CAMEL_MODEL_CONFIG

    clientId: str = camel_field("clientId", min_length=1)
    userId: str = camel_field("userId", min_length=1)
    deviceId: Optional[str] = camel_field("deviceId", default=None)
    gameCode: str = camel_field("gameCode", min_length=1)
    mode: str = Field(min_length=1)
    result: str = Field(min_length=1)
    difficultyCode: Optional[str] = camel_field("difficultyCode", default=None)
    durationMs: Optional[int] = camel_field("durationMs", default=None, ge=0)
    score: int = 0
    propUsesJson: Optional[str] = camel_field("propUsesJson", default=None)
    payloadJson: Optional[str] = camel_field("payloadJson", default=None)


class MatchRecordRead(BaseModel):
    """对局记录响应。"""

    model_config = ConfigDict(from_attributes=True)

    server_id: str
    client_id: str
    user_id: str
    device_id: Optional[str] = None
    game_code: str
    mode: str
    result: str
    difficulty_code: Optional[str] = None
    duration_ms: Optional[int] = None
    score: int
    prop_uses_json: Optional[str] = None
    payload_json: Optional[str] = None
    created_at: int
    updated_at: int
    synced_at: Optional[int] = None
    deleted_at: Optional[int] = None


class MatchRecordListData(BaseModel):
    """用户对局列表响应体。"""

    model_config = ConfigDict(extra="forbid")

    items: List[MatchRecordRead]


class MatchActionRecordCreate(BaseModel):
    """创建单条对局操作记录请求体。"""

    model_config = CAMEL_MODEL_CONFIG

    clientId: str = camel_field("clientId", min_length=1)
    matchId: str = camel_field("matchId", min_length=1)
    userId: str = camel_field("userId", min_length=1)
    deviceId: Optional[str] = camel_field("deviceId", default=None)
    gameCode: str = camel_field("gameCode", min_length=1)
    actionType: str = camel_field("actionType", min_length=1)
    actionSeq: int = camel_field("actionSeq", ge=0)
    actionTimeMs: int = camel_field("actionTimeMs", ge=0)
    payloadJson: Optional[str] = camel_field("payloadJson", default=None)


class MatchActionRecordRead(BaseModel):
    """对局操作记录响应。"""

    model_config = ConfigDict(from_attributes=True)

    server_id: str
    client_id: str
    match_id: str
    user_id: str
    device_id: Optional[str] = None
    game_code: str
    action_type: str
    action_seq: int
    action_time_ms: int
    payload_json: Optional[str] = None
    created_at: int
    updated_at: int
    synced_at: Optional[int] = None
    deleted_at: Optional[int] = None


class MatchActionBatchCreate(BaseModel):
    """批量创建对局操作记录请求体。"""

    model_config = ConfigDict(extra="forbid")

    items: List[MatchActionRecordCreate] = Field(min_length=1)


class MatchActionListData(BaseModel):
    """对局操作列表响应体。"""

    model_config = ConfigDict(extra="forbid")

    items: List[MatchActionRecordRead]


class MatchActionBatchResult(BaseModel):
    """批量创建对局操作结果。"""

    model_config = ConfigDict(extra="forbid")

    items: List[MatchActionRecordRead]
    created_count: int


class ScoreRecordCreate(BaseModel):
    """创建成绩记录请求体。"""

    model_config = CAMEL_MODEL_CONFIG

    clientId: str = camel_field("clientId", min_length=1)
    userId: str = camel_field("userId", min_length=1)
    deviceId: Optional[str] = camel_field("deviceId", default=None)
    gameCode: str = camel_field("gameCode", min_length=1)
    mode: str = Field(min_length=1)
    difficultyCode: Optional[str] = camel_field("difficultyCode", default=None)
    result: str = Field(min_length=1)
    score: int
    durationMs: Optional[int] = camel_field("durationMs", default=None, ge=0)
    payloadJson: Optional[str] = camel_field("payloadJson", default=None)


class ScoreRecordRead(BaseModel):
    """成绩记录响应。"""

    model_config = ConfigDict(from_attributes=True)

    server_id: str
    client_id: str
    user_id: str
    device_id: Optional[str] = None
    game_code: str
    mode: str
    difficulty_code: Optional[str] = None
    result: str
    score: int
    duration_ms: Optional[int] = None
    payload_json: Optional[str] = None
    created_at: int
    updated_at: int
    synced_at: Optional[int] = None
    deleted_at: Optional[int] = None
