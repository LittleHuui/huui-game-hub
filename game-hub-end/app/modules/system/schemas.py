"""系统域 Pydantic 模型。"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.common.base_entity import BaseEntityResponse
from app.common.camel_schema import CAMEL_MODEL_CONFIG
from app.modules.system.models import SystemConfig


class SystemConfigResponse(BaseEntityResponse):
    """系统配置 HTTP 响应。"""

    model_config = ConfigDict(extra="forbid")

    configKey: str
    configValue: Optional[str] = None
    description: Optional[str] = None
    enabled: int


class SystemConfigListResponse(BaseModel):
    """配置列表响应体。"""

    model_config = ConfigDict(extra="forbid")

    items: List[SystemConfigResponse]


class SystemConfigUpsert(BaseModel):
    """按 config_key 创建或更新配置。"""

    model_config = CAMEL_MODEL_CONFIG

    configValue: Optional[str] = Field(default=None)
    description: Optional[str] = None
    enabled: Optional[int] = Field(default=None, description="0 禁用，1 启用")


def system_config_to_response(entity: SystemConfig) -> SystemConfigResponse:
    """
    将系统配置 ORM 转为 HTTP 响应。

    :param entity: 系统配置实体。
    :return: ``SystemConfigResponse``。
    """
    return SystemConfigResponse(
        serverId=entity.server_id,
        createdAt=entity.created_at,
        updatedAt=entity.updated_at,
        deletedAt=entity.deleted_at,
        configKey=entity.config_key,
        configValue=entity.config_value,
        description=entity.description,
        enabled=entity.enabled,
    )


class RequestLogRead(BaseModel):
    """请求日志响应。"""

    model_config = ConfigDict(from_attributes=True)

    server_id: str
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    device_id: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    query_string: Optional[str] = None
    status_code: Optional[int] = None
    duration_ms: Optional[int] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    payload_json: Optional[str] = None
    created_at: int
    updated_at: int
    deleted_at: Optional[int] = None


class LoginLogRead(BaseModel):
    """登录日志响应。"""

    model_config = ConfigDict(from_attributes=True)

    server_id: str
    user_id: Optional[str] = None
    device_id: Optional[str] = None
    login_type: Optional[str] = None
    login_result: Optional[str] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    payload_json: Optional[str] = None
    created_at: int
    updated_at: int
    deleted_at: Optional[int] = None

