"""启动与依赖探测响应合同。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.common.base_entity import BaseEntityResponse

from app.modules.user.response_schemas import UserSummaryResponse, UserSystemSettingResponse
from app.modules.game_config.response_schemas import GameSummaryResponse

class HealthCheckResponse(BaseModel):
    status: str
    serverTime: int
    components: Dict[str, Any] = Field(default_factory=dict)


class BootContextRequest(BaseModel):
    userId: Optional[str] = None
    deviceId: str
    clientTime: int


class BootContextResponse(BaseModel):
    serverTime: int
    userExists: bool
    user: Optional[UserSummaryResponse] = None
    systemSetting: Optional[UserSystemSettingResponse] = None
    games: List[GameSummaryResponse] = Field(default_factory=list)
