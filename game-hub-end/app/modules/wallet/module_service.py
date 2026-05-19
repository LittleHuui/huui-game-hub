"""钱包域模块级编排服务。"""

from typing import List, Optional

from app.common.page_response import PageResponse
from app.core.exceptions import NotFoundException, ValidationException
from app.modules.boot.schemas import UserWalletResponse, WalletLedgerResponse
from app.modules.user.entity_service import UserAccountEntityService
from app.modules.wallet.entity_service import UserWalletEntityService, WalletLedgerEntityService
from app.modules.wallet.mappers import to_user_wallet_response, to_wallet_ledger_response
from app.modules.wallet.models import UserWallet, WalletLedger
from app.modules.wallet.schemas import WalletRebuildResult

_CHANGE_GAIN = "gain"
_CHANGE_COST = "cost"
_CHANGE_REFUND = "refund"

_CHANGE_ALIASES = {
    "reward": _CHANGE_GAIN,
    "gain": _CHANGE_GAIN,
    "refund": _CHANGE_REFUND,
    "cost": _CHANGE_COST,
    "spend": _CHANGE_COST,
}


class WalletModuleService:
    """钱包模块对外业务能力：流水为权威来源，钱包为快照。"""

    def __init__(
        self,
        wallet_entity: UserWalletEntityService,
        ledger_entity: WalletLedgerEntityService,
        account_entity: UserAccountEntityService,
    ) -> None:
        self._wallets = wallet_entity
        self._ledgers = ledger_entity
        self._accounts = account_entity

    def get_or_create_wallet(self, user_id: str) -> UserWallet:
        """
        获取用户钱包，不存在则创建空钱包。

        :param user_id: 用户 ``server_id``。
        :return: 钱包实体。
        """
        existing = self._wallets.get_wallet_by_user_id(user_id)
        if existing is not None:
            return existing
        return self._wallets.create_wallet_for_user(user_id)

    def add_wallet_ledger(
        self,
        *,
        user_id: str,
        client_id: str,
        change_type: str,
        reason: str,
        amount: int,
        device_id: Optional[str] = None,
        game_code: Optional[str] = None,
        payload_json: Optional[str] = None,
    ) -> WalletLedger:
        """
        统一写入钱包流水并按流水重算余额（幂等）。

        :param user_id: 用户主键。
        :param client_id: 客户端幂等 ID。
        :param change_type: ``gain`` / ``cost`` / ``refund``（兼容 reward/spend 别名）。
        :param reason: 业务原因。
        :param amount: 正整数变动量。
        :param device_id: 设备 ID，可空。
        :param game_code: 游戏编码，可空。
        :param payload_json: 附加 JSON，可空。
        :return: 流水记录。
        """
        normalized = self._normalize_change_type(change_type)
        if amount <= 0:
            raise ValidationException("流水变动量必须为正整数")
        ledger, is_new = self._ledgers.create_ledger_if_not_exists(
            client_id=client_id,
            user_id=user_id,
            device_id=device_id,
            game_code=game_code,
            change_type=normalized,
            reason=reason,
            amount=amount,
            balance_after=None,
            payload_json=payload_json,
        )
        if not is_new:
            return ledger
        rebuild = self.rebuild_wallet_from_ledgers(user_id)
        if rebuild.balance < 0:
            raise ValidationException("积分余额不足")
        return ledger

    def gain_score(
        self,
        *,
        user_id: str,
        client_id: str,
        amount: int,
        reason: str,
        device_id: Optional[str] = None,
        game_code: Optional[str] = None,
        payload_json: Optional[str] = None,
    ) -> WalletLedger:
        """
        增加积分：写入 ``gain`` 流水并重算余额。

        :param user_id: 用户主键。
        :param client_id: 客户端幂等 ID。
        :param amount: 正整数变动量。
        :param reason: 业务原因。
        :return: 流水记录。
        """
        return self.add_wallet_ledger(
            user_id=user_id,
            client_id=client_id,
            change_type=_CHANGE_GAIN,
            reason=reason,
            amount=amount,
            device_id=device_id,
            game_code=game_code,
            payload_json=payload_json,
        )

    def cost_score(
        self,
        *,
        user_id: str,
        client_id: str,
        amount: int,
        reason: str,
        device_id: Optional[str] = None,
        game_code: Optional[str] = None,
        payload_json: Optional[str] = None,
    ) -> WalletLedger:
        """
        扣减积分：写入 ``cost`` 流水并重算余额。

        :param user_id: 用户主键。
        :param client_id: 客户端幂等 ID。
        :param amount: 正整数扣减量。
        :param reason: 业务原因。
        :return: 流水记录。
        """
        return self.add_wallet_ledger(
            user_id=user_id,
            client_id=client_id,
            change_type=_CHANGE_COST,
            reason=reason,
            amount=amount,
            device_id=device_id,
            game_code=game_code,
            payload_json=payload_json,
        )

    def refund_score(
        self,
        *,
        user_id: str,
        client_id: str,
        amount: int,
        reason: str,
        device_id: Optional[str] = None,
        game_code: Optional[str] = None,
        payload_json: Optional[str] = None,
    ) -> WalletLedger:
        """
        退款：写入 ``refund`` 流水并重算余额。

        :param user_id: 用户主键。
        :param client_id: 客户端幂等 ID。
        :param amount: 正整数退款量。
        :param reason: 业务原因。
        :return: 流水记录。
        """
        return self.add_wallet_ledger(
            user_id=user_id,
            client_id=client_id,
            change_type=_CHANGE_REFUND,
            reason=reason,
            amount=amount,
            device_id=device_id,
            game_code=game_code,
            payload_json=payload_json,
        )

    def apply_ledger_by_change_type(
        self,
        *,
        user_id: str,
        client_id: str,
        change_type: str,
        reason: str,
        amount: int,
        device_id: Optional[str] = None,
        game_code: Optional[str] = None,
        payload_json: Optional[str] = None,
    ) -> WalletLedger:
        """
        按 ``change_type`` 写入流水（供同步编排调用）。

        :param change_type: ``gain`` / ``cost`` / ``refund`` 或兼容别名。
        :param amount: 变动量；若为负数则取绝对值。
        :return: 流水记录。
        """
        normalized = self._normalize_change_type(change_type)
        return self.add_wallet_ledger(
            user_id=user_id,
            client_id=client_id,
            change_type=normalized,
            reason=reason,
            amount=abs(amount),
            device_id=device_id,
            game_code=game_code,
            payload_json=payload_json,
        )

    def ledger_exists(self, user_id: str, client_id: str) -> bool:
        """
        判断钱包流水是否已存在（幂等去重）。

        :param user_id: 用户主键。
        :param client_id: 客户端幂等 ID。
        :return: 已存在为 True。
        """
        return self._ledgers.get_by_user_and_client_id(user_id, client_id) is not None

    def rebuild_wallet_from_ledgers(self, user_id: str) -> WalletRebuildResult:
        """
        按流水升序重放，校正 ``user_wallet`` 快照。

        :param user_id: 用户主键。
        :return: 重算后的余额摘要。
        """
        wallet = self.get_or_create_wallet(user_id)
        rows = self._ledgers.list_ledgers_by_user(user_id)
        balance = 0
        total_earned = 0
        for row in rows:
            delta = self._ledger_balance_delta(row)
            balance += delta
            if row.change_type in (_CHANGE_GAIN, _CHANGE_REFUND) and row.amount > 0:
                total_earned += row.amount
        self._wallets.update_wallet_balance(wallet, balance, total_earned)
        return WalletRebuildResult(user_id=user_id, balance=balance, total_earned=total_earned)

    def list_ledgers(self, user_id: str) -> List[WalletLedger]:
        """
        列出用户流水（确保钱包行存在）。

        :param user_id: 用户主键。
        :return: 按创建时间升序的流水列表。
        """
        self.get_or_create_wallet(user_id)
        return self._ledgers.list_ledgers_by_user(user_id)

    def get_user_wallet(self, user_id: str) -> UserWalletResponse:
        """
        查询用户钱包快照；不存在则创建默认空钱包。

        :param user_id: 用户主键。
        :return: 钱包 API 响应。
        :raises NotFoundException: 用户不存在。
        """
        self._ensure_user_exists(user_id)
        wallet = self.get_or_create_wallet(user_id)
        return to_user_wallet_response(wallet)

    def page_wallet_ledgers(
        self,
        user_id: str,
        page_num: int,
        page_size: int,
    ) -> PageResponse[WalletLedgerResponse]:
        """
        分页查询用户钱包流水（按创建时间降序）。

        :param user_id: 用户主键。
        :param page_num: 页码，从 1 开始。
        :param page_size: 每页条数，最大 100。
        :return: 分页流水响应。
        :raises NotFoundException: 用户不存在。
        """
        self._ensure_user_exists(user_id)
        total = self._ledgers.count_ledgers_by_user(user_id)
        rows = self._ledgers.page_ledgers_by_user(user_id, page_num, page_size)
        items = [to_wallet_ledger_response(row) for row in rows]
        return PageResponse(
            pageNum=page_num,
            pageSize=page_size,
            total=total,
            items=items,
        )

    def _ensure_user_exists(self, user_id: str) -> None:
        """
        校验用户是否存在。

        :param user_id: 用户主键。
        :raises NotFoundException: 用户不存在。
        """
        if self._accounts.get_by_server_id(user_id, active_only=True) is None:
            raise NotFoundException("用户不存在")

    def _normalize_change_type(self, raw: str) -> str:
        """
        规范化变动类型。

        :param raw: 原始类型字符串。
        :return: ``gain`` / ``cost`` / ``refund``。
        """
        normalized = _CHANGE_ALIASES.get(raw.strip().lower())
        if normalized is None:
            raise ValidationException(f"不支持的 change_type: {raw}")
        return normalized

    def _ledger_balance_delta(self, row: WalletLedger) -> int:
        """单条流水对可用余额的贡献。"""
        change_type = row.change_type.strip().lower()
        if change_type in (_CHANGE_GAIN, _CHANGE_REFUND):
            return row.amount
        if change_type == _CHANGE_COST:
            return -row.amount
        if row.amount < 0:
            return row.amount
        return row.amount
