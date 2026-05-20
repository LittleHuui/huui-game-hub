from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.common.base_entity import BaseEntityResponse


class HealthCheckResponse(BaseModel):
    status: str
    serverTime: int


class BootContextRequest(BaseModel):
    userId: Optional[str] = None
    deviceId: str
    clientTime: int


class UserSummaryResponse(BaseEntityResponse):
    username: str
    nickname: str
    avatar: Optional[str] = None
    status: str


class UserSystemSettingJson(BaseModel):
    dataMode: str = "auto"
    theme: str = "dark"
    autoSync: bool = True
    language: str = "zh-CN"
    enableSound: bool = True
    enableAnimation: bool = True
    extra: Dict[str, Any] = Field(default_factory=dict)


class UserSystemSettingResponse(BaseEntityResponse):
    userId: str
    setting: UserSystemSettingJson


class GameSummaryResponse(BaseModel):
    gameCode: str
    gameName: str
    gameSubName: Optional[str] = None
    supportOnline: bool
    enabled: bool
    sortNo: int


class BootContextResponse(BaseModel):
    serverTime: int
    userExists: bool
    user: Optional[UserSummaryResponse] = None
    systemSetting: Optional[UserSystemSettingResponse] = None
    games: List[GameSummaryResponse] = Field(default_factory=list)


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


class UserWalletResponse(BaseEntityResponse):
    userId: str
    balance: int
    totalEarned: int


class UserPropBagResponse(BaseEntityResponse):
    userId: str
    gameCode: str
    propCode: str
    quantity: int


class UserGameSettingResponse(BaseEntityResponse):
    userId: str
    gameCode: str
    setting: Dict[str, Any]


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


class PropPurchaseRecordResponse(BaseEntityResponse):
    userId: str
    deviceId: Optional[str] = None
    gameCode: str
    propCode: str
    quantity: int
    unitPrice: int
    totalPrice: int
    syncedAt: Optional[int] = None


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
