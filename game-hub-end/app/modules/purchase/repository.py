"""购买域数据访问。"""

from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.purchase.models import PropPurchaseRecord


class PropPurchaseRecordRepository:
    """``prop_purchase_record`` 表 CRUD。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_user_and_client_id(
        self,
        user_id: str,
        client_id: str,
        *,
        active_only: bool = True,
    ) -> Optional[PropPurchaseRecord]:
        """按用户与客户端幂等键查询购买记录。"""
        stmt = select(PropPurchaseRecord).where(
            PropPurchaseRecord.user_id == user_id,
            PropPurchaseRecord.client_id == client_id,
        )
        if active_only:
            stmt = stmt.where(PropPurchaseRecord.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def list_by_user(self, user_id: str, *, active_only: bool = True) -> List[PropPurchaseRecord]:
        """按更新时间倒序列出用户购买记录。"""
        stmt = select(PropPurchaseRecord).where(PropPurchaseRecord.user_id == user_id)
        if active_only:
            stmt = stmt.where(PropPurchaseRecord.deleted_at.is_(None))
        stmt = stmt.order_by(
            PropPurchaseRecord.updated_at.desc(),
            PropPurchaseRecord.created_at.desc(),
        )
        return list(self._session.scalars(stmt).all())

    def page_by_user(
        self,
        user_id: str,
        *,
        game_code: Optional[str] = None,
        prop_code: Optional[str] = None,
        page_num: int = 1,
        page_size: int = 20,
        active_only: bool = True,
    ) -> Tuple[List[PropPurchaseRecord], int]:
        """
        分页查询用户购买记录（按创建时间倒序）。

        :param user_id: 用户主键。
        :param game_code: 可选游戏编码过滤。
        :param prop_code: 可选道具编码过滤。
        :param page_num: 页码，从 1 开始。
        :param page_size: 每页条数。
        :param active_only: 是否排除软删记录。
        :return: 当前页记录列表与总条数。
        """
        filters = [PropPurchaseRecord.user_id == user_id]
        if active_only:
            filters.append(PropPurchaseRecord.deleted_at.is_(None))
        if game_code is not None and game_code.strip():
            filters.append(PropPurchaseRecord.game_code == game_code.strip())
        if prop_code is not None and prop_code.strip():
            filters.append(PropPurchaseRecord.prop_code == prop_code.strip())

        count_stmt = select(func.count(PropPurchaseRecord.server_id)).where(*filters)
        total = int(self._session.scalar(count_stmt) or 0)

        offset = (page_num - 1) * page_size
        list_stmt = (
            select(PropPurchaseRecord)
            .where(*filters)
            .order_by(
                PropPurchaseRecord.updated_at.desc(),
                PropPurchaseRecord.created_at.desc(),
            )
            .offset(offset)
            .limit(page_size)
        )
        items = list(self._session.scalars(list_stmt).all())
        return items, total

    def add(self, entity: PropPurchaseRecord) -> PropPurchaseRecord:
        """插入购买记录。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: PropPurchaseRecord) -> PropPurchaseRecord:
        """持久化购买记录变更。"""
        self._session.add(entity)
        self._session.flush()
        return entity
