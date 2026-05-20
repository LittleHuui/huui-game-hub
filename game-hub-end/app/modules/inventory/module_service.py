"""背包域模块级编排服务。"""

from typing import Dict, List, Optional, Set, Tuple

from app.common.page_response import PageResponse
from app.common.exceptions import NotFoundException, ValidationException
from app.modules.boot.schemas import PropUsageRecordResponse, UserPropBagResponse
from app.modules.inventory.entity_service import (
    PropUsageRecordEntityService,
    UserPropBagEntityService,
)
from app.modules.inventory.mappers import to_prop_usage_record_response, to_user_prop_bag_response
from app.modules.inventory.models import PropUsageRecord, UserPropBag
from app.modules.match.schemas import object_to_json_text
from app.modules.prop.schemas import (
    PropUsageRecordCreate,
    PropUsageRecordRead,
    UserPropBagListData,
    UserPropBagRead,
)
from app.modules.purchase.entity_service import PropPurchaseRecordEntityService
from app.modules.user.entity_service import UserAccountEntityService


class InventoryModuleService:
    """背包模块：库存聚合与重算，不处理支付与道具定义。"""

    def __init__(
        self,
        bag_entity: UserPropBagEntityService,
        purchase_entity: PropPurchaseRecordEntityService,
        usage_entity: PropUsageRecordEntityService,
        account_entity: UserAccountEntityService,
    ) -> None:
        self._bags = bag_entity
        self._purchases = purchase_entity
        self._usages = usage_entity
        self._accounts = account_entity

    def get_user_bag(self, user_id: str, *, game_code: Optional[str] = None) -> UserPropBagListData:
        """
        查询用户道具背包（快照表，调用方可在写入后重算）。

        :param user_id: 用户主键。
        :param game_code: 可选，按游戏过滤。
        :return: 背包列表视图。
        """
        rows = self._bags.list_by_user(user_id, game_code=game_code)
        return UserPropBagListData(
            user_id=user_id,
            items=[UserPropBagRead.model_validate(row) for row in rows if row.quantity > 0],
        )

    def rebuild_inventory_from_records(self, user_id: str) -> List[UserPropBag]:
        """
        按购买/使用记录重算背包数量（权威来源为流水，不信任直接改 quantity）。

        :param user_id: 用户主键。
        :return: 重算后 quantity 大于 0 的背包行。
        """
        purchase_totals = self._aggregate_purchase_totals(user_id)
        usage_totals = self._aggregate_usage_totals(user_id)
        computed = self._compute_net_quantities(purchase_totals, usage_totals)
        existing_map = {(row.game_code, row.prop_code): row for row in self._bags.list_by_user(user_id)}
        touched_keys = self._apply_computed_quantities(user_id, computed, existing_map)
        self._zero_untouched_bag_lines(existing_map, touched_keys)
        return [row for row in self._bags.list_by_user(user_id) if row.quantity > 0]

    def record_prop_usage(self, payload: PropUsageRecordCreate) -> PropUsageRecordRead:
        """
        记录道具使用（幂等）；背包数量由购买/使用记录聚合重算。

        :param payload: 使用记录请求。
        :return: 使用记录视图。
        """
        existing = self._usages.get_by_user_and_client_id(payload.userId, payload.clientId)
        if existing is not None:
            return PropUsageRecordRead.model_validate(existing)

        if payload.consumeFromBag:
            self._assert_usage_available(payload)

        record = self._usages.create_record(
            client_id=payload.clientId,
            user_id=payload.userId,
            device_id=payload.deviceId,
            game_code=payload.gameCode,
            match_id=payload.matchId,
            prop_code=payload.propCode,
            quantity=payload.quantity,
            use_reason=payload.useReason,
            payload_json=object_to_json_text(payload.payload),
        )
        if payload.consumeFromBag:
            self.rebuild_inventory_from_records(payload.userId)
        return PropUsageRecordRead.model_validate(record)

    def list_usage_records(self, user_id: str) -> List[PropUsageRecord]:
        """
        列出用户道具使用记录。

        :param user_id: 用户主键。
        :return: 使用记录实体列表。
        """
        return self._usages.list_by_user(user_id)

    def list_user_inventory(
        self,
        user_id: str,
        *,
        game_code: Optional[str] = None,
    ) -> List[UserPropBagResponse]:
        """
        查询用户背包快照（不重算）。

        :param user_id: 用户主键。
        :param game_code: 可选游戏过滤。
        :return: 背包响应列表。
        :raises NotFoundException: 用户不存在。
        """
        self._ensure_user_exists(user_id)
        normalized_game_code = self._normalize_optional_filter(game_code)
        rows = self._bags.list_by_user(user_id, game_code=normalized_game_code)
        return [to_user_prop_bag_response(row) for row in rows]

    def list_usage_records_page(
        self,
        user_id: str,
        *,
        game_code: Optional[str] = None,
        prop_code: Optional[str] = None,
        page_num: int = 1,
        page_size: int = 20,
    ) -> PageResponse[PropUsageRecordResponse]:
        """
        分页查询用户道具使用记录。

        :param user_id: 用户主键。
        :param game_code: 可选游戏过滤。
        :param prop_code: 可选道具过滤。
        :param page_num: 页码，从 1 开始。
        :param page_size: 每页条数。
        :return: 分页使用记录响应。
        :raises NotFoundException: 用户不存在。
        """
        self._ensure_user_exists(user_id)
        normalized_game_code = self._normalize_optional_filter(game_code)
        normalized_prop_code = self._normalize_optional_filter(prop_code)
        total = self._usages.count_by_user(
            user_id,
            game_code=normalized_game_code,
            prop_code=normalized_prop_code,
        )
        rows = self._usages.list_by_user_paged(
            user_id,
            game_code=normalized_game_code,
            prop_code=normalized_prop_code,
            page_num=page_num,
            page_size=page_size,
        )
        return PageResponse(
            pageNum=page_num,
            pageSize=page_size,
            total=total,
            items=[to_prop_usage_record_response(row) for row in rows],
        )

    def usage_exists(self, user_id: str, client_id: str) -> bool:
        """
        判断使用记录是否已存在（幂等去重）。

        :param user_id: 用户主键。
        :param client_id: 客户端幂等 ID。
        :return: 已存在为 True。
        """
        return self._usages.get_by_user_and_client_id(user_id, client_id) is not None

    def _aggregate_purchase_totals(self, user_id: str) -> Dict[Tuple[str, str], int]:
        """汇总用户各道具购买数量。"""
        totals: Dict[Tuple[str, str], int] = {}
        for record in self._purchases.list_by_user(user_id):
            key = (record.game_code, record.prop_code)
            totals[key] = totals.get(key, 0) + record.quantity
        return totals

    def _aggregate_usage_totals(self, user_id: str) -> Dict[Tuple[str, str], int]:
        """汇总用户各道具使用数量。"""
        totals: Dict[Tuple[str, str], int] = {}
        for record in self._usages.list_by_user(user_id):
            key = (record.game_code, record.prop_code)
            totals[key] = totals.get(key, 0) + record.quantity
        return totals

    def _compute_net_quantities(
        self,
        purchase_totals: Dict[Tuple[str, str], int],
        usage_totals: Dict[Tuple[str, str], int],
    ) -> Dict[Tuple[str, str], int]:
        """计算净库存（购买 - 使用）。"""
        computed: Dict[Tuple[str, str], int] = {}
        for key in set(purchase_totals.keys()) | set(usage_totals.keys()):
            computed[key] = purchase_totals.get(key, 0) - usage_totals.get(key, 0)
        return computed

    def _apply_computed_quantities(
        self,
        user_id: str,
        computed: Dict[Tuple[str, str], int],
        existing_map: Dict[Tuple[str, str], UserPropBag],
    ) -> Set[Tuple[str, str]]:
        """将聚合结果写入背包快照表。"""
        touched_keys: Set[Tuple[str, str]] = set()
        for key, raw_quantity in computed.items():
            game_code, prop_code = key
            touched_keys.add(key)
            store_quantity = raw_quantity if raw_quantity > 0 else 0
            bag = existing_map.get(key)
            if bag is None:
                if store_quantity <= 0:
                    continue
                bag = self._bags.ensure_line(user_id, game_code, prop_code)
            self._bags.apply_aggregate_quantity(bag, store_quantity)
            existing_map[key] = bag
        return touched_keys

    def _zero_untouched_bag_lines(
        self,
        existing_map: Dict[Tuple[str, str], UserPropBag],
        touched_keys: Set[Tuple[str, str]],
    ) -> None:
        """将未出现在聚合结果中的背包行数量归零。"""
        for key, bag in existing_map.items():
            if key in touched_keys:
                continue
            if bag.quantity == 0:
                continue
            self._bags.apply_aggregate_quantity(bag, 0)

    def _ensure_user_exists(self, user_id: str) -> None:
        """
        校验用户是否存在。

        :param user_id: 用户主键。
        :raises NotFoundException: 用户不存在。
        """
        if self._accounts.get_by_server_id(user_id, active_only=True) is None:
            raise NotFoundException("用户不存在")

    def _normalize_optional_filter(self, value: Optional[str]) -> Optional[str]:
        """
        规范化可选过滤参数：空白视为未传。

        :param value: 原始过滤值。
        :return: 去空白后的值，或 ``None``。
        """
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return stripped

    def _assert_usage_available(self, payload: PropUsageRecordCreate) -> None:
        """
        校验使用数量不超过当前聚合库存（购买 - 已使用）。

        :param payload: 使用记录请求。
        :raises ValidationException: 库存不足。
        """
        purchase_totals = self._aggregate_purchase_totals(payload.userId)
        usage_totals = self._aggregate_usage_totals(payload.userId)
        key = (payload.gameCode, payload.propCode)
        available = purchase_totals.get(key, 0) - usage_totals.get(key, 0)
        if available < payload.quantity:
            raise ValidationException("道具数量不足")
