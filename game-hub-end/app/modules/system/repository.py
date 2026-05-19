"""系统域数据访问。"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time_utils import now_ms
from app.modules.system.models import LoginLog, RequestLog, SystemConfig


class SystemConfigRepository:
    """``system_config`` 表 CRUD。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_server_id(self, server_id: str, *, active_only: bool = True) -> Optional[SystemConfig]:
        """按主键查询配置。"""
        stmt = select(SystemConfig).where(SystemConfig.server_id == server_id)
        if active_only:
            stmt = stmt.where(SystemConfig.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def get_by_config_key(self, config_key: str, *, active_only: bool = True) -> Optional[SystemConfig]:
        """按配置键查询。"""
        stmt = select(SystemConfig).where(SystemConfig.config_key == config_key)
        if active_only:
            stmt = stmt.where(SystemConfig.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def get_any_by_config_key(self, config_key: str) -> Optional[SystemConfig]:
        """按配置键查询（含软删），用于复活占用唯一键的旧行。"""
        stmt = select(SystemConfig).where(SystemConfig.config_key == config_key)
        return self._session.scalar(stmt)

    def list_all(self, *, active_only: bool = True) -> List[SystemConfig]:
        """列出全部配置，按 config_key 升序。"""
        stmt = select(SystemConfig)
        if active_only:
            stmt = stmt.where(SystemConfig.deleted_at.is_(None))
        stmt = stmt.order_by(SystemConfig.config_key.asc())
        return list(self._session.scalars(stmt).all())

    def add(self, entity: SystemConfig) -> SystemConfig:
        """插入配置。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: SystemConfig) -> SystemConfig:
        """持久化配置变更。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def soft_delete(self, entity: SystemConfig) -> SystemConfig:
        """软删除配置。"""
        entity.deleted_at = now_ms()
        return self.save(entity)


class RequestLogRepository:
    """``request_log`` 表 CRUD。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_server_id(self, server_id: str, *, active_only: bool = True) -> Optional[RequestLog]:
        """按主键查询请求日志。"""
        stmt = select(RequestLog).where(RequestLog.server_id == server_id)
        if active_only:
            stmt = stmt.where(RequestLog.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def add(self, entity: RequestLog) -> RequestLog:
        """插入请求日志。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: RequestLog) -> RequestLog:
        """持久化请求日志变更。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def soft_delete(self, entity: RequestLog) -> RequestLog:
        """软删除请求日志。"""
        entity.deleted_at = now_ms()
        return self.save(entity)


class LoginLogRepository:
    """``login_log`` 表 CRUD。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_server_id(self, server_id: str, *, active_only: bool = True) -> Optional[LoginLog]:
        """按主键查询登录日志。"""
        stmt = select(LoginLog).where(LoginLog.server_id == server_id)
        if active_only:
            stmt = stmt.where(LoginLog.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def add(self, entity: LoginLog) -> LoginLog:
        """插入登录日志。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: LoginLog) -> LoginLog:
        """持久化登录日志变更。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def soft_delete(self, entity: LoginLog) -> LoginLog:
        """软删除登录日志。"""
        entity.deleted_at = now_ms()
        return self.save(entity)

