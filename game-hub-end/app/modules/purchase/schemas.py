"""购买域 HTTP 请求与响应模型。"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.common.camel_schema import CAMEL_MODEL_CONFIG, camel_field
from app.modules.boot.schemas import (
    PropPurchaseRecordResponse,
    UserPropBagResponse,
    UserWalletResponse,
)


class CreatePropPurchaseRequest(BaseModel):
    """购买道具请求（客户端幂等键 + 服务端定价）。"""

    model_config = CAMEL_MODEL_CONFIG

    clientId: str = camel_field("clientId", min_length=1)
    userId: str = camel_field("userId", min_length=1)
    deviceId: Optional[str] = camel_field("deviceId", default=None)
    gameCode: str = camel_field("gameCode", min_length=1)
    propCode: str = camel_field("propCode", min_length=1)
    quantity: int = Field(ge=1)
    createdAt: int = camel_field("createdAt")
    updatedAt: int = camel_field("updatedAt")


class PropPurchaseResultResponse(BaseModel):
    """购买道具成功响应载荷。"""

    model_config = ConfigDict(extra="forbid")

    purchaseRecord: PropPurchaseRecordResponse
    wallet: UserWalletResponse
    inventoryItem: UserPropBagResponse
