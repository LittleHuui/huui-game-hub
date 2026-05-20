"""购买域模块级编排服务。"""

from typing import List, Optional

from app.common.page_response import PageResponse
from app.common.exceptions import NotFoundException, ValidationException
from app.modules.boot.schemas import PropPurchaseRecordResponse
from app.modules.inventory.entity_service import UserPropBagEntityService
from app.modules.inventory.module_service import InventoryModuleService
from app.modules.purchase.converters import (
    to_prop_purchase_record_response,
    to_user_prop_bag_response,
    to_user_wallet_response,
)
from app.modules.purchase.entity_service import PropPurchaseRecordEntityService
from app.modules.purchase.models import PropPurchaseRecord
from app.modules.purchase.schemas import CreatePropPurchaseRequest, PropPurchaseResultResponse
from app.modules.prop.module_service import PropModuleService
from app.modules.prop.schemas import PropPurchaseRecordRead, PropPurchaseRequest
from app.modules.user.entity_service import UserAccountEntityService
from app.modules.wallet.module_service import WalletModuleService

_REASON_BUY_PROP = "buy_prop"


class PurchaseModuleService:
    """购买模块：购买行为编排，支付走钱包，库存走背包聚合。"""

    def __init__(
        self,
        purchase_entity: PropPurchaseRecordEntityService,
        prop_module: PropModuleService,
        wallet_module: WalletModuleService,
        inventory_module: InventoryModuleService,
        bag_entity: UserPropBagEntityService,
        user_accounts: UserAccountEntityService,
    ) -> None:
        self._purchases = purchase_entity
        self._prop = prop_module
        self._wallet = wallet_module
        self._inventory = inventory_module
        self._bags = bag_entity
        self._users = user_accounts

    def purchase_prop_with_result(self, request: CreatePropPurchaseRequest) -> PropPurchaseResultResponse:
        """
        购买道具并返回购买记录、钱包与背包快照（幂等）。

        :param request: 购买请求。
        :return: 购买结果聚合响应。
        """
        self._require_user(request.userId)
        if request.quantity <= 0:
            raise ValidationException("购买数量必须大于 0")

        existing = self._purchases.get_by_user_and_client_id(request.userId, request.clientId)
        if existing is not None:
            return self._build_purchase_result(existing)

        rule = self._prop.require_enabled_rule(request.gameCode, request.propCode)
        self._prop.require_enabled_definition(request.propCode)

        unit_price = rule.price
        if unit_price < 0:
            raise ValidationException("道具单价无效")
        total_price = unit_price * request.quantity
        if total_price < 0:
            raise ValidationException("购买总价无效")

        wallet_snapshot = self._wallet.rebuild_wallet_from_ledgers(request.userId)
        if wallet_snapshot.balance < total_price:
            raise ValidationException("积分余额不足")

        wallet_client_id = "{0}:wallet".format(request.clientId)
        self._wallet.add_wallet_ledger(
            user_id=request.userId,
            client_id=wallet_client_id,
            change_type="cost",
            reason=_REASON_BUY_PROP,
            amount=total_price,
            device_id=request.deviceId,
            game_code=request.gameCode,
            payload_json=None,
        )

        record = self._purchases.create_record(
            client_id=request.clientId,
            user_id=request.userId,
            device_id=request.deviceId,
            game_code=request.gameCode,
            prop_code=request.propCode,
            quantity=request.quantity,
            unit_price=unit_price,
            total_price=total_price,
        )
        self._inventory.rebuild_inventory_from_records(request.userId)
        return self._build_purchase_result(record)

    def list_purchase_records_page(
        self,
        user_id: str,
        *,
        game_code: Optional[str] = None,
        prop_code: Optional[str] = None,
        page_num: int = 1,
        page_size: int = 20,
    ) -> PageResponse[PropPurchaseRecordResponse]:
        """
        分页查询用户购买记录。

        :param user_id: 用户主键。
        :param game_code: 可选游戏编码过滤。
        :param prop_code: 可选道具编码过滤。
        :param page_num: 页码，从 1 开始。
        :param page_size: 每页条数。
        :return: 分页购买记录响应。
        """
        self._require_user(user_id)
        rows, total = self._purchases.page_by_user(
            user_id,
            game_code=game_code,
            prop_code=prop_code,
            page_num=page_num,
            page_size=page_size,
        )
        items = [to_prop_purchase_record_response(row) for row in rows]
        return PageResponse(
            pageNum=page_num,
            pageSize=page_size,
            total=total,
            items=items,
        )

    def purchase_prop(
        self,
        payload: PropPurchaseRequest,
        *,
        unit_price: Optional[int] = None,
        total_price: Optional[int] = None,
    ) -> PropPurchaseRecordRead:
        """
        购买道具：校验规则与价格、扣减积分、落购买记录并重算背包。

        :param payload: 购买请求。
        :param unit_price: 可选单价（同步事件携带时优先）。
        :param total_price: 可选总价（同步事件携带时优先）。
        :return: 购买记录视图。
        """
        existing = self._purchases.get_by_user_and_client_id(payload.userId, payload.clientId)
        if existing is not None:
            return PropPurchaseRecordRead.model_validate(existing)

        rule = self._prop.require_enabled_rule(payload.gameCode, payload.propCode)
        self._prop.require_enabled_definition(payload.propCode)

        resolved_unit_price = unit_price if unit_price is not None else rule.price
        if resolved_unit_price < 0:
            raise ValidationException("道具单价无效")
        resolved_total_price = (
            total_price if total_price is not None else resolved_unit_price * payload.quantity
        )
        if resolved_total_price < 0:
            raise ValidationException("购买总价无效")

        wallet_snapshot = self._wallet.rebuild_wallet_from_ledgers(payload.userId)
        if wallet_snapshot.balance < resolved_total_price:
            raise ValidationException("积分余额不足")

        self._wallet.add_wallet_ledger(
            user_id=payload.userId,
            client_id=payload.walletClientId,
            change_type="cost",
            reason=_REASON_BUY_PROP,
            amount=resolved_total_price,
            device_id=payload.deviceId,
            game_code=payload.gameCode,
            payload_json=None,
        )

        record = self._purchases.create_record(
            client_id=payload.clientId,
            user_id=payload.userId,
            device_id=payload.deviceId,
            game_code=payload.gameCode,
            prop_code=payload.propCode,
            quantity=payload.quantity,
            unit_price=resolved_unit_price,
            total_price=resolved_total_price,
        )
        self._inventory.rebuild_inventory_from_records(payload.userId)
        return PropPurchaseRecordRead.model_validate(record)

    def list_purchase_records(self, user_id: str) -> List[PropPurchaseRecord]:
        """
        列出用户道具购买记录。

        :param user_id: 用户主键。
        :return: 购买记录实体列表。
        """
        return self._purchases.list_by_user(user_id)

    def purchase_exists(self, user_id: str, client_id: str) -> bool:
        """
        判断购买记录是否已存在（幂等去重）。

        :param user_id: 用户主键。
        :param client_id: 客户端幂等 ID。
        :return: 已存在为 True。
        """
        return self._purchases.get_by_user_and_client_id(user_id, client_id) is not None

    def _require_user(self, user_id: str) -> None:
        """
        校验用户存在且未软删。

        :param user_id: 用户主键。
        :raises NotFoundException: 用户不存在。
        """
        if self._users.get_by_server_id(user_id) is None:
            raise NotFoundException("用户不存在")

    def _build_purchase_result(self, record: PropPurchaseRecord) -> PropPurchaseResultResponse:
        """
        组装购买结果（重算钱包与背包快照，不重复扣款）。

        :param record: 购买记录实体。
        :return: 购买结果聚合响应。
        """
        self._wallet.rebuild_wallet_from_ledgers(record.user_id)
        wallet_entity = self._wallet.get_or_create_wallet(record.user_id)
        self._inventory.rebuild_inventory_from_records(record.user_id)
        bag = self._bags.ensure_line(record.user_id, record.game_code, record.prop_code)
        return PropPurchaseResultResponse(
            purchaseRecord=to_prop_purchase_record_response(record),
            wallet=to_user_wallet_response(wallet_entity),
            inventoryItem=to_user_prop_bag_response(bag),
        )
