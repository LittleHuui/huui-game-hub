"""云存档批次与快照响应合同。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.common.base_entity import BaseEntityResponse

from app.modules.user.response_schemas import UserSummaryResponse
from app.modules.user.response_schemas import UserSystemSettingJson
from app.modules.user.response_schemas import UserSystemSettingResponse
from app.modules.user.response_schemas import UserGameSettingResponse
from app.modules.wallet.response_schemas import UserWalletResponse
from app.modules.wallet.response_schemas import WalletLedgerResponse
from app.modules.inventory.response_schemas import UserPropBagResponse
from app.modules.inventory.response_schemas import PropUsageRecordResponse
from app.modules.purchase.response_schemas import PropPurchaseRecordResponse
from app.modules.match.response_schemas import MatchRecordResponse
from app.modules.score.response_schemas import ScoreRecordResponse

class PendingSyncEventRequest(BaseModel):
    clientId: str
    eventType: str
    createdAt: int
    updatedAt: int
    payload: Dict[str, Any]


class CloudSaveSyncRequest(BaseModel):
    userId: str
    deviceId: str
    clientSnapshotVersion: Optional[int] = None
    clientTime: int
    pendingEvents: List[PendingSyncEventRequest] = Field(default_factory=list)


class SyncResultResponse(BaseModel):
    receivedCount: int
    successCount: int
    duplicateCount: int
    failCount: int


class CloudSaveSyncResponse(BaseModel):
    serverTime: int
    cloudSnapshotVersion: int
    syncResult: SyncResultResponse
    user: UserSummaryResponse
    systemSetting: UserSystemSettingResponse
    wallet: UserWalletResponse
    inventory: List[UserPropBagResponse] = Field(default_factory=list)
    userGameSettings: List[UserGameSettingResponse] = Field(default_factory=list)
    walletLedgers: List[WalletLedgerResponse] = Field(default_factory=list)
    purchaseRecords: List[PropPurchaseRecordResponse] = Field(default_factory=list)
    propUsageRecords: List[PropUsageRecordResponse] = Field(default_factory=list)
    matchRecords: List[MatchRecordResponse] = Field(default_factory=list)
    scoreRecords: List[ScoreRecordResponse] = Field(default_factory=list)
