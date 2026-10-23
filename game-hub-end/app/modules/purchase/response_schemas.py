"""purchase 领域对外响应模型。"""

from typing import Optional


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
