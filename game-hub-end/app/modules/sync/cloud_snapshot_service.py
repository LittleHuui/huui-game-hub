from typing import List
from app.modules.sync.cloud_save_schemas import CloudSaveSyncRequest
from app.modules.sync.cloud_save_schemas import CloudSaveSyncResponse
from app.modules.sync.cloud_save_schemas import SyncResultResponse
from app.modules.inventory.response_schemas import UserPropBagResponse
from app.modules.inventory.module_service import InventoryModuleService
from app.modules.match.schemas import to_match_record_response
from app.modules.match.module_service import MatchModuleService
from app.modules.purchase.module_service import PurchaseModuleService
from app.modules.score.module_service import ScoreModuleService
from app.modules.user.models import UserAccount
from app.modules.user.module_service import UserModuleService
from app.modules.inventory.mappers import to_prop_usage_record_response, to_user_prop_bag_response
from app.modules.purchase.converters import to_prop_purchase_record_response
from app.modules.wallet.mappers import to_user_wallet_response, to_wallet_ledger_response
from app.modules.wallet.models import UserWallet
from app.modules.wallet.module_service import WalletModuleService
from app.modules.user.response_mappers import to_user_summary, to_user_system_setting_response, to_user_game_setting_response
from app.modules.score.response_mappers import to_score_record_response


CLOUD_MATCH_RECORD_LIMIT = 100
CLOUD_SCORE_RECORD_LIMIT = 200


class CloudSnapshotService:
    """重建派生资产并读取云存档完整响应。"""

    def __init__(self, user_module_service: UserModuleService, wallet_module_service: WalletModuleService,
                 inventory_module_service: InventoryModuleService, purchase_module_service: PurchaseModuleService,
                 match_module_service: MatchModuleService, score_module_service: ScoreModuleService) -> None:
        """显式注入云快照所需的领域读取与重建能力。"""
        self._user_module_service = user_module_service
        self._wallet_module_service = wallet_module_service
        self._inventory_module_service = inventory_module_service
        self._purchase_module_service = purchase_module_service
        self._match_module_service = match_module_service
        self._score_module_service = score_module_service

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
        wallet_module = self._wallet_module_service
        wallet_module.rebuild_wallet_from_ledgers(user_id)
        return wallet_module.get_or_create_wallet(user_id)

    def _rebuild_user_inventory(self, user_id: str) -> List[UserPropBagResponse]:
        """
        按购买/使用记录重算背包数量（不信任客户端 quantity）。

        :param user_id: 用户主键。
        :return: 重算后的背包响应列表（quantity 为 0 的行不返回）。
        """
        inventory_module = self._inventory_module_service
        rows = inventory_module.rebuild_inventory_from_records(user_id)
        return [to_user_prop_bag_response(row) for row in rows if row.quantity > 0]

    def build_cloud_save_response(
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
        user_module = self._user_module_service
        setting_entity = user_module.get_or_create_user_system_setting(request.userId)
        cloud_snapshot_version = self._resolve_cloud_snapshot_version(request)
        wallet_entity = self._rebuild_user_wallet(request.userId)
        inventory_items = self._rebuild_user_inventory(request.userId)

        wallet_ledgers = [
            to_wallet_ledger_response(row)
            for row in self._wallet_module_service.list_ledgers(request.userId)
        ]

        purchase_records = [
            to_prop_purchase_record_response(row)
            for row in self._purchase_module_service.list_purchase_records(request.userId)
        ]
        prop_usage_records = [
            to_prop_usage_record_response(row)
            for row in self._inventory_module_service.list_usage_records(request.userId)
        ]

        match_records = [
            to_match_record_response(row)
            for row in self._match_module_service.list_user_matches(request.userId, limit=CLOUD_MATCH_RECORD_LIMIT)
        ]
        score_records = [
            to_score_record_response(row)
            for row in self._score_module_service.list_user_score_records(request.userId, limit=CLOUD_SCORE_RECORD_LIMIT)
        ]

        user_game_settings = [
            to_user_game_setting_response(row)
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
            user=to_user_summary(user),
            systemSetting=to_user_system_setting_response(setting_entity),
            wallet=to_user_wallet_response(wallet_entity),
            inventory=inventory_items,
            userGameSettings=user_game_settings,
            walletLedgers=wallet_ledgers,
            purchaseRecords=purchase_records,
            propUsageRecords=prop_usage_records,
            matchRecords=match_records,
            scoreRecords=score_records,
        )
