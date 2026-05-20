"""认证模块 Pydantic 模型。"""

from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.common.camel_schema import CAMEL_MODEL_CONFIG
from app.modules.boot.schemas import UserPropBagResponse, UserWalletResponse
from app.modules.user.schemas import UserAccountResponse, UserSystemSettingResponse


class LoginRequest(BaseModel):
    """用户名登录请求体。"""

    model_config = CAMEL_MODEL_CONFIG

    username: str = Field(min_length=1, description="登录用户名")
    deviceId: str = Field(min_length=1, description="前端设备 ID")

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        """
        去除用户名首尾空格并校验非空。

        :param value: 原始用户名。
        :return: 规范化后的用户名。
        """
        stripped = value.strip()
        if not stripped:
            raise ValueError("username 不能为空")
        return stripped


class LoginResponse(BaseModel):
    """登录成功后的启动基础数据。"""

    model_config = ConfigDict(extra="forbid")

    user: UserAccountResponse
    systemSetting: UserSystemSettingResponse
    wallet: UserWalletResponse
    inventory: List[UserPropBagResponse] = Field(default_factory=list)
