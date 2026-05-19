import json
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException, NotFoundException, ValidationException
from app.core.logging import get_logger
from app.core.time_utils import now_ms
from app.modules.boot.schemas import (
    BootContextRequest,
    BootContextResponse,
    CloudSaveSyncRequest,
    CloudSaveSyncResponse,
    GameSummaryResponse,
    HealthCheckResponse,
    MatchRecordResponse,
    PendingSyncEventRequest,
    PropPurchaseRecordResponse,
    PropUsageRecordResponse,
    ScoreRecordResponse,
    SyncResultResponse,
    UserGameSettingResponse,
    UserPropBagResponse,
    UserSummaryResponse,
    UserSystemSettingJson,
    UserSystemSettingResponse,
    UserWalletResponse,
    WalletLedgerResponse,
)
from app.modules.game.models import GameDefinition
from app.modules.game.module_service import GameModuleService
from app.modules.inventory.module_service import InventoryModuleService
from app.modules.inventory.models import PropUsageRecord
from app.modules.match.models import MatchRecord
from app.modules.match.module_service import MatchModuleService
from app.modules.purchase.models import PropPurchaseRecord
from app.modules.score.models import ScoreRecord
from app.modules.purchase.module_service import PurchaseModuleService
from app.modules.score.module_service import ScoreModuleService
from app.modules.sync.entity_service import SyncLogEntityService
from app.modules.sync.module_service import SyncModuleService
from app.modules.sync.schemas import PendingEvent
from app.modules.user.schemas import UserGameSettingRead
from app.modules.user.models import UserAccount, UserSystemSetting
from app.modules.user.module_service import UserModuleService
from app.modules.inventory.mappers import to_user_prop_bag_response
from app.modules.wallet.mappers import to_user_wallet_response
from app.modules.wallet.models import UserWallet, WalletLedger
from app.modules.wallet.module_service import WalletModuleService

logger = get_logger(__name__)

SyncEventResult = Literal["success", "duplicate"]

_SUPPORTED_SYNC_EVENT_TYPES = frozenset(
    {
        "user_update",
        "user_system_setting_update",
        "user_game_setting_update",
        "wallet_ledger",
        "prop_purchase",
        "prop_usage",
        "match_record",
        "score_record",
    }
)

# 状态类同步事件：需按 updatedAt LWW 合并；与事件类（幂等追加）区分处理顺序。
_STATE_SYNC_EVENT_TYPES = frozenset(
    {
        "user_update",
        "user_system_setting_update",
        "user_game_setting_update",
    }
)


def _order_cloud_save_events(
    events: List[PendingSyncEventRequest],
) -> List[PendingSyncEventRequest]:
    """
    构造云存档同步处理顺序。

    状态类事件先按 ``updatedAt`` 升序、同戳按 ``clientId`` 升序排序后处理（LWW）；
    事件类（wallet_ledger / match_record 等）保持 ``pendingEvents`` 中的相对顺序，不重排。

    :param events: 客户端上报的待同步事件列表。
    :return: 实际分发顺序列表。
    """
    state_events = [event for event in events if event.eventType in _STATE_SYNC_EVENT_TYPES]
    action_events = [event for event in events if event.eventType not in _STATE_SYNC_EVENT_TYPES]
    state_events.sort(key=lambda item: (item.updatedAt, item.clientId))
    return state_events + action_events

def _boot_event_to_pending(event: PendingSyncEventRequest) -> PendingEvent:
    """
    将启动模块同步事件转为 sync 域 ``PendingEvent``。

    :param event: 启动模块待同步事件。
    :return: sync 域事件模型。
    """
    return PendingEvent(
        clientId=event.clientId,
        eventType=event.eventType,
        createdAt=event.createdAt,
        updatedAt=event.updatedAt,
        payload=event.payload,
    )


def _parse_user_system_setting_json(raw: Optional[str]) -> UserSystemSettingJson:
    """
    将数据库 setting_json 解析为启动模块响应结构。

    :param raw: 原始 JSON 文本。
    :return: 解析成功则返回对象，否则返回默认值。
    """
    if raw is None or not str(raw).strip():
        return UserSystemSettingJson()
    try:
        return UserSystemSettingJson.model_validate_json(raw)
    except Exception:
        return UserSystemSettingJson()


def _to_user_summary(user: UserAccount) -> UserSummaryResponse:
    """
    将用户 ORM 转为启动模块用户摘要。

    :param user: 用户账号实体。
    :return: ``UserSummaryResponse``。
    """
    return UserSummaryResponse(
        serverId=user.server_id,
        clientId=user.client_id,
        username=user.username,
        nickname=user.nickname,
        avatar=user.avatar,
        status=user.status,
        createdAt=user.created_at,
        updatedAt=user.updated_at,
        deletedAt=user.deleted_at,
    )


def _to_user_system_setting_response(setting: UserSystemSetting) -> UserSystemSettingResponse:
    """
    将用户系统设置 ORM 转为启动模块响应。

    :param setting: 用户系统设置实体。
    :return: ``UserSystemSettingResponse``。
    """
    return UserSystemSettingResponse(
        serverId=setting.server_id,
        clientId=setting.client_id,
        userId=setting.user_id,
        setting=_parse_user_system_setting_json(setting.setting_json),
        createdAt=setting.created_at,
        updatedAt=setting.updated_at,
        deletedAt=setting.deleted_at,
    )


def _parse_optional_json_dict(raw: Optional[str], *, strict: bool = True) -> Optional[Dict[str, Any]]:
    """
    将存库 JSON 文本解析为字典。

    :param raw: JSON 文本，可空。
    :param strict: 为 ``False`` 时解析失败返回 ``None`` 而不抛错。
    :return: 字典或 ``None``。
    :raises ValidationException: 严格模式下解析失败或类型非对象。
    """
    if raw is None or not str(raw).strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        if not strict:
            return None
        raise ValidationException(f"JSON 解析失败: {exc}") from exc
    if parsed is None:
        return None
    if not isinstance(parsed, dict):
        if not strict:
            return None
        raise ValidationException("JSON 必须为对象")
    return parsed


def _to_wallet_ledger_response(ledger: WalletLedger) -> WalletLedgerResponse:
    """
    将钱包流水 ORM 转为启动模块响应。

    :param ledger: 流水实体。
    :return: ``WalletLedgerResponse``。
    """
    return WalletLedgerResponse(
        serverId=ledger.server_id,
        clientId=ledger.client_id,
        userId=ledger.user_id,
        deviceId=ledger.device_id,
        gameCode=ledger.game_code,
        changeType=ledger.change_type,
        reason=ledger.reason,
        amount=ledger.amount,
        balanceAfter=ledger.balance_after,
        payload=_parse_optional_json_dict(ledger.payload_json, strict=False),
        syncedAt=ledger.synced_at,
        createdAt=ledger.created_at,
        updatedAt=ledger.updated_at,
        deletedAt=ledger.deleted_at,
    )


def _to_prop_purchase_response(record: PropPurchaseRecord) -> PropPurchaseRecordResponse:
    """
    将道具购买记录 ORM 转为启动模块响应。

    :param record: 购买记录实体。
    :return: ``PropPurchaseRecordResponse``。
    """
    return PropPurchaseRecordResponse(
        serverId=record.server_id,
        clientId=record.client_id,
        userId=record.user_id,
        deviceId=record.device_id,
        gameCode=record.game_code,
        propCode=record.prop_code,
        quantity=record.quantity,
        unitPrice=record.unit_price,
        totalPrice=record.total_price,
        syncedAt=record.synced_at,
        createdAt=record.created_at,
        updatedAt=record.updated_at,
        deletedAt=record.deleted_at,
    )


def _to_prop_usage_response(record: PropUsageRecord) -> PropUsageRecordResponse:
    """
    将道具使用记录 ORM 转为启动模块响应。

    :param record: 使用记录实体。
    :return: ``PropUsageRecordResponse``。
    """
    return PropUsageRecordResponse(
        serverId=record.server_id,
        clientId=record.client_id,
        userId=record.user_id,
        deviceId=record.device_id,
        gameCode=record.game_code,
        matchId=record.match_id,
        propCode=record.prop_code,
        quantity=record.quantity,
        useReason=record.use_reason,
        payload=_parse_optional_json_dict(record.payload_json, strict=False),
        syncedAt=record.synced_at,
        createdAt=record.created_at,
        updatedAt=record.updated_at,
        deletedAt=record.deleted_at,
    )


def _to_match_record_response(record: MatchRecord) -> MatchRecordResponse:
    """
    将对局记录 ORM 转为启动模块响应。

    :param record: 对局记录实体。
    :return: ``MatchRecordResponse``。
    """
    return MatchRecordResponse(
        serverId=record.server_id,
        clientId=record.client_id,
        userId=record.user_id,
        deviceId=record.device_id,
        gameCode=record.game_code,
        mode=record.mode,
        result=record.result,
        difficultyCode=record.difficulty_code,
        durationMs=record.duration_ms,
        score=record.score,
        propUses=_parse_optional_json_dict(record.prop_uses_json, strict=False),
        payload=_parse_optional_json_dict(record.payload_json, strict=False),
        syncedAt=record.synced_at,
        createdAt=record.created_at,
        updatedAt=record.updated_at,
        deletedAt=record.deleted_at,
    )


def _to_score_record_response(record: ScoreRecord) -> ScoreRecordResponse:
    """
    将成绩记录 ORM 转为启动模块响应。

    :param record: 成绩记录实体。
    :return: ``ScoreRecordResponse``。
    """
    return ScoreRecordResponse(
        serverId=record.server_id,
        clientId=record.client_id,
        userId=record.user_id,
        deviceId=record.device_id,
        gameCode=record.game_code,
        mode=record.mode,
        difficultyCode=record.difficulty_code,
        result=record.result,
        score=record.score,
        durationMs=record.duration_ms,
        payload=_parse_optional_json_dict(record.payload_json, strict=False),
        syncedAt=record.synced_at,
        createdAt=record.created_at,
        updatedAt=record.updated_at,
        deletedAt=record.deleted_at,
    )


def _to_user_game_setting_response(setting: UserGameSettingRead) -> UserGameSettingResponse:
    """
    将用户游戏设置读模型转为启动模块响应。

    :param setting: 游戏设置读模型。
    :return: ``UserGameSettingResponse``。
    """
    return UserGameSettingResponse(
        serverId=setting.server_id,
        clientId=setting.client_id,
        userId=setting.user_id,
        gameCode=setting.game_code,
        setting=setting.setting if setting.setting is not None else {},
        createdAt=setting.created_at,
        updatedAt=setting.updated_at,
        deletedAt=setting.deleted_at,
    )


def _to_game_summary(game: GameDefinition) -> GameSummaryResponse:
    """
    将游戏定义 ORM 转为启动模块游戏摘要。

    :param game: 游戏定义实体。
    :return: ``GameSummaryResponse``。
    """
    return GameSummaryResponse(
        gameCode=game.game_code,
        gameName=game.game_name,
        gameSubName=game.game_sub_name,
        supportOnline=bool(game.support_online),
        enabled=bool(game.enabled),
        sortNo=game.sort_no,
    )


class BootModuleService:
    """启动模块业务服务。"""

    def __init__(
        self,
        user_module_service: Optional[UserModuleService] = None,
        game_module_service: Optional[GameModuleService] = None,
        sync_log_entity_service: Optional[SyncLogEntityService] = None,
        sync_module_service: Optional[SyncModuleService] = None,
        wallet_module_service: Optional[WalletModuleService] = None,
        purchase_module_service: Optional[PurchaseModuleService] = None,
        inventory_module_service: Optional[InventoryModuleService] = None,
        match_module_service: Optional[MatchModuleService] = None,
        score_module_service: Optional[ScoreModuleService] = None,
    ) -> None:
        self._user_module_service = user_module_service
        self._game_module_service = game_module_service
        self._sync_log_entity_service = sync_log_entity_service
        self._sync_module_service = sync_module_service
        self._wallet_module_service = wallet_module_service
        self._purchase_module_service = purchase_module_service
        self._inventory_module_service = inventory_module_service
        self._match_module_service = match_module_service
        self._score_module_service = score_module_service

    def _list_enabled_games(self) -> List[GameSummaryResponse]:
        """
        查询已启用游戏列表并转为响应对象。

        :return: 游戏摘要列表。
        """
        if self._game_module_service is None:
            return []
        games = self._game_module_service.list_enabled_games()
        return [_to_game_summary(game) for game in games]

    def _resolve_cloud_snapshot_version(self, request: CloudSaveSyncRequest) -> int:
        """
        计算云存档版本号。

        :param request: 云存档同步请求。
        :return: 云存档版本。
        """
        base = request.clientSnapshotVersion if request.clientSnapshotVersion and request.clientSnapshotVersion > 0 else 0
        if request.pendingEvents:
            return base + 1
        return base if base > 0 else 1

    def _rebuild_user_wallet(self, user_id: str) -> UserWallet:
        """
        按全部 ``wallet_ledger`` 重算 ``user_wallet`` 快照（不信任客户端 balance）。

        :param user_id: 用户主键。
        :return: 重算后的钱包实体。
        """
        wallet_module = self._require_wallet_module()
        wallet_module.rebuild_wallet_from_ledgers(user_id)
        return wallet_module.get_or_create_wallet(user_id)

    def _rebuild_user_inventory(self, user_id: str) -> List[UserPropBagResponse]:
        """
        按购买/使用记录重算背包数量（不信任客户端 quantity）。

        :param user_id: 用户主键。
        :return: 重算后的背包响应列表（quantity 为 0 的行不返回）。
        """
        inventory_module = self._require_inventory_module()
        rows = inventory_module.rebuild_inventory_from_records(user_id)
        return [to_user_prop_bag_response(row) for row in rows if row.quantity > 0]

    def _ensure_user_module(self) -> UserModuleService:
        """
        获取已注入的用户模块服务。

        :return: 用户模块服务。
        :raises NotFoundException: 未注入用户模块。
        """
        if self._user_module_service is None:
            raise NotFoundException("用户不存在")
        return self._user_module_service

    def _validate_cloud_save_request(self, request: CloudSaveSyncRequest) -> UserAccount:
        """
        校验云存档同步请求（用户存在、批次内 clientId 不重复）。

        :param request: 云存档同步请求。
        :return: 用户账号实体。
        :raises NotFoundException: 用户不存在。
        :raises ValidationException: 事件列表非法。
        """
        user_module = self._ensure_user_module()
        user = user_module.get_user_by_id(request.userId)
        if user is None:
            raise NotFoundException("用户不存在")
        seen_client_ids: Set[str] = set()
        for idx, event in enumerate(request.pendingEvents):
            if event.clientId in seen_client_ids:
                raise ValidationException(f"同一批次内 clientId 重复: index={idx}")
            seen_client_ids.add(event.clientId)
        return user

    def _format_sync_event_error(self, client_id: str, exc: Exception) -> str:
        """
        将单条事件异常格式化为可读错误信息。

        :param client_id: 事件 clientId。
        :param exc: 捕获的异常。
        :return: 错误描述文本。
        """
        if isinstance(exc, BizException):
            return f"{client_id}: {exc.message}"
        if isinstance(exc, json.JSONDecodeError):
            return f"{client_id}: JSON 解析失败"
        if isinstance(exc, PydanticValidationError):
            return f"{client_id}: 数据校验失败"
        if isinstance(exc, SQLAlchemyError):
            return f"{client_id}: 数据库异常"
        return f"{client_id}: {exc}"

    def _append_sync_log(
        self,
        *,
        request: CloudSaveSyncRequest,
        sync_result: str,
        received_count: int,
        success_count: int,
        duplicate_count: int,
        fail_count: int,
        start_time: int,
        finish_time: int,
        error_messages: List[str],
    ) -> None:
        """
        写入云存档同步审计日志（含开始/结束时间与统计）。

        :param request: 云存档请求。
        :param sync_result: 批次结果标签。
        :param received_count: 收到事件数。
        :param success_count: 新写入成功数。
        :param duplicate_count: 幂等重复数。
        :param fail_count: 失败数。
        :param start_time: 同步开始时间（毫秒）。
        :param finish_time: 同步结束时间（毫秒）。
        :param error_messages: 聚合错误列表。
        :return: None
        """
        if self._sync_log_entity_service is None:
            return
        self._sync_log_entity_service.append_cloud_save(
            user_id=request.userId,
            device_id=request.deviceId,
            sync_result=sync_result,
            pending_count=received_count,
            success_count=success_count,
            fail_count=fail_count,
            duplicate_count=duplicate_count,
            start_time=start_time,
            finish_time=finish_time,
            error_message="; ".join(error_messages) if error_messages else None,
            client_snapshot_version=request.clientSnapshotVersion,
            processed_client_ids=[event.clientId for event in request.pendingEvents],
        )

    def _build_cloud_save_response(
        self,
        *,
        request: CloudSaveSyncRequest,
        user: UserAccount,
        server_time: int,
        received_count: int,
        success_count: int,
        duplicate_count: int,
        fail_count: int,
    ) -> CloudSaveSyncResponse:
        """
        重算派生数据并构建完整云存档同步响应。

        :param request: 云存档请求。
        :param user: 用户账号实体。
        :param server_time: 服务器时间戳（毫秒）。
        :param received_count: 收到事件数。
        :param success_count: 新写入成功数。
        :param duplicate_count: 幂等重复数。
        :param fail_count: 失败数。
        :return: 完整 ``CloudSaveSyncResponse``。
        """
        user_module = self._ensure_user_module()
        setting_entity = user_module.get_or_create_user_system_setting(request.userId)
        cloud_snapshot_version = self._resolve_cloud_snapshot_version(request)
        wallet_entity = self._rebuild_user_wallet(request.userId)
        inventory_items = self._rebuild_user_inventory(request.userId)

        wallet_ledgers: List[WalletLedgerResponse] = []
        if self._wallet_module_service is not None:
            wallet_ledgers = [
                _to_wallet_ledger_response(row)
                for row in self._wallet_module_service.list_ledgers(request.userId)
            ]

        purchase_records: List[PropPurchaseRecordResponse] = []
        prop_usage_records: List[PropUsageRecordResponse] = []
        if self._purchase_module_service is not None:
            purchase_records = [
                _to_prop_purchase_response(row)
                for row in self._purchase_module_service.list_purchase_records(request.userId)
            ]
        if self._inventory_module_service is not None:
            prop_usage_records = [
                _to_prop_usage_response(row)
                for row in self._inventory_module_service.list_usage_records(request.userId)
            ]

        match_records: List[MatchRecordResponse] = []
        score_records: List[ScoreRecordResponse] = []
        if self._match_module_service is not None:
            match_records = [
                _to_match_record_response(row)
                for row in self._match_module_service.list_user_matches(request.userId, limit=100)
            ]
        if self._score_module_service is not None:
            score_records = [
                _to_score_record_response(row)
                for row in self._score_module_service.list_user_score_records(request.userId, limit=200)
            ]

        user_game_settings = [
            _to_user_game_setting_response(row)
            for row in user_module.list_user_game_settings(request.userId)
        ]

        return CloudSaveSyncResponse(
            serverTime=server_time,
            cloudSnapshotVersion=cloud_snapshot_version,
            syncResult=SyncResultResponse(
                receivedCount=received_count,
                successCount=success_count,
                duplicateCount=duplicate_count,
                failCount=fail_count,
            ),
            user=_to_user_summary(user),
            systemSetting=_to_user_system_setting_response(setting_entity),
            wallet=to_user_wallet_response(wallet_entity),
            inventory=inventory_items,
            userGameSettings=user_game_settings,
            walletLedgers=wallet_ledgers,
            purchaseRecords=purchase_records,
            propUsageRecords=prop_usage_records,
            matchRecords=match_records,
            scoreRecords=score_records,
        )

    async def _dispatch_sync_event(
        self,
        user_id: str,
        device_id: str,
        event: PendingSyncEventRequest,
    ) -> SyncEventResult:
        """
        按 eventType 分发同步事件。

        :param user_id: 用户主键。
        :param device_id: 设备 ID。
        :param event: 待处理事件。
        :return: ``success`` 或 ``duplicate``。
        """
        event_type = event.eventType
        if event_type not in _SUPPORTED_SYNC_EVENT_TYPES:
            raise ValidationException("不支持的 eventType: {0}".format(event_type))
        if event_type == "wallet_ledger" and self._wallet_ledger_exists(user_id, event.clientId):
            return "duplicate"
        if event_type == "prop_purchase" and self._prop_purchase_exists(user_id, event.clientId):
            return "duplicate"
        if event_type == "prop_usage" and self._prop_usage_exists(user_id, event.clientId):
            return "duplicate"
        if event_type == "match_record" and self._match_record_exists(user_id, event.clientId):
            return "duplicate"
        if event_type == "score_record" and self._score_record_exists(user_id, event.clientId):
            return "duplicate"
        sync_module = self._require_sync_module()
        sync_module.dispatch_pending_event(user_id, device_id, _boot_event_to_pending(event))
        return "success"

    def _require_wallet_module(self) -> WalletModuleService:
        """
        获取已注入的钱包模块服务。

        :return: 钱包模块服务。
        :raises NotFoundException: 未注入钱包模块。
        """
        if self._wallet_module_service is None:
            raise NotFoundException("钱包服务不可用")
        return self._wallet_module_service

    def _require_sync_module(self) -> SyncModuleService:
        """
        获取已注入的同步模块服务。

        :return: 同步模块服务。
        :raises NotFoundException: 未注入同步模块。
        """
        if self._sync_module_service is None:
            raise NotFoundException("同步服务不可用")
        return self._sync_module_service

    def _require_purchase_module(self) -> PurchaseModuleService:
        """
        获取已注入的购买模块服务。

        :return: 购买模块服务。
        :raises NotFoundException: 未注入购买模块。
        """
        if self._purchase_module_service is None:
            raise NotFoundException("购买服务不可用")
        return self._purchase_module_service

    def _require_inventory_module(self) -> InventoryModuleService:
        """
        获取已注入的背包模块服务。

        :return: 背包模块服务。
        :raises NotFoundException: 未注入背包模块。
        """
        if self._inventory_module_service is None:
            raise NotFoundException("背包服务不可用")
        return self._inventory_module_service

    def _require_score_module(self) -> ScoreModuleService:
        """
        获取已注入的成绩模块服务。

        :return: 成绩模块服务。
        :raises NotFoundException: 未注入成绩模块。
        """
        if self._score_module_service is None:
            raise NotFoundException("成绩服务不可用")
        return self._score_module_service

    def _require_match_module(self) -> MatchModuleService:
        """
        获取已注入的对局模块服务。

        :return: 对局模块服务。
        :raises NotFoundException: 未注入对局模块。
        """
        if self._match_module_service is None:
            raise NotFoundException("对局服务不可用")
        return self._match_module_service

    def _wallet_ledger_exists(self, user_id: str, client_id: str) -> bool:
        """
        判断钱包流水是否已按 userId + clientId 存在。

        :param user_id: 用户主键。
        :param client_id: 事件 clientId。
        :return: 已存在为 True。
        """
        wallet_module = self._require_wallet_module()
        return wallet_module.ledger_exists(user_id, client_id)

    def _prop_purchase_exists(self, user_id: str, client_id: str) -> bool:
        """
        判断道具购买记录是否已存在。

        :param user_id: 用户主键。
        :param client_id: 事件 clientId。
        :return: 已存在为 True。
        """
        purchase_module = self._require_purchase_module()
        return purchase_module.purchase_exists(user_id, client_id)

    def _prop_usage_exists(self, user_id: str, client_id: str) -> bool:
        """
        判断道具使用记录是否已存在。

        :param user_id: 用户主键。
        :param client_id: 事件 clientId。
        :return: 已存在为 True。
        """
        inventory_module = self._require_inventory_module()
        return inventory_module.usage_exists(user_id, client_id)

    def _match_record_exists(self, user_id: str, client_id: str) -> bool:
        """
        判断对局记录是否已存在。

        :param user_id: 用户主键。
        :param client_id: 事件 clientId。
        :return: 已存在为 True。
        """
        match_module = self._require_match_module()
        return match_module.match_record_exists(user_id, client_id)

    def _score_record_exists(self, user_id: str, client_id: str) -> bool:
        """
        判断成绩记录是否已存在。

        :param user_id: 用户主键。
        :param client_id: 事件 clientId。
        :return: 已存在为 True。
        """
        score_module = self._require_score_module()
        return score_module.score_record_exists(user_id, client_id)

    async def health_check(self) -> HealthCheckResponse:
        """健康检查。"""
        server_time = now_ms()

        return HealthCheckResponse(
            status="ok",
            serverTime=server_time,
        )

    async def get_boot_context(
        self,
        request: BootContextRequest,
    ) -> BootContextResponse:
        """获取启动上下文。"""
        server_time = now_ms()
        games = self._list_enabled_games()

        user_id = request.userId
        if user_id is None or not user_id.strip():
            return BootContextResponse(
                serverTime=server_time,
                userExists=False,
                user=None,
                systemSetting=None,
                games=games,
            )

        user_id = user_id.strip()
        if self._user_module_service is None:
            return BootContextResponse(
                serverTime=server_time,
                userExists=False,
                user=None,
                systemSetting=None,
                games=games,
            )

        user = self._user_module_service.get_user_by_id(user_id)
        if user is None:
            return BootContextResponse(
                serverTime=server_time,
                userExists=False,
                user=None,
                systemSetting=None,
                games=games,
            )

        self._user_module_service.bind_or_update_device_for_boot(user_id, request.deviceId)
        setting_entity = self._user_module_service.get_or_create_user_system_setting(user_id)

        return BootContextResponse(
            serverTime=server_time,
            userExists=True,
            user=_to_user_summary(user),
            systemSetting=_to_user_system_setting_response(setting_entity),
            games=games,
        )

    async def sync_cloud_save(
        self,
        request: CloudSaveSyncRequest,
    ) -> CloudSaveSyncResponse:
        """云存档同步：事件分发、派生数据重算、审计日志与完整快照返回。"""
        start_time = now_ms()
        user = self._validate_cloud_save_request(request)

        received_count = len(request.pendingEvents)
        success_count = 0
        duplicate_count = 0
        fail_count = 0
        error_messages: List[str] = []
        sync_result_label = "success"

        try:
            # 状态类（如 user_system_setting_update）须按事件时间 LWW 合并，先排序再与事件类按序分发。
            ordered_events = _order_cloud_save_events(request.pendingEvents)
            for event in ordered_events:
                try:
                    result = await self._dispatch_sync_event(
                        request.userId,
                        request.deviceId,
                        event,
                    )
                    if result == "duplicate":
                        duplicate_count += 1
                    else:
                        success_count += 1
                except BizException as exc:
                    fail_count += 1
                    message = self._format_sync_event_error(event.clientId, exc)
                    error_messages.append(message)
                    logger.warning("sync event failed clientId={} message={}", event.clientId, exc.message)
                except (json.JSONDecodeError, PydanticValidationError) as exc:
                    fail_count += 1
                    error_messages.append(self._format_sync_event_error(event.clientId, exc))
                    logger.warning("sync event parse failed clientId={}", event.clientId)
                except SQLAlchemyError as exc:
                    fail_count += 1
                    error_messages.append(self._format_sync_event_error(event.clientId, exc))
                    logger.exception("sync event database error clientId={}", event.clientId)
                except Exception as exc:
                    fail_count += 1
                    error_messages.append(self._format_sync_event_error(event.clientId, exc))
                    logger.exception("sync event unexpected error clientId={}", event.clientId)

            if fail_count == 0:
                sync_result_label = "success"
            elif success_count > 0 or duplicate_count > 0:
                sync_result_label = "partial"
            else:
                sync_result_label = "failed"

            server_time = now_ms()
            return self._build_cloud_save_response(
                request=request,
                user=user,
                server_time=server_time,
                received_count=received_count,
                success_count=success_count,
                duplicate_count=duplicate_count,
                fail_count=fail_count,
            )
        except BizException:
            sync_result_label = "failed"
            raise
        except SQLAlchemyError as exc:
            sync_result_label = "failed"
            logger.exception("云存档同步数据库异常 userId={}", request.userId)
            raise BizException(ErrorCode.SYSTEM_ERROR, message="数据库异常") from exc
        except Exception as exc:
            sync_result_label = "failed"
            logger.exception("云存档同步未预期异常 userId={}", request.userId)
            raise BizException(ErrorCode.SYSTEM_ERROR, message="服务器内部错误") from exc
        finally:
            finish_time = now_ms()
            self._append_sync_log(
                request=request,
                sync_result=sync_result_label,
                received_count=received_count,
                success_count=success_count,
                duplicate_count=duplicate_count,
                fail_count=fail_count,
                start_time=start_time,
                finish_time=finish_time,
                error_messages=error_messages,
            )
