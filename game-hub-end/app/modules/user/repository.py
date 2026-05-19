"""用户域数据访问。"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time_utils import now_ms
from app.modules.user.models import UserAccount, UserDevice, UserGameSetting, UserSystemSetting


class UserAccountRepository:
    """``user_account`` 表查询与持久化。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_server_id(self, server_id: str, *, active_only: bool = True) -> Optional[UserAccount]:
        """按服务端主键查询账号。"""
        stmt = select(UserAccount).where(UserAccount.server_id == server_id)
        if active_only:
            stmt = stmt.where(UserAccount.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def get_by_client_id(self, client_id: str, *, active_only: bool = True) -> Optional[UserAccount]:
        """按客户端幂等 ID 查询账号。"""
        stmt = select(UserAccount).where(UserAccount.client_id == client_id)
        if active_only:
            stmt = stmt.where(UserAccount.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def get_by_username(self, username: str, *, active_only: bool = True) -> Optional[UserAccount]:
        """按用户名查询账号。"""
        stmt = select(UserAccount).where(UserAccount.username == username)
        if active_only:
            stmt = stmt.where(UserAccount.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def list_active(self) -> List[UserAccount]:
        """列出未软删的全部账号（管理或测试用）。"""
        stmt = select(UserAccount).where(UserAccount.deleted_at.is_(None)).order_by(UserAccount.created_at.asc())
        return list(self._session.scalars(stmt).all())

    def add(self, entity: UserAccount) -> UserAccount:
        """插入账号记录。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: UserAccount) -> UserAccount:
        """持久化已跟踪账号变更。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def soft_delete(self, entity: UserAccount) -> UserAccount:
        """软删除账号。"""
        entity.deleted_at = now_ms()
        return self.save(entity)


class UserDeviceRepository:
    """``user_device`` 表查询与持久化。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_server_id(self, server_id: str, *, active_only: bool = True) -> Optional[UserDevice]:
        """按服务端主键查询设备。"""
        stmt = select(UserDevice).where(UserDevice.server_id == server_id)
        if active_only:
            stmt = stmt.where(UserDevice.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def get_by_client_id(
        self,
        client_id: str,
        *,
        active_only: bool = True,
        exclude_server_id: Optional[str] = None,
    ) -> Optional[UserDevice]:
        """按客户端幂等 ID 查询设备。"""
        stmt = select(UserDevice).where(UserDevice.client_id == client_id)
        if active_only:
            stmt = stmt.where(UserDevice.deleted_at.is_(None))
        if exclude_server_id is not None:
            stmt = stmt.where(UserDevice.server_id != exclude_server_id)
        return self._session.scalar(stmt)

    def get_by_user_id_and_device_id(
        self,
        user_id: str,
        device_id: str,
        *,
        active_only: bool = True,
    ) -> Optional[UserDevice]:
        """按用户与设备业务 ID 查询。"""
        stmt = select(UserDevice).where(
            UserDevice.user_id == user_id,
            UserDevice.device_id == device_id,
        )
        if active_only:
            stmt = stmt.where(UserDevice.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def list_by_user_id(self, user_id: str, *, active_only: bool = True) -> List[UserDevice]:
        """按用户列出设备。"""
        stmt = select(UserDevice).where(UserDevice.user_id == user_id)
        if active_only:
            stmt = stmt.where(UserDevice.deleted_at.is_(None))
        stmt = stmt.order_by(UserDevice.created_at.asc())
        return list(self._session.scalars(stmt).all())

    def add(self, entity: UserDevice) -> UserDevice:
        """插入设备记录。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: UserDevice) -> UserDevice:
        """持久化设备变更。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def soft_delete(self, entity: UserDevice) -> UserDevice:
        """软删除设备。"""
        entity.deleted_at = now_ms()
        return self.save(entity)


class UserGameSettingRepository:
    """``user_game_setting`` 表查询与持久化。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_server_id(self, server_id: str, *, active_only: bool = True) -> Optional[UserGameSetting]:
        """按服务端主键查询游戏设置。"""
        stmt = select(UserGameSetting).where(UserGameSetting.server_id == server_id)
        if active_only:
            stmt = stmt.where(UserGameSetting.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def get_by_client_id(
        self,
        client_id: str,
        *,
        active_only: bool = True,
        exclude_server_id: Optional[str] = None,
    ) -> Optional[UserGameSetting]:
        """按客户端幂等 ID 查询游戏设置。"""
        stmt = select(UserGameSetting).where(UserGameSetting.client_id == client_id)
        if active_only:
            stmt = stmt.where(UserGameSetting.deleted_at.is_(None))
        if exclude_server_id is not None:
            stmt = stmt.where(UserGameSetting.server_id != exclude_server_id)
        return self._session.scalar(stmt)

    def get_by_user_id_and_game_code(
        self,
        user_id: str,
        game_code: str,
        *,
        active_only: bool = True,
    ) -> Optional[UserGameSetting]:
        """按用户与游戏编码查询设置。"""
        stmt = select(UserGameSetting).where(
            UserGameSetting.user_id == user_id,
            UserGameSetting.game_code == game_code,
        )
        if active_only:
            stmt = stmt.where(UserGameSetting.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def list_by_user_id(self, user_id: str, *, active_only: bool = True) -> List[UserGameSetting]:
        """列出某用户的全部游戏设置。"""
        stmt = select(UserGameSetting).where(UserGameSetting.user_id == user_id)
        if active_only:
            stmt = stmt.where(UserGameSetting.deleted_at.is_(None))
        stmt = stmt.order_by(UserGameSetting.created_at.asc())
        return list(self._session.scalars(stmt).all())

    def add(self, entity: UserGameSetting) -> UserGameSetting:
        """插入游戏设置记录。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: UserGameSetting) -> UserGameSetting:
        """持久化游戏设置变更。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def soft_delete(self, entity: UserGameSetting) -> UserGameSetting:
        """软删除游戏设置。"""
        entity.deleted_at = now_ms()
        return self.save(entity)


class UserSystemSettingRepository:
    """``user_system_setting`` 表查询与持久化。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_server_id(self, server_id: str, *, active_only: bool = True) -> Optional[UserSystemSetting]:
        """按服务端主键查询系统设置。"""
        stmt = select(UserSystemSetting).where(UserSystemSetting.server_id == server_id)
        if active_only:
            stmt = stmt.where(UserSystemSetting.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def get_by_client_id(
        self,
        client_id: str,
        *,
        active_only: bool = True,
        exclude_server_id: Optional[str] = None,
    ) -> Optional[UserSystemSetting]:
        """按客户端幂等 ID 查询系统设置。"""
        stmt = select(UserSystemSetting).where(UserSystemSetting.client_id == client_id)
        if active_only:
            stmt = stmt.where(UserSystemSetting.deleted_at.is_(None))
        if exclude_server_id is not None:
            stmt = stmt.where(UserSystemSetting.server_id != exclude_server_id)
        return self._session.scalar(stmt)

    def get_by_user_id(self, user_id: str, *, active_only: bool = True) -> Optional[UserSystemSetting]:
        """按用户查询系统设置。"""
        stmt = select(UserSystemSetting).where(UserSystemSetting.user_id == user_id)
        if active_only:
            stmt = stmt.where(UserSystemSetting.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def add(self, entity: UserSystemSetting) -> UserSystemSetting:
        """插入系统设置记录。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: UserSystemSetting) -> UserSystemSetting:
        """持久化系统设置变更。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def soft_delete(self, entity: UserSystemSetting) -> UserSystemSetting:
        """软删除系统设置。"""
        entity.deleted_at = now_ms()
        return self.save(entity)
