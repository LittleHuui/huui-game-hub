"""同步域模块级编排服务。"""

from typing import List, Literal

from app.core.exceptions import ValidationException
from app.modules.inventory.module_service import InventoryModuleService
from app.modules.match.module_service import MatchModuleService
from app.modules.match.schemas import (
    MatchRecordCreate,
    ScoreRecordCreate,
    object_to_json_text,
)
from app.modules.prop.schemas import PropPurchaseRequest, PropUsageRecordCreate
from app.modules.purchase.module_service import PurchaseModuleService
from app.modules.score.module_service import ScoreModuleService
from app.modules.sync.entity_service import (
    as_required_str,
    payload_array,
    payload_bool,
    payload_int,
    payload_object,
    payload_str,
    require_fields,
)
from app.modules.sync.schemas import PendingEvent
from app.modules.user.module_service import UserModuleService
from app.modules.wallet.module_service import WalletModuleService

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

_STATE_SYNC_EVENT_TYPES = frozenset(
    {
        "user_update",
        "user_system_setting_update",
        "user_game_setting_update",
    }
)


def order_cloud_save_events(events: List[PendingEvent]) -> List[PendingEvent]:
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


class SyncModuleService:
    """同步模块：pending 事件排序、幂等分发与各领域写入。"""

    def __init__(
        self,
        user_module: UserModuleService,
        wallet_module: WalletModuleService,
        purchase_module: PurchaseModuleService,
        inventory_module: InventoryModuleService,
        match_module: MatchModuleService,
        score_module: ScoreModuleService,
    ) -> None:
        self._users = user_module
        self._wallet = wallet_module
        self._purchase = purchase_module
        self._inventory = inventory_module
        self._match = match_module
        self._score = score_module

    def dispatch_cloud_save_event(
        self,
        user_id: str,
        device_id: str,
        event: PendingEvent,
    ) -> SyncEventResult:
        """
        按 eventType 幂等分发单条云存档事件。

        :param user_id: 用户主键。
        :param device_id: 设备 ID。
        :param event: 待处理事件。
        :return: ``success`` 或 ``duplicate``。
        """
        event_type = event.eventType
        if event_type not in _SUPPORTED_SYNC_EVENT_TYPES:
            raise ValidationException("不支持的 eventType: {0}".format(event_type))
        if event_type == "wallet_ledger" and self._wallet.ledger_exists(user_id, event.clientId):
            return "duplicate"
        if event_type == "prop_purchase" and self._purchase.purchase_exists(user_id, event.clientId):
            return "duplicate"
        if event_type == "prop_usage" and self._inventory.usage_exists(user_id, event.clientId):
            return "duplicate"
        if event_type == "match_record" and self._match.match_record_exists(user_id, event.clientId):
            self._dispatch(user_id, device_id, event)
            return "duplicate"
        if event_type == "score_record" and self._score.score_record_exists(user_id, event.clientId):
            return "duplicate"
        self._dispatch(user_id, device_id, event)
        return "success"

    def dispatch_pending_event(self, user_id: str, device_id: str, event: PendingEvent) -> None:
        """
        对外暴露的单条事件分发入口（供 boot 等编排层调用）。

        :param user_id: 用户主键。
        :param device_id: 设备 ID。
        :param event: 待处理事件。
        """
        self._dispatch(user_id, device_id, event)

    def _dispatch(self, user_id: str, device_id: str, event: PendingEvent) -> None:
        """
        将单条事件按 ``eventType`` 路由到对应业务模块。

        :param user_id: 批次用户主键。
        :param device_id: 设备 ID。
        :param event: 待处理事件。
        """
        handlers = {
            "user_update": self._handle_user_update,
            "user_system_setting_update": self._handle_user_system_setting_update,
            "user_game_setting_update": self._handle_user_game_setting_update,
            "wallet_ledger": self._handle_wallet_ledger,
            "prop_purchase": self._handle_prop_purchase,
            "prop_usage": self._handle_prop_usage,
            "match_record": self._handle_match_record,
            "score_record": self._handle_score_record,
        }
        handler = handlers.get(event.eventType)
        if handler is None:
            raise ValidationException("不支持的 eventType: {0}".format(event.eventType))
        handler(user_id, device_id, event)

    def _handle_user_update(self, user_id: str, device_id: str, event: PendingEvent) -> None:
        """
        分发用户资料更新事件。

        :param user_id: 用户主键。
        :param device_id: 请求设备 ID。
        :param event: 事件。
        """
        self._users.merge_user_account_from_sync(user_id, event.updatedAt, event.payload)

    def _handle_user_system_setting_update(self, user_id: str, device_id: str, event: PendingEvent) -> None:
        """
        分发用户系统设置更新事件。

        :param user_id: 用户主键。
        :param device_id: 设备 ID。
        :param event: 事件。
        """
        del device_id
        self._users.merge_user_system_setting_from_sync(user_id, event.updatedAt, event.payload)

    def _handle_user_game_setting_update(
        self,
        user_id: str,
        device_id: str,
        event: PendingEvent,
    ) -> None:
        """
        分发用户游戏设置更新事件。

        :param user_id: 用户主键。
        :param device_id: 请求设备 ID（未使用，保留签名一致）。
        :param event: 事件。
        """
        del device_id
        self._users.merge_user_game_setting_from_sync(user_id, event.updatedAt, event.payload)

    def _handle_wallet_ledger(self, user_id: str, device_id: str, event: PendingEvent) -> None:
        """
        分发钱包流水事件。

        :param user_id: 用户主键。
        :param device_id: 设备 ID。
        :param event: 事件。
        """
        require_fields(event.payload, ["changeType", "reason", "amount"], event)
        change_type = as_required_str(payload_str(event.payload, "changeType"), "changeType")
        reason = as_required_str(payload_str(event.payload, "reason"), "reason")
        amount = payload_int(event.payload, "amount")
        if amount is None:
            raise ValidationException("amount 不能为空")
        self._wallet.apply_ledger_by_change_type(
            user_id=user_id,
            client_id=event.clientId,
            change_type=change_type,
            reason=reason,
            amount=amount,
            device_id=device_id,
            game_code=payload_str(event.payload, "gameCode"),
            payload_json=object_to_json_text(payload_object(event.payload, "payload")),
        )

    def _handle_prop_purchase(self, user_id: str, device_id: str, event: PendingEvent) -> None:
        """
        分发道具购买事件。

        :param user_id: 用户主键。
        :param device_id: 设备 ID。
        :param event: 事件。
        """
        require_fields(event.payload, ["gameCode", "propCode", "quantity"], event)
        quantity = payload_int(event.payload, "quantity")
        if quantity is None or quantity < 1:
            raise ValidationException("quantity 必须为正整数")
        wallet_client_id = payload_str(event.payload, "walletClientId")
        if wallet_client_id is None or not wallet_client_id.strip():
            wallet_client_id = "{0}:wallet".format(event.clientId)
        unit_price = payload_int(event.payload, "unitPrice")
        total_price = payload_int(event.payload, "totalPrice")
        self._purchase.purchase_prop(
            PropPurchaseRequest(
                clientId=event.clientId,
                walletClientId=wallet_client_id,
                userId=user_id,
                deviceId=device_id,
                gameCode=as_required_str(payload_str(event.payload, "gameCode"), "gameCode"),
                propCode=as_required_str(payload_str(event.payload, "propCode"), "propCode"),
                quantity=quantity,
            ),
            unit_price=unit_price,
            total_price=total_price,
        )

    def _handle_prop_usage(self, user_id: str, device_id: str, event: PendingEvent) -> None:
        """
        分发道具使用事件。

        :param user_id: 用户主键。
        :param device_id: 设备 ID。
        :param event: 事件。
        """
        require_fields(event.payload, ["gameCode", "propCode"], event)
        quantity = payload_int(event.payload, "quantity", default=1)
        if quantity is None or quantity < 1:
            raise ValidationException("quantity 必须为正整数")
        self._inventory.record_prop_usage(
            PropUsageRecordCreate(
                clientId=event.clientId,
                userId=user_id,
                deviceId=device_id,
                gameCode=as_required_str(payload_str(event.payload, "gameCode"), "gameCode"),
                matchId=payload_str(event.payload, "matchId"),
                propCode=as_required_str(payload_str(event.payload, "propCode"), "propCode"),
                quantity=quantity,
                useReason=payload_str(event.payload, "useReason"),
                payload=payload_object(event.payload, "payload"),
                consumeFromBag=payload_bool(event.payload, "consumeFromBag", default=True),
            )
        )

    def _handle_match_record(self, user_id: str, device_id: str, event: PendingEvent) -> None:
        """
        分发对局记录事件。

        :param user_id: 用户主键。
        :param device_id: 设备 ID。
        :param event: 事件。
        """
        require_fields(event.payload, ["gameCode", "mode", "result"], event)
        self._match.create_match_record_if_not_exists(
            MatchRecordCreate(
                clientId=event.clientId,
                userId=user_id,
                deviceId=device_id,
                gameCode=as_required_str(payload_str(event.payload, "gameCode"), "gameCode"),
                mode=as_required_str(payload_str(event.payload, "mode"), "mode"),
                result=as_required_str(payload_str(event.payload, "result"), "result"),
                difficultyCode=payload_str(event.payload, "difficultyCode"),
                durationMs=payload_int(event.payload, "durationMs"),
                score=payload_int(event.payload, "score", default=0) or 0,
                propUses=payload_array(event.payload, "propUses"),
                payload=payload_object(event.payload, "payload"),
            )
        )

    def _handle_score_record(self, user_id: str, device_id: str, event: PendingEvent) -> None:
        """
        分发成绩记录事件。

        :param user_id: 用户主键。
        :param device_id: 设备 ID。
        :param event: 事件。
        """
        require_fields(event.payload, ["gameCode", "mode", "result", "score"], event)
        score = payload_int(event.payload, "score")
        if score is None:
            raise ValidationException("score 不能为空")
        self._score.create_score_record_if_not_exists(
            ScoreRecordCreate(
                clientId=event.clientId,
                userId=user_id,
                deviceId=device_id,
                gameCode=as_required_str(payload_str(event.payload, "gameCode"), "gameCode"),
                mode=as_required_str(payload_str(event.payload, "mode"), "mode"),
                difficultyCode=payload_str(event.payload, "difficultyCode"),
                result=as_required_str(payload_str(event.payload, "result"), "result"),
                score=score,
                durationMs=payload_int(event.payload, "durationMs"),
                payload=payload_object(event.payload, "payload"),
            )
        )
