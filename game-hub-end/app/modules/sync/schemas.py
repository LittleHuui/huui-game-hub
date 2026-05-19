"""同步域 Pydantic 模型（云存档协议）。"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.common.camel_schema import CAMEL_MODEL_CONFIG, camel_field
from app.modules.match.schemas import MatchRecordRead, ScoreRecordRead
from app.modules.prop.schemas import PropPurchaseRecordRead, PropUsageRecordRead, UserPropBagRead
from app.modules.user.schemas import UserAccountRead, UserGameSettingRead, UserSystemSettingRead
from app.modules.wallet.schemas import UserWalletRead, WalletLedgerRead

SyncEventType = Literal[
    "user_update",
    "user_system_setting_update",
    "user_game_setting_update",
    "wallet_ledger",
    "prop_purchase",
    "prop_usage",
    "match_record",
    "match_action",
    "score_record",
]


class PendingEvent(BaseModel):
    """待同步的客户端事件。"""

    model_config = CAMEL_MODEL_CONFIG

    clientId: str = camel_field("clientId", min_length=1)
    eventType: SyncEventType = camel_field("eventType")
    createdAt: int = camel_field("createdAt")
    updatedAt: int = camel_field("updatedAt")
    payload: Dict[str, Any] = Field(default_factory=dict)


class CloudSaveRequest(BaseModel):
    """云存档同步请求体。"""

    model_config = CAMEL_MODEL_CONFIG

    userId: str = camel_field("userId", min_length=1)
    deviceId: str = camel_field("deviceId", min_length=1)
    clientSnapshotVersion: int = camel_field("clientSnapshotVersion", default=0, ge=0)
    pendingEvents: List[PendingEvent] = Field(default_factory=list)
    localSnapshot: Dict[str, Any] = Field(default_factory=dict)


class CloudInventoryItem(BaseModel):
    """云存档背包行。"""

    model_config = ConfigDict(extra="forbid")

    gameCode: str
    propCode: str
    quantity: int


class CloudWalletSnapshot(BaseModel):
    """云存档钱包摘要。"""

    model_config = ConfigDict(extra="forbid")

    userId: str
    balance: int
    totalEarned: int


class CloudUserSnapshot(BaseModel):
    """云存档用户摘要。"""

    model_config = ConfigDict(extra="forbid")

    userId: str
    clientId: str
    username: str
    nickname: str
    avatar: Optional[str] = None
    status: str


class CloudSaveResponse(BaseModel):
    """云存档同步响应体。"""

    model_config = ConfigDict(extra="forbid")

    serverTime: int
    cloudSnapshotVersion: int
    user: CloudUserSnapshot
    wallet: CloudWalletSnapshot
    inventory: List[CloudInventoryItem]
    settings: List[Dict[str, Any]]
    histories: List[MatchRecordRead]
    walletLedgers: List[WalletLedgerRead]
    propUsageRecords: List[PropUsageRecordRead]
    purchaseRecords: List[PropPurchaseRecordRead]
    matchRecords: List[MatchRecordRead]
    scoreRecords: List[Dict[str, Any]]


def wallet_to_cloud(wallet: UserWalletRead) -> CloudWalletSnapshot:
    """
    将钱包读模型转为云存档钱包摘要。

    :param wallet: 钱包读模型。
    :return: 云存档钱包摘要。
    """
    return CloudWalletSnapshot(
        userId=wallet.user_id,
        balance=wallet.balance,
        totalEarned=wallet.total_earned,
    )


def user_to_cloud(user: UserAccountRead) -> CloudUserSnapshot:
    """
    将用户读模型转为云存档用户摘要。

    :param user: 用户读模型。
    :return: 云存档用户摘要。
    """
    return CloudUserSnapshot(
        userId=user.server_id,
        clientId=user.client_id,
        username=user.username,
        nickname=user.nickname,
        avatar=user.avatar,
        status=user.status,
    )


def bag_row_to_cloud(row: UserPropBagRead) -> CloudInventoryItem:
    """
    将背包行转为云存档库存项。

    :param row: 背包读模型。
    :return: 云存档库存项。
    """
    return CloudInventoryItem(
        gameCode=row.game_code,
        propCode=row.prop_code,
        quantity=row.quantity,
    )


def game_setting_to_cloud_dict(setting: UserGameSettingRead) -> Dict[str, Any]:
    """
    将游戏设置读模型转为云存档 settings 列表元素。

    :param setting: 游戏设置读模型。
    :return: 字典（camelCase 键）。
    """
    return {
        "kind": "game",
        "serverId": setting.server_id,
        "clientId": setting.client_id,
        "userId": setting.user_id,
        "gameCode": setting.game_code,
        "setting": setting.setting,
        "createdAt": setting.created_at,
        "updatedAt": setting.updated_at,
    }


def system_setting_to_cloud_dict(setting: UserSystemSettingRead) -> Dict[str, Any]:
    """
    将系统设置读模型转为云存档 settings 列表元素。

    :param setting: 系统设置读模型。
    :return: 字典（camelCase 键）。
    """
    return {
        "kind": "system",
        "serverId": setting.server_id,
        "clientId": setting.client_id,
        "userId": setting.user_id,
        "setting": setting.setting.model_dump(),
        "createdAt": setting.created_at,
        "updatedAt": setting.updated_at,
    }


def score_record_read_to_cloud(record: ScoreRecordRead) -> Dict[str, Any]:
    """
    将成绩读模型转为云存档 scoreRecords 元素（camelCase）。

    :param record: 成绩读模型。
    :return: 字典。
    """
    return {
        "serverId": record.server_id,
        "clientId": record.client_id,
        "userId": record.user_id,
        "deviceId": record.device_id,
        "gameCode": record.game_code,
        "mode": record.mode,
        "difficultyCode": record.difficulty_code,
        "result": record.result,
        "score": record.score,
        "durationMs": record.duration_ms,
        "payloadJson": record.payload_json,
        "syncedAt": record.synced_at,
        "createdAt": record.created_at,
        "updatedAt": record.updated_at,
    }
