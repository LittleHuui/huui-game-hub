"""score 领域对外响应模型。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.common.base_entity import BaseEntityResponse


class ScoreRecordResponse(BaseEntityResponse):
    userId: str
    deviceId: Optional[str] = None
    gameCode: str
    mode: str
    difficultyCode: Optional[str] = None
    result: str
    score: int
    durationMs: Optional[int] = None
    payload: Optional[Dict[str, Any]] = None
    syncedAt: Optional[int] = None
