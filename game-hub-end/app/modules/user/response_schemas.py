"""user 领域对外响应模型。"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.common.base_entity import BaseEntityResponse


class UserSummaryResponse(BaseEntityResponse):
    username: str
    nickname: str
    avatar: Optional[str] = None
    status: str


class UserSystemSettingJson(BaseModel):
    dataMode: str = "auto"
    theme: str = "dark"
    autoSync: bool = True
    language: str = "zh-CN"
    enableSound: bool = True
    enableAnimation: bool = True
    extra: Dict[str, Any] = Field(default_factory=dict)


class UserSystemSettingResponse(BaseEntityResponse):
    userId: str
    setting: UserSystemSettingJson


class UserGameSettingResponse(BaseEntityResponse):
    userId: str
    gameCode: str
    setting: Dict[str, Any]
