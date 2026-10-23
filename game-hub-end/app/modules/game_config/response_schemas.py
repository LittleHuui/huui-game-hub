"""game_config 领域对外响应模型。"""

from typing import Optional

from pydantic import BaseModel

from app.common.base_entity import BaseEntityResponse


class GameSummaryResponse(BaseModel):
    gameCode: str
    gameName: str
    gameSubName: Optional[str] = None
    supportOnline: bool
    enabled: bool
    sortNo: int
