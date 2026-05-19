"""用户域 setting_json 对应的 Pydantic 结构。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UserSystemSettingJson(BaseModel):
    """平台级用户系统偏好设置 JSON 结构。"""

    model_config = ConfigDict(extra="forbid")

    dataMode: Literal["auto", "local", "remote"] = Field(default="auto", description="数据同步模式")
    theme: Literal["dark", "light", "auto"] = Field(default="dark", description="界面主题")
    autoSync: bool = Field(default=True, description="是否自动同步")
    language: str = Field(default="zh-CN", min_length=1, description="界面语言")
    enableSound: bool = Field(default=True, description="是否启用音效")
    enableAnimation: bool = Field(default=True, description="是否启用动画")


def default_user_system_setting_json() -> UserSystemSettingJson:
    """
    返回新建用户系统设置时的默认 JSON 对象。

    :return: 默认 ``UserSystemSettingJson`` 实例。
    """
    return UserSystemSettingJson()
