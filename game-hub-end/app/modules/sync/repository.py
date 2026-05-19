"""同步域数据访问。"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time_utils import now_ms
from app.modules.sync.models import SyncLog


class SyncLogRepository:
    """``sync_log`` 表 CRUD。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_server_id(self, server_id: str, *, active_only: bool = True) -> Optional[SyncLog]:
        """
        按主键查询同步日志。

        :param server_id: 服务端主键。
        :param active_only: 是否只查未软删行。
        :return: 同步日志或 ``None``。
        """
        stmt = select(SyncLog).where(SyncLog.server_id == server_id)
        if active_only:
            stmt = stmt.where(SyncLog.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def add(self, entity: SyncLog) -> SyncLog:
        """
        插入同步日志。

        :param entity: 待持久化实体。
        :return: 已 flush 的实体。
        """
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: SyncLog) -> SyncLog:
        """
        持久化同步日志变更。

        :param entity: 已加载实体。
        :return: 已 flush 的实体。
        """
        self._session.add(entity)
        self._session.flush()
        return entity

    def soft_delete(self, entity: SyncLog) -> SyncLog:
        """
        软删除同步日志。

        :param entity: 已加载实体。
        :return: 更新后的实体。
        """
        entity.deleted_at = now_ms()
        return self.save(entity)
