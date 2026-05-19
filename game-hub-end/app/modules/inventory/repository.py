"""背包域数据访问。"""

from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.time_utils import now_ms
from app.modules.inventory.models import PropUsageRecord, UserPropBag


class UserPropBagRepository:
    """``user_prop_bag`` 表 CRUD。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_user_game_prop(
        self,
        user_id: str,
        game_code: str,
        prop_code: str,
        *,
        active_only: bool = True,
    ) -> Optional[UserPropBag]:
        """按用户、游戏、道具查询背包行。"""
        stmt = select(UserPropBag).where(
            UserPropBag.user_id == user_id,
            UserPropBag.game_code == game_code,
            UserPropBag.prop_code == prop_code,
        )
        if active_only:
            stmt = stmt.where(UserPropBag.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def list_by_user(self, user_id: str, *, game_code: Optional[str] = None, active_only: bool = True) -> List[UserPropBag]:
        """列出用户背包（可按游戏过滤）。"""
        stmt = select(UserPropBag).where(UserPropBag.user_id == user_id)
        if game_code is not None:
            stmt = stmt.where(UserPropBag.game_code == game_code)
        if active_only:
            stmt = stmt.where(UserPropBag.deleted_at.is_(None))
        stmt = stmt.order_by(UserPropBag.game_code.asc(), UserPropBag.prop_code.asc())
        return list(self._session.scalars(stmt).all())

    def add(self, entity: UserPropBag) -> UserPropBag:
        """插入背包行。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: UserPropBag) -> UserPropBag:
        """持久化背包行变更。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def soft_delete(self, entity: UserPropBag) -> UserPropBag:
        """软删除背包行。"""
        entity.deleted_at = now_ms()
        return self.save(entity)


class PropUsageRecordRepository:
    """``prop_usage_record`` 表 CRUD。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_user_and_client_id(
        self,
        user_id: str,
        client_id: str,
        *,
        active_only: bool = True,
    ) -> Optional[PropUsageRecord]:
        """按用户与客户端幂等键查询使用记录。"""
        stmt = select(PropUsageRecord).where(
            PropUsageRecord.user_id == user_id,
            PropUsageRecord.client_id == client_id,
        )
        if active_only:
            stmt = stmt.where(PropUsageRecord.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def list_by_user(self, user_id: str, *, active_only: bool = True) -> List[PropUsageRecord]:
        """按创建时间升序列出用户使用记录。"""
        stmt = select(PropUsageRecord).where(PropUsageRecord.user_id == user_id)
        if active_only:
            stmt = stmt.where(PropUsageRecord.deleted_at.is_(None))
        stmt = stmt.order_by(PropUsageRecord.created_at.asc())
        return list(self._session.scalars(stmt).all())

    def count_by_user(
        self,
        user_id: str,
        *,
        game_code: Optional[str] = None,
        prop_code: Optional[str] = None,
        active_only: bool = True,
    ) -> int:
        """
        统计用户使用记录条数。

        :param user_id: 用户主键。
        :param game_code: 可选游戏过滤。
        :param prop_code: 可选道具过滤。
        :param active_only: 是否仅统计未软删记录。
        :return: 符合条件的总条数。
        """
        stmt = select(func.count()).select_from(PropUsageRecord).where(PropUsageRecord.user_id == user_id)
        if game_code is not None:
            stmt = stmt.where(PropUsageRecord.game_code == game_code)
        if prop_code is not None:
            stmt = stmt.where(PropUsageRecord.prop_code == prop_code)
        if active_only:
            stmt = stmt.where(PropUsageRecord.deleted_at.is_(None))
        total = self._session.scalar(stmt)
        return int(total or 0)

    def list_by_user_paged(
        self,
        user_id: str,
        *,
        game_code: Optional[str] = None,
        prop_code: Optional[str] = None,
        page_num: int,
        page_size: int,
        active_only: bool = True,
    ) -> List[PropUsageRecord]:
        """
        分页列出用户使用记录（按创建时间倒序）。

        :param user_id: 用户主键。
        :param game_code: 可选游戏过滤。
        :param prop_code: 可选道具过滤。
        :param page_num: 页码，从 1 开始。
        :param page_size: 每页条数。
        :param active_only: 是否仅查询未软删记录。
        :return: 当前页使用记录列表。
        """
        stmt = select(PropUsageRecord).where(PropUsageRecord.user_id == user_id)
        if game_code is not None:
            stmt = stmt.where(PropUsageRecord.game_code == game_code)
        if prop_code is not None:
            stmt = stmt.where(PropUsageRecord.prop_code == prop_code)
        if active_only:
            stmt = stmt.where(PropUsageRecord.deleted_at.is_(None))
        offset = (page_num - 1) * page_size
        stmt = stmt.order_by(PropUsageRecord.created_at.desc()).offset(offset).limit(page_size)
        return list(self._session.scalars(stmt).all())

    def add(self, entity: PropUsageRecord) -> PropUsageRecord:
        """插入使用记录。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: PropUsageRecord) -> PropUsageRecord:
        """持久化使用记录变更。"""
        self._session.add(entity)
        self._session.flush()
        return entity
