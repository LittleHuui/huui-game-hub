"""用户域单实体服务。"""

from typing import Any, Dict, List, Optional

from app.core.database import new_entity_ids
from app.core.exceptions import NotFoundException, ValidationException
from app.core.time_utils import now_ms
from app.modules.user.json_schemas import UserSystemSettingJson, default_user_system_setting_json
from app.modules.user.models import UserAccount, UserDevice, UserGameSetting, UserSystemSetting
from app.modules.user.repository import (
    UserAccountRepository,
    UserDeviceRepository,
    UserGameSettingRepository,
    UserSystemSettingRepository,
)
from app.modules.user.schemas import encode_setting_json, encode_user_system_setting_json


def _stable_system_setting_client_id(user_id: str) -> str:
    """
    为 ``user_id`` 生成稳定且全局唯一的系统设置幂等 client_id。

    :param user_id: 用户 ``server_id``。
    :return: 合成 client_id 字符串。
    """
    return f"uss|{user_id}"


def _stable_game_setting_client_id(user_id: str, game_code: str) -> str:
    """
    为 ``(user_id, game_code)`` 生成稳定且全局唯一的幂等 client_id。

    :param user_id: 用户 ``server_id``。
    :param game_code: 游戏编码。
    :return: 合成 client_id 字符串。
    """
    return f"ugs|{user_id}|{game_code}"


class UserAccountEntityService:
    """用户账号实体的基础校验与 CRUD。"""

    def __init__(self, repository: UserAccountRepository) -> None:
        self._repository = repository

    def get_by_server_id(self, server_id: str, *, active_only: bool = True) -> Optional[UserAccount]:
        """按主键读取账号。"""
        return self._repository.get_by_server_id(server_id, active_only=active_only)

    def get_by_username(self, username: str, *, active_only: bool = True) -> Optional[UserAccount]:
        """按用户名读取账号。"""
        return self._repository.get_by_username(username, active_only=active_only)

    def get_by_client_id(self, client_id: str, *, active_only: bool = True) -> Optional[UserAccount]:
        """按客户端幂等 ID 读取账号。"""
        return self._repository.get_by_client_id(client_id, active_only=active_only)

    def list_active(self) -> List[UserAccount]:
        """列出全部未删除账号。"""
        return self._repository.list_active()

    def create_account(
        self,
        client_id: str,
        username: str,
        nickname: str,
        avatar: Optional[str],
    ) -> UserAccount:
        """创建账号并校验唯一性。"""
        if self._repository.get_by_client_id(client_id) is not None:
            raise ValidationException("client_id 已存在")
        if self._repository.get_by_username(username) is not None:
            raise ValidationException("username 已存在")
        server_id, created_at, updated_at = new_entity_ids("user")
        entity = UserAccount(
            server_id=server_id,
            client_id=client_id,
            username=username,
            nickname=nickname,
            avatar=avatar,
            status="normal",
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity)

    def update_nickname(self, server_id: str, nickname: str) -> UserAccount:
        """更新昵称。"""
        entity = self._repository.get_by_server_id(server_id)
        if entity is None:
            raise NotFoundException("用户不存在")
        entity.nickname = nickname
        return self._repository.save(entity)

    def save(self, entity: UserAccount) -> UserAccount:
        """
        持久化账号变更。

        :param entity: 账号实体。
        :return: 持久化后的账号。
        """
        return self._repository.save(entity)

    def soft_delete(self, server_id: str) -> UserAccount:
        """软删除账号。"""
        entity = self._repository.get_by_server_id(server_id)
        if entity is None:
            raise NotFoundException("用户不存在")
        return self._repository.soft_delete(entity)


class UserDeviceEntityService:
    """用户设备实体的基础校验与 CRUD。"""

    def __init__(self, repository: UserDeviceRepository) -> None:
        self._repository = repository

    def get_by_server_id(self, server_id: str, *, active_only: bool = True) -> Optional[UserDevice]:
        """按服务端主键读取设备。"""
        return self._repository.get_by_server_id(server_id, active_only=active_only)

    def get_by_client_id(self, client_id: str, *, active_only: bool = True) -> Optional[UserDevice]:
        """按客户端幂等 ID 读取设备。"""
        return self._repository.get_by_client_id(client_id, active_only=active_only)

    def get_by_user_id_and_device_id(
        self,
        user_id: str,
        device_id: str,
        *,
        active_only: bool = True,
    ) -> Optional[UserDevice]:
        """按用户与设备 ID 读取。"""
        return self._repository.get_by_user_id_and_device_id(user_id, device_id, active_only=active_only)

    def list_by_user_id(self, user_id: str, *, active_only: bool = True) -> List[UserDevice]:
        """列出用户设备。"""
        return self._repository.list_by_user_id(user_id, active_only=active_only)

    def bind_or_update_device(
        self,
        user_id: str,
        client_id: str,
        device_id: str,
        device_name: Optional[str],
        device_type: Optional[str],
    ) -> UserDevice:
        """
        绑定或更新设备：同一 ``user_id + device_id`` 做更新并刷新最近登录时间；
        若曾软删则恢复。

        :param user_id: 用户 ``server_id``。
        :param client_id: 本条设备记录的幂等 client_id。
        :param device_id: 前端设备 ID。
        :param device_name: 可选展示名。
        :param device_type: 可选设备类型。
        :return: 持久化后的 ``UserDevice``。
        """
        now = now_ms()
        existing = self._repository.get_by_user_id_and_device_id(user_id, device_id, active_only=False)
        if existing is not None:
            conflict = self._repository.get_by_client_id(
                client_id,
                active_only=True,
                exclude_server_id=existing.server_id,
            )
            if conflict is not None:
                raise ValidationException("client_id 已被其他设备占用")
            existing.client_id = client_id
            existing.device_name = device_name
            existing.device_type = device_type
            existing.last_login_at = now
            if existing.deleted_at is not None:
                existing.deleted_at = None
            return self._repository.save(existing)
        if self._repository.get_by_client_id(client_id) is not None:
            raise ValidationException("client_id 已存在")
        server_id, created_at, updated_at = new_entity_ids("user_device")
        entity = UserDevice(
            server_id=server_id,
            client_id=client_id,
            user_id=user_id,
            device_id=device_id,
            device_name=device_name,
            device_type=device_type,
            last_login_at=now,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity)

    def soft_delete(self, server_id: str) -> UserDevice:
        """按主键软删除设备。"""
        entity = self._repository.get_by_server_id(server_id)
        if entity is None:
            raise NotFoundException("设备不存在")
        return self._repository.soft_delete(entity)


class UserGameSettingEntityService:
    """用户游戏设置实体的基础校验与 CRUD。"""

    def __init__(self, repository: UserGameSettingRepository) -> None:
        self._repository = repository

    def get_by_server_id(self, server_id: str, *, active_only: bool = True) -> Optional[UserGameSetting]:
        """按主键读取游戏设置。"""
        return self._repository.get_by_server_id(server_id, active_only=active_only)

    def get_by_user_id_and_game_code(
        self,
        user_id: str,
        game_code: str,
        *,
        active_only: bool = True,
    ) -> Optional[UserGameSetting]:
        """按用户与游戏读取设置。"""
        return self._repository.get_by_user_id_and_game_code(user_id, game_code, active_only=active_only)

    def list_by_user_id(self, user_id: str, *, active_only: bool = True) -> List[UserGameSetting]:
        """列出用户全部游戏设置。"""
        return self._repository.list_by_user_id(user_id, active_only=active_only)

    def get_or_create(self, user_id: str, game_code: str) -> UserGameSetting:
        """
        获取或创建默认游戏设置行（幂等 client_id 由 ``user_id + game_code`` 推导）。

        :param user_id: 用户 ``server_id``。
        :param game_code: 游戏编码。
        :return: 持久化后的 ``UserGameSetting``。
        """
        active = self._repository.get_by_user_id_and_game_code(user_id, game_code, active_only=True)
        if active is not None:
            return active
        tomb = self._repository.get_by_user_id_and_game_code(user_id, game_code, active_only=False)
        if tomb is not None and tomb.deleted_at is not None:
            tomb.deleted_at = None
            return self._repository.save(tomb)
        client_id = _stable_game_setting_client_id(user_id, game_code)
        if self._repository.get_by_client_id(client_id) is not None:
            raise ValidationException("游戏设置幂等键冲突，请检查数据")
        server_id, created_at, updated_at = new_entity_ids("user_game_setting")
        entity = UserGameSetting(
            server_id=server_id,
            client_id=client_id,
            user_id=user_id,
            game_code=game_code,
            setting_json=None,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity)

    def update_setting_json(
        self,
        user_id: str,
        game_code: str,
        setting: Optional[Dict[str, Any]],
    ) -> UserGameSetting:
        """
        整体覆盖 ``setting_json``（先保证行存在）。

        :param user_id: 用户 ``server_id``。
        :param game_code: 游戏编码。
        :param setting: 设置字典，可为空表示清空。
        :return: 更新后的 ``UserGameSetting``。
        """
        entity = self.get_or_create(user_id, game_code)
        entity.setting_json = encode_setting_json(setting)
        return self._repository.save(entity)

    def save(self, entity: UserGameSetting) -> UserGameSetting:
        """
        持久化游戏设置变更。

        :param entity: 游戏设置实体。
        :return: 持久化后的实体。
        """
        return self._repository.save(entity)

    def soft_delete(self, server_id: str) -> UserGameSetting:
        """按主键软删除游戏设置。"""
        entity = self._repository.get_by_server_id(server_id)
        if entity is None:
            raise NotFoundException("游戏设置不存在")
        return self._repository.soft_delete(entity)


class UserSystemSettingEntityService:
    """用户系统设置实体的基础校验与 CRUD。"""

    def __init__(self, repository: UserSystemSettingRepository) -> None:
        self._repository = repository

    def get_by_server_id(self, server_id: str, *, active_only: bool = True) -> Optional[UserSystemSetting]:
        """按主键读取系统设置。"""
        return self._repository.get_by_server_id(server_id, active_only=active_only)

    def get_by_user_id(self, user_id: str, *, active_only: bool = True) -> Optional[UserSystemSetting]:
        """按用户读取系统设置。"""
        return self._repository.get_by_user_id(user_id, active_only=active_only)

    def create_if_not_exists(self, user_id: str) -> UserSystemSetting:
        """
        若用户尚无系统设置则创建默认行；若曾软删则恢复。

        :param user_id: 用户 ``server_id``。
        :return: 持久化后的 ``UserSystemSetting``。
        """
        active = self._repository.get_by_user_id(user_id, active_only=True)
        if active is not None:
            return active
        tomb = self._repository.get_by_user_id(user_id, active_only=False)
        if tomb is not None and tomb.deleted_at is not None:
            tomb.deleted_at = None
            return self._repository.save(tomb)
        client_id = _stable_system_setting_client_id(user_id)
        if self._repository.get_by_client_id(client_id) is not None:
            raise ValidationException("系统设置幂等键冲突，请检查数据")
        default_setting = default_user_system_setting_json()
        server_id, created_at, updated_at = new_entity_ids("user_system_setting")
        entity = UserSystemSetting(
            server_id=server_id,
            client_id=client_id,
            user_id=user_id,
            setting_json=encode_user_system_setting_json(default_setting),
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity)

    def update_setting(self, user_id: str, setting: UserSystemSettingJson) -> UserSystemSetting:
        """
        整体覆盖 ``setting_json``（先保证行存在）。

        :param user_id: 用户 ``server_id``。
        :param setting: 系统设置 JSON 对象。
        :return: 更新后的 ``UserSystemSetting``。
        """
        entity = self.create_if_not_exists(user_id)
        entity.setting_json = encode_user_system_setting_json(setting)
        return self._repository.save(entity)

    def save(self, entity: UserSystemSetting) -> UserSystemSetting:
        """
        持久化系统设置变更。

        :param entity: 系统设置实体。
        :return: 持久化后的实体。
        """
        return self._repository.save(entity)

    def soft_delete(self, server_id: str) -> UserSystemSetting:
        """按主键软删除系统设置。"""
        entity = self._repository.get_by_server_id(server_id)
        if entity is None:
            raise NotFoundException("系统设置不存在")
        return self._repository.soft_delete(entity)
