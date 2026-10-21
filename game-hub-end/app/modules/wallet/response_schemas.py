"""wallet 领域对外响应模型。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.common.base_entity import BaseEntityResponse


class UserWalletResponse(BaseEntityResponse):
    userId: str
    balance: int
    totalEarned: int


class WalletLedgerResponse(BaseEntityResponse):
    userId: str
    deviceId: Optional[str] = None
    gameCode: Optional[str] = None
    changeType: str
    reason: str
    amount: int
    balanceAfter: Optional[int] = None
    payload: Optional[Dict[str, Any]] = None
    syncedAt: Optional[int] = None
