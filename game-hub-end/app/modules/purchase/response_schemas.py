"""purchase 领域对外响应模型。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.common.base_entity import BaseEntityResponse


class PropPurchaseRecordResponse(BaseEntityResponse):
    userId: str
    deviceId: Optional[str] = None
    gameCode: str
    propCode: str
    quantity: int
    unitPrice: int
    totalPrice: int
    syncedAt: Optional[int] = None
