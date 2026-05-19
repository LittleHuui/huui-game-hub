"""通用 Pydantic 模型与请求上下文。"""

from typing import Optional

from fastapi import Header
from typing_extensions import Annotated
from pydantic import BaseModel, ConfigDict, Field


class ClientContext(BaseModel):
    """预留的客户端身份上下文（当前不做鉴权，仅从请求头读取）。"""

    model_config = ConfigDict(from_attributes=True)

    user_id: Optional[str] = Field(default=None, description="预留用户 ID")
    device_id: Optional[str] = Field(default=None, description="预留设备 ID")


def get_client_context(
    x_user_id: Annotated[Optional[str], Header(alias="X-User-Id")] = None,
    x_device_id: Annotated[Optional[str], Header(alias="X-Device-Id")] = None,
) -> ClientContext:
    """
    从请求头解析用户与设备标识，供后续鉴权与埋点扩展。

    :param x_user_id: 可选用户 ID。
    :param x_device_id: 可选设备 ID。
    :return: ``ClientContext``。
    """
    return ClientContext(user_id=x_user_id, device_id=x_device_id)


class HealthData(BaseModel):
    """健康检查数据载荷。"""

    model_config = ConfigDict(from_attributes=True)

    serverTime: int = Field(description="服务器当前 Unix 毫秒时间戳")
    status: str = Field(description="服务状态文案")


class EchoRequest(BaseModel):
    """示例 JSON 入参（用于验证统一 JSON 约定）。"""

    model_config = ConfigDict(from_attributes=True)

    ping: str = Field(min_length=1, description="任意非空字符串")


class EchoData(BaseModel):
    """示例 JSON 出参。"""

    model_config = ConfigDict(from_attributes=True)

    pong: str
    userId: Optional[str] = None
    deviceId: Optional[str] = None
