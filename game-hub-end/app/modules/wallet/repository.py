"""钱包域数据访问。"""

from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.time_utils import now_ms
from app.modules.wallet.models import UserWallet, WalletLedger


class UserWalletRepository:
    """``user_wallet`` 表 CRUD。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_server_id(self, server_id: str, *, active_only: bool = True) -> Optional[UserWallet]:
        """按主键查询钱包。"""
        stmt = select(UserWallet).where(UserWallet.server_id == server_id)
        if active_only:
            stmt = stmt.where(UserWallet.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def get_by_user_id(self, user_id: str, *, active_only: bool = True) -> Optional[UserWallet]:
        """按用户 ID 查询钱包。"""
        stmt = select(UserWallet).where(UserWallet.user_id == user_id)
        if active_only:
            stmt = stmt.where(UserWallet.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def add(self, entity: UserWallet) -> UserWallet:
        """插入钱包。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: UserWallet) -> UserWallet:
        """持久化钱包变更。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def soft_delete(self, entity: UserWallet) -> UserWallet:
        """软删除钱包。"""
        entity.deleted_at = now_ms()
        return self.save(entity)


class WalletLedgerRepository:
    """``wallet_ledger`` 表 CRUD。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_server_id(self, server_id: str, *, active_only: bool = True) -> Optional[WalletLedger]:
        """按主键查询流水。"""
        stmt = select(WalletLedger).where(WalletLedger.server_id == server_id)
        if active_only:
            stmt = stmt.where(WalletLedger.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def get_by_user_and_client_id(
        self,
        user_id: str,
        client_id: str,
        *,
        active_only: bool = True,
    ) -> Optional[WalletLedger]:
        """按用户与客户端幂等键查询流水。"""
        stmt = select(WalletLedger).where(
            WalletLedger.user_id == user_id,
            WalletLedger.client_id == client_id,
        )
        if active_only:
            stmt = stmt.where(WalletLedger.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def get_any_by_user_and_client_id(self, user_id: str, client_id: str) -> Optional[WalletLedger]:
        """按用户与 client_id 查询流水（含软删），用于复活占用唯一键的旧行。"""
        stmt = select(WalletLedger).where(
            WalletLedger.user_id == user_id,
            WalletLedger.client_id == client_id,
        )
        return self._session.scalar(stmt)

    def list_by_user_id(self, user_id: str, *, active_only: bool = True) -> List[WalletLedger]:
        """按创建时间升序列出流水。"""
        stmt = select(WalletLedger).where(WalletLedger.user_id == user_id)
        if active_only:
            stmt = stmt.where(WalletLedger.deleted_at.is_(None))
        stmt = stmt.order_by(WalletLedger.created_at.asc())
        return list(self._session.scalars(stmt).all())

    def count_by_user_id(self, user_id: str, *, active_only: bool = True) -> int:
        """
        统计用户流水条数。

        :param user_id: 用户主键。
        :param active_only: 是否只统计未软删行。
        :return: 符合条件的记录数。
        """
        stmt = select(func.count()).select_from(WalletLedger).where(WalletLedger.user_id == user_id)
        if active_only:
            stmt = stmt.where(WalletLedger.deleted_at.is_(None))
        total = self._session.scalar(stmt)
        return int(total or 0)

    def page_by_user_id(
        self,
        user_id: str,
        page_num: int,
        page_size: int,
        *,
        active_only: bool = True,
    ) -> List[WalletLedger]:
        """
        分页查询用户流水（按创建时间降序）。

        :param user_id: 用户主键。
        :param page_num: 页码，从 1 开始。
        :param page_size: 每页条数。
        :param active_only: 是否只查未软删行。
        :return: 当前页流水列表。
        """
        stmt = select(WalletLedger).where(WalletLedger.user_id == user_id)
        if active_only:
            stmt = stmt.where(WalletLedger.deleted_at.is_(None))
        offset = (page_num - 1) * page_size
        stmt = stmt.order_by(WalletLedger.created_at.desc()).offset(offset).limit(page_size)
        return list(self._session.scalars(stmt).all())

    def add(self, entity: WalletLedger) -> WalletLedger:
        """插入流水。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: WalletLedger) -> WalletLedger:
        """持久化流水变更。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def soft_delete(self, entity: WalletLedger) -> WalletLedger:
        """软删除流水。"""
        entity.deleted_at = now_ms()
        return self.save(entity)
