"""用户域模块级编排服务。"""

from typing import Any, Dict, List, Optional

from app.common.exceptions import NotFoundException, ValidationException
from app.modules.user.entity_service import (
    UserAccountEntityService,
    UserDeviceEntityService,
    UserGameSettingEntityService,
    UserSystemSettingEntityService,
)
from app.modules.user.json_schemas import UserSystemSettingJson
from app.modules.user.models import UserAccount, UserDevice, UserGameSetting, UserSystemSetting
from app.modules.user.schemas import (
    UserAccountCreate,
    UserAccountRead,
    UserAccountUpdateNickname,
    UserDetailRead,
    UserDeviceBind,
    UserDeviceRead,
    UserGameSettingRead,
    UserSystemSettingRead,
    decode_setting_json,
    decode_user_system_setting_json,
    encode_setting_json,
    encode_user_system_setting_json,
    user_game_setting_to_read,
    user_system_setting_to_read,
)


class UserModuleService:
    """用户模块对外业务能力。"""

    def __init__(
        self,
        account_entity: UserAccountEntityService,
        device_entity: UserDeviceEntityService,
        game_setting_entity: UserGameSettingEntityService,
        system_setting_entity: UserSystemSettingEntityService,
    ) -> None:
        self._accounts = account_entity
        self._devices = device_entity
        self._game_settings = game_setting_entity
        self._system_settings = system_setting_entity

    def create_user(self, payload: UserAccountCreate) -> UserAccount:
        """创建用户账号。"""
        return self._accounts.create_account(
            client_id=payload.clientId,
            username=payload.username,
            nickname=payload.nickname,
            avatar=payload.avatar,
        )

    def get_user_by_id(self, user_id: str) -> Optional[UserAccount]:
        """
        按 server_id 查询未软删用户。

        :param user_id: 用户主键。
        :return: 用户实体；不存在或已软删时返回 ``None``。
        """
        if user_id is None or not user_id.strip():
            return None
        return self._accounts.get_by_server_id(user_id.strip(), active_only=True)

    def bind_or_update_device_for_boot(self, user_id: str, device_id: str) -> UserDevice:
        """
        启动上下文：按 user_id + device_id 绑定或刷新最近登录时间。

        :param user_id: 用户主键。
        :param device_id: 前端设备 ID。
        :return: 持久化后的设备实体。
        """
        if self._accounts.get_by_server_id(user_id, active_only=True) is None:
            raise NotFoundException("用户不存在")
        client_id = f"boot|{user_id}|{device_id}"
        return self._devices.bind_or_update_device(
            user_id=user_id,
            client_id=client_id,
            device_id=device_id,
            device_name=None,
            device_type=None,
        )

    def get_user_detail(self, user_id: str) -> UserDetailRead:
        """查询用户详情（账号 + 设备列表）。"""
        account = self._accounts.get_by_server_id(user_id)
        if account is None:
            raise NotFoundException("用户不存在")
        devices = self._devices.list_by_user_id(user_id)
        return UserDetailRead(
            user=UserAccountRead.model_validate(account),
            devices=[UserDeviceRead.model_validate(d) for d in devices],
        )

    def update_nickname(self, user_id: str, payload: UserAccountUpdateNickname) -> UserAccount:
        """更新展示昵称。"""
        return self._accounts.update_nickname(user_id, payload.nickname)

    def merge_user_account_from_sync(
        self,
        user_id: str,
        event_updated_at: int,
        payload: Dict[str, Any],
    ) -> UserAccount:
        """
        按 updatedAt 合并同步用户资料（状态类 LWW）。

        仅当 ``event_updated_at`` 严格小于库中事件时间时跳过；同毫秒时允许后写覆盖前写。

        :param user_id: 用户主键。
        :param event_updated_at: 事件更新时间（毫秒）。
        :param payload: 事件载荷。
        :return: 用户账号实体。
        """
        account = self._accounts.get_by_server_id(user_id, active_only=True)
        if account is None:
            raise NotFoundException("用户不存在")
        if event_updated_at < account.updated_at:
            return account
        nickname = payload.get("nickname")
        if nickname is not None and str(nickname).strip():
            account.nickname = str(nickname).strip()
        if "avatar" in payload:
            avatar = payload.get("avatar")
            account.avatar = str(avatar) if avatar else None
        status = payload.get("status")
        if status is not None and str(status).strip():
            account.status = str(status).strip()
        account.updated_at = event_updated_at
        return self._accounts.save(account)

    def merge_user_system_setting_from_sync(
        self,
        user_id: str,
        event_updated_at: int,
        payload: Dict[str, Any],
    ) -> UserSystemSetting:
        """
        按 updatedAt 合并同步用户系统设置（状态类 LWW）。

        ``entity.updated_at`` 存事件时间，由 ``before_flush`` 保留，不得被 flush 时刻覆盖。
        仅当 ``event_updated_at`` 严格小于库中事件时间时跳过；同毫秒时允许后写覆盖前写。

        :param user_id: 用户主键。
        :param event_updated_at: 事件更新时间（毫秒）。
        :param payload: 事件载荷。
        :return: 用户系统设置实体。
        """
        if self._accounts.get_by_server_id(user_id, active_only=True) is None:
            raise NotFoundException("用户不存在")
        setting_patch = payload.get("setting")
        if setting_patch is not None and not isinstance(setting_patch, dict):
            raise ValidationException("setting 必须为对象")

        entity = self._system_settings.get_by_user_id(user_id, active_only=True)
        if entity is None:
            entity = self._system_settings.create_if_not_exists(user_id)
            if isinstance(setting_patch, dict):
                current = decode_user_system_setting_json(entity.setting_json)
                merged = UserSystemSettingJson.model_validate(
                    {**current.model_dump(), **setting_patch},
                )
                entity.setting_json = encode_user_system_setting_json(merged)
                entity.updated_at = event_updated_at
                return self._system_settings.save(entity)
            return entity

        if event_updated_at < entity.updated_at:
            return entity
        if not isinstance(setting_patch, dict):
            return entity

        current = decode_user_system_setting_json(entity.setting_json)
        merged = UserSystemSettingJson.model_validate({**current.model_dump(), **setting_patch})
        entity.setting_json = encode_user_system_setting_json(merged)
        entity.updated_at = event_updated_at
        return self._system_settings.save(entity)

    def merge_user_game_setting_from_sync(
        self,
        user_id: str,
        event_updated_at: int,
        payload: Dict[str, Any],
    ) -> UserGameSetting:
        """
        按 updatedAt 合并同步用户游戏设置（状态类 LWW）。

        仅当 ``event_updated_at`` 严格小于库中事件时间时跳过；同毫秒时允许后写覆盖前写。

        :param user_id: 用户主键。
        :param event_updated_at: 事件更新时间（毫秒）。
        :param payload: 事件载荷。
        :return: 用户游戏设置实体。
        """
        if self._accounts.get_by_server_id(user_id, active_only=True) is None:
            raise NotFoundException("用户不存在")
        game_code = payload.get("gameCode")
        if game_code is None:
            game_code = payload.get("game_code")
        if game_code is None or not str(game_code).strip():
            raise ValidationException("gameCode 不能为空")
        game_code = str(game_code).strip()

        setting_patch = payload.get("setting")
        if setting_patch is not None and not isinstance(setting_patch, dict):
            raise ValidationException("setting 必须为对象")

        entity = self._game_settings.get_by_user_id_and_game_code(user_id, game_code, active_only=True)
        if entity is None:
            entity = self._game_settings.get_or_create(user_id, game_code)
            if isinstance(setting_patch, dict):
                current = decode_setting_json(entity.setting_json) or {}
                merged = {**current, **setting_patch}
                entity.setting_json = encode_setting_json(merged)
                entity.updated_at = event_updated_at
                return self._game_settings.save(entity)
            return entity

        if event_updated_at < entity.updated_at:
            return entity
        if not isinstance(setting_patch, dict):
            return entity

        current = decode_setting_json(entity.setting_json) or {}
        merged = {**current, **setting_patch}
        entity.setting_json = encode_setting_json(merged)
        entity.updated_at = event_updated_at
        return self._game_settings.save(entity)

    def bind_or_update_device(self, user_id: str, payload: UserDeviceBind) -> UserDevice:
        """绑定或更新用户设备。"""
        if self._accounts.get_by_server_id(user_id) is None:
            raise NotFoundException("用户不存在")
        return self._devices.bind_or_update_device(
            user_id=user_id,
            client_id=payload.clientId,
            device_id=payload.deviceId,
            device_name=payload.deviceName,
            device_type=payload.deviceType,
        )

    def get_or_create_user_game_setting(self, user_id: str, game_code: str) -> UserGameSetting:
        """获取或创建用户在指定游戏下的设置行。"""
        if self._accounts.get_by_server_id(user_id) is None:
            raise NotFoundException("用户不存在")
        return self._game_settings.get_or_create(user_id, game_code)

    def update_user_game_setting(
        self,
        user_id: str,
        game_code: str,
        setting: Optional[Dict[str, Any]],
    ) -> UserGameSetting:
        """覆盖写入用户游戏设置 JSON。"""
        if self._accounts.get_by_server_id(user_id) is None:
            raise NotFoundException("用户不存在")
        return self._game_settings.update_setting_json(user_id, game_code, setting)

    def read_user_game_setting(self, user_id: str, game_code: str) -> UserGameSettingRead:
        """读取用户游戏设置（解析 JSON）。"""
        entity = self.get_or_create_user_game_setting(user_id, game_code)
        return user_game_setting_to_read(entity)

    def get_or_create_user_system_setting(self, user_id: str) -> UserSystemSetting:
        """获取或创建用户平台级系统设置行。"""
        if self._accounts.get_by_server_id(user_id) is None:
            raise NotFoundException("用户不存在")
        return self._system_settings.create_if_not_exists(user_id)

    def update_user_system_setting(self, user_id: str, setting: UserSystemSettingJson) -> UserSystemSetting:
        """覆盖写入用户平台级系统设置 JSON。"""
        if self._accounts.get_by_server_id(user_id) is None:
            raise NotFoundException("用户不存在")
        return self._system_settings.update_setting(user_id, setting)

    def read_user_system_setting(self, user_id: str) -> UserSystemSettingRead:
        """读取用户系统设置（解析 JSON）。"""
        entity = self.get_or_create_user_system_setting(user_id)
        return user_system_setting_to_read(entity)

    def list_user_game_settings(self, user_id: str) -> List[UserGameSettingRead]:
        """
        列出用户全部游戏设置（解析 JSON）。

        :param user_id: 用户主键。
        :return: 游戏设置读模型列表。
        """
        if self._accounts.get_by_server_id(user_id) is None:
            raise NotFoundException("用户不存在")
        rows = self._game_settings.list_by_user_id(user_id)
        return [user_game_setting_to_read(row) for row in rows]

    def apply_sync_user_update(
        self,
        *,
        user_id: str,
        event_client_id: str,
        device_id: str,
        payload: Dict[str, Any],
    ) -> None:
        """
        同步用户资料更新：以事件 ``clientId`` 作为设备行幂等键，重复事件不重复写入。

        :param user_id: 用户主键。
        :param event_client_id: 事件 clientId。
        :param device_id: 请求设备 ID。
        :param payload: 事件载荷（支持 nickname / avatar / deviceName / deviceType）。
        :return: None
        """
        if self._accounts.get_by_server_id(user_id) is None:
            raise NotFoundException("用户不存在")
        existing_device = self._devices.get_by_client_id(event_client_id)
        if existing_device is not None:
            if existing_device.user_id != user_id:
                raise ValidationException("clientId 已被其他用户占用")
            return

        nickname = payload.get("nickname")
        if nickname is not None and str(nickname).strip():
            self._accounts.update_nickname(user_id, str(nickname).strip())

        avatar = payload.get("avatar")
        if avatar is not None:
            account = self._accounts.get_by_server_id(user_id)
            if account is not None:
                account.avatar = str(avatar) if avatar else None
                self._accounts.save(account)

        device_name = payload.get("deviceName")
        if device_name is None:
            device_name = payload.get("device_name")
        device_type = payload.get("deviceType")
        if device_type is None:
            device_type = payload.get("device_type")
        self._devices.bind_or_update_device(
            user_id=user_id,
            client_id=event_client_id,
            device_id=device_id,
            device_name=str(device_name) if device_name is not None else None,
            device_type=str(device_type) if device_type is not None else None,
        )
