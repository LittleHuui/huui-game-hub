"""inventory 领域对外响应模型。"""

from typing import Any, Dict, Optional


from app.common.base_entity import BaseEntityResponse


class UserPropBagResponse(BaseEntityResponse):
    userId: str
    gameCode: str
    propCode: str
    quantity: int


class PropUsageRecordResponse(BaseEntityResponse):
    userId: str
    deviceId: Optional[str] = None
    gameCode: str
    matchId: Optional[str] = None
    propCode: str
    quantity: int
    useReason: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    syncedAt: Optional[int] = None
