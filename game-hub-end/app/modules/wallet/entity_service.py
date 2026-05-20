"""钱包域单实体服务。"""

from typing import List, Optional, Tuple

from app.core.database import new_entity_ids
from app.core.time_utils import now_ms
from app.common.exceptions import ValidationException
from app.modules.wallet.models import UserWallet, WalletLedger
from app.modules.wallet.repository import UserWalletRepository, WalletLedgerRepository


class UserWalletEntityService:
    """用户钱包实体：查询、创建、余额覆盖。"""

    def __init__(self, repository: UserWalletRepository) -> None:
        self._repository = repository

    def get_wallet_by_user_id(self, user_id: str, *, active_only: bool = True) -> Optional[UserWallet]:
        """
        按用户 ID 读取钱包。

        :param user_id: 用户主键。
        :param active_only: 是否只查未软删行。
        :return: 钱包实体或 ``None``。
        """
        return self._repository.get_by_user_id(user_id, active_only=active_only)

    def create_wallet_for_user(self, user_id: str) -> UserWallet:
        """
        为用户新建空钱包。

        :param user_id: 用户主键。
        :return: 新钱包。
        :raises ValidationException: 该用户已有钱包。
        """
        if self._repository.get_by_user_id(user_id) is not None:
            raise ValidationException("用户钱包已存在")
        server_id, created_at, updated_at = new_entity_ids("user_wallet")
        entity = UserWallet(
            server_id=server_id,
            user_id=user_id,
            balance=0,
            total_earned=0,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity)

    def update_wallet_balance(self, wallet: UserWallet, balance: int, total_earned: int) -> UserWallet:
        """
        覆盖写入可用余额与累计获得积分。

        :param wallet: 已加载的钱包实体。
        :param balance: 新余额。
        :param total_earned: 新累计获得。
        :return: 持久化后的钱包。
        """
        wallet.balance = balance
        wallet.total_earned = total_earned
        return self._repository.save(wallet)


class WalletLedgerEntityService:
    """钱包流水实体：幂等写入与列表。"""

    def __init__(self, repository: WalletLedgerRepository) -> None:
        self._repository = repository

    def create_ledger_if_not_exists(
        self,
        *,
        client_id: str,
        user_id: str,
        device_id: Optional[str],
        game_code: Optional[str],
        change_type: str,
        reason: str,
        amount: int,
        balance_after: Optional[int],
        payload_json: Optional[str],
    ) -> Tuple[WalletLedger, bool]:
        """
        按 ``user_id + client_id`` 幂等写入流水；已存在未删行则返回既有记录。

        若唯一键被软删行占用，则复活该行并更新字段。

        :param client_id: 客户端幂等 ID。
        :param user_id: 用户主键。
        :param device_id: 设备 ID，可空。
        :param game_code: 游戏编码，可空。
        :param change_type: ``gain`` / ``cost`` 等。
        :param reason: 业务原因。
        :param amount: 变动数量（与 ``change_type`` 约定一致，参见模块服务）。
        :param balance_after: 变动后的余额快照，可空。
        :param payload_json: 附加 JSON 文本，可空。
        :return: ``(流水, 是否新产生可记账副作用)``；已存在未删行时第二项为 ``False``。
        """
        active = self._repository.get_by_user_and_client_id(user_id, client_id, active_only=True)
        if active is not None:
            return active, False
        tomb = self._repository.get_any_by_user_and_client_id(user_id, client_id)
        if tomb is not None and tomb.deleted_at is not None:
            tomb.deleted_at = None
            tomb.client_id = client_id
            tomb.user_id = user_id
            tomb.device_id = device_id
            tomb.game_code = game_code
            tomb.change_type = change_type
            tomb.reason = reason
            tomb.amount = amount
            tomb.balance_after = balance_after
            tomb.payload_json = payload_json
            tomb.synced_at = now_ms()
            return self._repository.save(tomb), True
        synced_at = now_ms()
        server_id, created_at, updated_at = new_entity_ids("wallet_ledger")
        entity = WalletLedger(
            server_id=server_id,
            client_id=client_id,
            user_id=user_id,
            device_id=device_id,
            game_code=game_code,
            change_type=change_type,
            reason=reason,
            amount=amount,
            balance_after=balance_after,
            payload_json=payload_json,
            synced_at=synced_at,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity), True

    def list_ledgers_by_user(self, user_id: str, *, active_only: bool = True) -> List[WalletLedger]:
        """
        列出某用户的流水。

        :param user_id: 用户主键。
        :param active_only: 是否只含未软删。
        :return: 按创建时间升序的流水列表。
        """
        return self._repository.list_by_user_id(user_id, active_only=active_only)

    def count_ledgers_by_user(self, user_id: str, *, active_only: bool = True) -> int:
        """
        统计某用户流水条数。

        :param user_id: 用户主键。
        :param active_only: 是否只统计未软删行。
        :return: 记录总数。
        """
        return self._repository.count_by_user_id(user_id, active_only=active_only)

    def page_ledgers_by_user(
        self,
        user_id: str,
        page_num: int,
        page_size: int,
        *,
        active_only: bool = True,
    ) -> List[WalletLedger]:
        """
        分页查询某用户流水（按创建时间降序）。

        :param user_id: 用户主键。
        :param page_num: 页码，从 1 开始。
        :param page_size: 每页条数。
        :param active_only: 是否只含未软删。
        :return: 当前页流水列表。
        """
        return self._repository.page_by_user_id(
            user_id,
            page_num,
            page_size,
            active_only=active_only,
        )

    def get_by_user_and_client_id(self, user_id: str, client_id: str) -> Optional[WalletLedger]:
        """
        按幂等键读取流水。

        :param user_id: 用户主键。
        :param client_id: 客户端幂等 ID。
        :return: 流水实体或 ``None``。
        """
        return self._repository.get_by_user_and_client_id(user_id, client_id, active_only=True)
