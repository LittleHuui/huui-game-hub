"""match 领域对外响应模型。"""

from typing import Any, Dict, List, Optional


from app.common.base_entity import BaseEntityResponse


class MatchRecordResponse(BaseEntityResponse):
    userId: str
    deviceId: Optional[str] = None
    gameCode: str
    mode: str
    result: str
    difficultyCode: Optional[str] = None
    durationMs: Optional[int] = None
    score: int
    propUses: Optional[List[Any]] = None
    payload: Optional[Dict[str, Any]] = None
    syncedAt: Optional[int] = None
