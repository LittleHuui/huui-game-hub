"""道具域 Pydantic 模型。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.common.base_entity import BaseEntityResponse
from app.common.camel_schema import CAMEL_MODEL_CONFIG


class PropDefinitionResponse(BaseEntityResponse):
    """道具定义 HTTP 响应。"""

    model_config = ConfigDict(extra="forbid")

    propCode: str
    propName: str
    description: Optional[str] = None
    icon: Optional[str] = None
    basePrice: int
    enabled: bool


class PropDefinitionRead(BaseModel):
    """道具定义响应。"""

    model_config = ConfigDict(from_attributes=True)

    server_id: str
    prop_code: str
    prop_name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    base_price: int
    enabled: int
    created_at: int
    updated_at: int
    deleted_at: Optional[int] = None


class GamePropRuleRead(BaseModel):
    """游戏道具规则响应。"""

    model_config = ConfigDict(from_attributes=True)

    server_id: str
    game_code: str
    prop_code: str
    price: int
    max_use_per_match: Optional[int] = None
    trigger_type: Optional[str] = None
    effect_type: Optional[str] = None
    rule_json: Optional[str] = None
    sort_no: int
    enabled: int
    created_at: int
    updated_at: int
    deleted_at: Optional[int] = None


class GamePropItemRead(BaseModel):
    """某游戏下可购/可用道具（定义 + 规则合并视图）。"""

    model_config = ConfigDict(extra="forbid")

    prop_code: str
    prop_name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    base_price: int
    price: int
    max_use_per_match: Optional[int] = None
    trigger_type: Optional[str] = None
    effect_type: Optional[str] = None
    rule_json: Optional[str] = None


class GamePropListData(BaseModel):
    """游戏道具列表响应体。"""

    model_config = ConfigDict(extra="forbid")

    game_code: str
    items: List[GamePropItemRead]


class UserPropBagRead(BaseModel):
    """用户背包行响应。"""

    model_config = ConfigDict(from_attributes=True)

    server_id: str
    user_id: str
    game_code: str
    prop_code: str
    quantity: int
    created_at: int
    updated_at: int
    deleted_at: Optional[int] = None


class UserPropBagListData(BaseModel):
    """用户背包列表响应体。"""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    items: List[UserPropBagRead]


class PropPurchaseRecordRead(BaseModel):
    """道具购买记录响应。"""

    model_config = ConfigDict(from_attributes=True)

    server_id: str
    client_id: str
    user_id: str
    device_id: Optional[str] = None
    game_code: str
    prop_code: str
    quantity: int
    unit_price: int
    total_price: int
    synced_at: Optional[int] = None
    created_at: int
    updated_at: int
    deleted_at: Optional[int] = None


class PropUsageRecordRead(BaseModel):
    """道具使用记录响应。"""

    model_config = ConfigDict(from_attributes=True)

    server_id: str
    client_id: str
    user_id: str
    device_id: Optional[str] = None
    game_code: str
    match_id: Optional[str] = None
    prop_code: str
    quantity: int
    use_reason: Optional[str] = None
    payload_json: Optional[str] = None
    synced_at: Optional[int] = None
    created_at: int
    updated_at: int
    deleted_at: Optional[int] = None


class PropPurchaseRequest(BaseModel):
    """购买道具请求体。"""

    model_config = CAMEL_MODEL_CONFIG

    clientId: str = Field(min_length=1, description="购买记录幂等 ID")
    walletClientId: str = Field(min_length=1, description="钱包流水幂等 ID")
    userId: str = Field(min_length=1)
    deviceId: Optional[str] = Field(default=None)
    gameCode: str = Field(min_length=1)
    propCode: str = Field(min_length=1)
    quantity: int = Field(ge=1)


class PropConsumeRequest(BaseModel):
    """消耗道具请求体（模块内 / 同步骨架）。"""

    model_config = CAMEL_MODEL_CONFIG

    userId: str = Field(min_length=1)
    gameCode: str = Field(min_length=1)
    propCode: str = Field(min_length=1)
    quantity: int = Field(ge=1, default=1)


class PropUsageRecordCreate(BaseModel):
    """记录道具使用请求体。"""

    model_config = CAMEL_MODEL_CONFIG

    clientId: str = Field(min_length=1)
    userId: str = Field(min_length=1)
    deviceId: Optional[str] = Field(default=None)
    gameCode: str = Field(min_length=1)
    matchId: Optional[str] = Field(default=None)
    propCode: str = Field(min_length=1)
    quantity: int = Field(ge=1, default=1)
    useReason: Optional[str] = Field(default=None)
    payload: Optional[Dict[str, Any]] = None
    consumeFromBag: bool = Field(default=True, description="是否同时扣减背包数量")
