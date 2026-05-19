"""钱包域 Pydantic 模型。"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class UserWalletRead(BaseModel):
    """用户钱包响应。"""

    model_config = ConfigDict(from_attributes=True)

    server_id: str
    user_id: str
    balance: int
    total_earned: int
    created_at: int
    updated_at: int
    deleted_at: Optional[int] = None


class WalletLedgerRead(BaseModel):
    """钱包流水响应。"""

    model_config = ConfigDict(from_attributes=True)

    server_id: str
    client_id: str
    user_id: str
    device_id: Optional[str] = None
    game_code: Optional[str] = None
    change_type: str
    reason: str
    amount: int
    balance_after: Optional[int] = None
    payload_json: Optional[str] = None
    synced_at: Optional[int] = None
    created_at: int
    updated_at: int
    deleted_at: Optional[int] = None


class WalletLedgerListData(BaseModel):
    """流水列表响应体。"""

    model_config = ConfigDict(extra="forbid")

    items: List[WalletLedgerRead]


class WalletRebuildResult(BaseModel):
    """根据流水重算钱包快照后的结果。"""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    balance: int
    total_earned: int
