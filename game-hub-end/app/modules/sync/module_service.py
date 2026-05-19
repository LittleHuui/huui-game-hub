"""同步域模块级编排服务。"""

import json
from typing import Any, Dict, List, Optional

from app.core.exceptions import NotFoundException, ValidationException
from app.core.time_utils import now_ms
from app.modules.inventory.module_service import InventoryModuleService
from app.modules.match.module_service import MatchModuleService
from app.modules.match.schemas import MatchRecordCreate, MatchRecordRead, ScoreRecordRead
from app.modules.prop.schemas import PropPurchaseRecordRead, PropPurchaseRequest, PropUsageRecordCreate, PropUsageRecordRead
from app.modules.purchase.module_service import PurchaseModuleService
from app.modules.score.module_service import ScoreModuleService
from app.modules.match.schemas import ScoreRecordCreate
from app.modules.sync.entity_service import (
    SyncLogEntityService,
    as_required_str,
    payload_bool,
    payload_int,
    payload_json_text,
    payload_str,
    require_fields,
)
from app.modules.sync.schemas import (
    CloudSaveRequest,
    CloudSaveResponse,
    PendingEvent,
    bag_row_to_cloud,
    game_setting_to_cloud_dict,
    score_record_read_to_cloud,
    system_setting_to_cloud_dict,
    user_to_cloud,
    wallet_to_cloud,
)
from app.modules.user.module_service import UserModuleService
from app.modules.user.schemas import UserAccountRead
from app.modules.wallet.module_service import WalletModuleService
from app.modules.wallet.schemas import UserWalletRead, WalletLedgerRead


class SyncModuleService:
    """同步模块：仅负责事件分发、同步日志与快照聚合。"""

    def __init__(
        self,
        sync_log_entity: SyncLogEntityService,
        user_module: UserModuleService,
        wallet_module: WalletModuleService,
        purchase_module: PurchaseModuleService,
        inventory_module: InventoryModuleService,
        match_module: MatchModuleService,
        score_module: ScoreModuleService,
    ) -> None:
        self._sync_logs = sync_log_entity
        self._users = user_module
        self._wallet = wallet_module
        self._purchase = purchase_module
        self._inventory = inventory_module
        self._match = match_module
        self._score = score_module

    def cloud_save(self, body: CloudSaveRequest) -> CloudSaveResponse:
        """
        处理 pending 事件并返回完整云存档快照。

        :param body: 云存档同步请求。
        :return: 云存档响应。
        """
        self._validate_cloud_save_request(body)
        server_time = now_ms()
        success_count = 0
        fail_count = 0
        error_messages: List[str] = []

        for event in body.pendingEvents:
            try:
                self._dispatch(body.userId, body.deviceId, event)
                success_count += 1
            except (ValidationException, NotFoundException) as exc:
                fail_count += 1
                error_messages.append("{0}: {1}".format(event.clientId, exc.message))

        sync_result = "success" if fail_count == 0 else "partial" if success_count > 0 else "failed"
        self._sync_logs.append_cloud_save(
            user_id=body.userId,
            device_id=body.deviceId,
            sync_result=sync_result,
            pending_count=len(body.pendingEvents),
            success_count=success_count,
            fail_count=fail_count,
            error_message="; ".join(error_messages) if error_messages else None,
            payload_json=json.dumps(
                {
                    "clientSnapshotVersion": body.clientSnapshotVersion,
                    "processedClientIds": [e.clientId for e in body.pendingEvents],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        )

        if fail_count > 0 and success_count == 0:
            raise ValidationException(error_messages[0] if error_messages else "同步失败")

        return self._build_cloud_snapshot(
            user_id=body.userId,
            server_time=server_time,
            cloud_snapshot_version=self._resolve_cloud_version(body),
        )

    def _resolve_cloud_version(self, body: CloudSaveRequest) -> int:
        """
        计算服务端云存档版本号。

        :param body: 同步请求。
        :return: 云存档版本。
        """
        base = body.clientSnapshotVersion if body.clientSnapshotVersion > 0 else 0
        if body.pendingEvents:
            return base + 1
        return base if base > 0 else 1

    def _build_cloud_snapshot(
        self,
        *,
        user_id: str,
        server_time: int,
        cloud_snapshot_version: int,
    ) -> CloudSaveResponse:
        """
        聚合各业务模块数据构建云存档响应。

        :param user_id: 用户主键。
        :param server_time: 服务器时间戳（毫秒）。
        :param cloud_snapshot_version: 云存档版本。
        :return: 云存档响应。
        """
        detail = self._users.get_user_detail(user_id)
        self._wallet.rebuild_wallet_from_ledgers(user_id)
        self._inventory.rebuild_inventory_from_records(user_id)
        wallet_read = UserWalletRead.model_validate(self._wallet.get_or_create_wallet(user_id))
        bag = self._inventory.get_user_bag(user_id)
        game_settings = self._users.list_user_game_settings(user_id)
        system_setting = self._users.read_user_system_setting(user_id)
        settings: List[Dict[str, Any]] = [game_setting_to_cloud_dict(s) for s in game_settings]
        settings.append(system_setting_to_cloud_dict(system_setting))
        histories = [
            MatchRecordRead.model_validate(row)
            for row in self._match.list_user_matches(user_id, limit=100)
        ]
        wallet_ledgers = [
            WalletLedgerRead.model_validate(row) for row in self._wallet.list_ledgers(user_id)
        ]
        purchase_records = [
            PropPurchaseRecordRead.model_validate(row)
            for row in self._purchase.list_purchase_records(user_id)
        ]
        usage_records = [
            PropUsageRecordRead.model_validate(row)
            for row in self._inventory.list_usage_records(user_id)
        ]
        score_records = [
            score_record_read_to_cloud(ScoreRecordRead.model_validate(row))
            for row in self._score.list_user_score_records(user_id, limit=200)
        ]

        return CloudSaveResponse(
            serverTime=server_time,
            cloudSnapshotVersion=cloud_snapshot_version,
            user=user_to_cloud(UserAccountRead.model_validate(detail.user)),
            wallet=wallet_to_cloud(wallet_read),
            inventory=[bag_row_to_cloud(row) for row in bag.items],
            settings=settings,
            histories=histories,
            walletLedgers=wallet_ledgers,
            propUsageRecords=usage_records,
            purchaseRecords=purchase_records,
            matchRecords=histories,
            scoreRecords=score_records,
        )

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
        require_fields(event.payload, ["change_type", "reason", "amount"], event)
        change_type = as_required_str(
            payload_str(event.payload, "change_type", "changeType"),
            "change_type",
        )
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
            game_code=payload_str(event.payload, "game_code", "gameCode"),
            payload_json=payload_json_text(event.payload, "payload_json", "payloadJson", "payload"),
        )

    def _handle_prop_purchase(self, user_id: str, device_id: str, event: PendingEvent) -> None:
        """
        分发道具购买事件。

        :param user_id: 用户主键。
        :param device_id: 设备 ID。
        :param event: 事件。
        """
        require_fields(
            event.payload,
            ["game_code", "prop_code", "quantity"],
            event,
        )
        quantity = payload_int(event.payload, "quantity")
        if quantity is None or quantity < 1:
            raise ValidationException("quantity 必须为正整数")
        wallet_client_id = payload_str(event.payload, "wallet_client_id", "walletClientId")
        if wallet_client_id is None or not wallet_client_id.strip():
            wallet_client_id = "{0}:wallet".format(event.clientId)
        unit_price = payload_int(event.payload, "unit_price", "unitPrice")
        total_price = payload_int(event.payload, "total_price", "totalPrice")
        self._purchase.purchase_prop(
            PropPurchaseRequest(
                clientId=event.clientId,
                walletClientId=wallet_client_id,
                userId=user_id,
                deviceId=device_id,
                gameCode=as_required_str(
                    payload_str(event.payload, "game_code", "gameCode"),
                    "game_code",
                ),
                propCode=as_required_str(
                    payload_str(event.payload, "prop_code", "propCode"),
                    "prop_code",
                ),
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
        require_fields(event.payload, ["game_code", "prop_code"], event)
        quantity = payload_int(event.payload, "quantity", default=1)
        if quantity is None or quantity < 1:
            raise ValidationException("quantity 必须为正整数")
        self._inventory.record_prop_usage(
            PropUsageRecordCreate(
                clientId=event.clientId,
                userId=user_id,
                deviceId=device_id,
                gameCode=as_required_str(
                    payload_str(event.payload, "game_code", "gameCode"),
                    "game_code",
                ),
                matchId=payload_str(event.payload, "match_id", "matchId"),
                propCode=as_required_str(
                    payload_str(event.payload, "prop_code", "propCode"),
                    "prop_code",
                ),
                quantity=quantity,
                useReason=payload_str(event.payload, "use_reason", "useReason"),
                payloadJson=payload_json_text(event.payload, "payload_json", "payloadJson", "payload"),
                consumeFromBag=payload_bool(event.payload, "consume_from_bag", "consumeFromBag", default=True),
            )
        )

    def _handle_match_record(self, user_id: str, device_id: str, event: PendingEvent) -> None:
        """
        分发对局记录事件。

        :param user_id: 用户主键。
        :param device_id: 设备 ID。
        :param event: 事件。
        """
        require_fields(event.payload, ["game_code", "mode", "result"], event)
        self._match.create_match_record_if_not_exists(
            MatchRecordCreate(
                clientId=event.clientId,
                userId=user_id,
                deviceId=device_id,
                gameCode=as_required_str(
                    payload_str(event.payload, "game_code", "gameCode"),
                    "game_code",
                ),
                mode=as_required_str(payload_str(event.payload, "mode"), "mode"),
                result=as_required_str(payload_str(event.payload, "result"), "result"),
                difficultyCode=payload_str(event.payload, "difficulty_code", "difficultyCode"),
                durationMs=payload_int(event.payload, "duration_ms", "durationMs"),
                score=payload_int(event.payload, "score", default=0) or 0,
                propUsesJson=payload_json_text(event.payload, "prop_uses_json", "propUsesJson"),
                payloadJson=payload_json_text(event.payload, "payload_json", "payloadJson", "payload"),
            )
        )

    def _handle_score_record(self, user_id: str, device_id: str, event: PendingEvent) -> None:
        """
        分发成绩记录事件。

        :param user_id: 用户主键。
        :param device_id: 设备 ID。
        :param event: 事件。
        """
        require_fields(event.payload, ["game_code", "mode", "result", "score"], event)
        score = payload_int(event.payload, "score")
        if score is None:
            raise ValidationException("score 不能为空")
        self._score.create_score_record_if_not_exists(
            ScoreRecordCreate(
                clientId=event.clientId,
                userId=user_id,
                deviceId=device_id,
                gameCode=as_required_str(
                    payload_str(event.payload, "game_code", "gameCode"),
                    "game_code",
                ),
                mode=as_required_str(payload_str(event.payload, "mode"), "mode"),
                difficultyCode=payload_str(event.payload, "difficulty_code", "difficultyCode"),
                result=as_required_str(payload_str(event.payload, "result"), "result"),
                score=score,
                durationMs=payload_int(event.payload, "duration_ms", "durationMs"),
                payloadJson=payload_json_text(event.payload, "payload_json", "payloadJson", "payload"),
            )
        )

    def _validate_cloud_save_request(self, body: CloudSaveRequest) -> None:
        """
        校验云存档同步请求（用户存在性与批次内 clientId 唯一）。

        :param body: 同步请求体。
        :raises NotFoundException: 用户不存在。
        :raises ValidationException: 事件列表非法。
        """
        self._users.get_user_detail(body.userId)
        seen_client_ids: List[str] = []
        for idx, event in enumerate(body.pendingEvents):
            if event.clientId in seen_client_ids:
                raise ValidationException(f"同一批次内 clientId 重复: index={idx}")
            seen_client_ids.append(event.clientId)
