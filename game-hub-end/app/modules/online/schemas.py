"""在线/临时态模块 Pydantic 模型。"""

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


OnlineStatus = Literal["online", "away", "busy", "offline"]


class OnlineStatusRequest(BaseModel):
    """修改当前用户在线状态请求。"""

    model_config = ConfigDict(extra="forbid")

    status: OnlineStatus = Field(description="在线状态")


class OnlineUserResponse(BaseModel):
    """在线用户响应项。"""

    model_config = ConfigDict(extra="forbid")

    serviceId: str
    nickname: str
    avatar: Optional[str] = None
    status: OnlineStatus
    onlineAt: int
    lastActiveAt: int


class OnlineUsersResponse(BaseModel):
    """在线用户列表响应。"""

    model_config = ConfigDict(extra="forbid")

    users: List[OnlineUserResponse]
