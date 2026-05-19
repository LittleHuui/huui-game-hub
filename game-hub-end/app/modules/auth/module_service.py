"""认证模块业务编排。"""

from typing import List

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.modules.auth.schemas import LoginRequest, LoginResponse
from app.modules.boot.schemas import UserPropBagResponse, UserWalletResponse
from app.modules.inventory.module_service import InventoryModuleService
from app.modules.user.entity_service import (
    UserAccountEntityService,
    UserDeviceEntityService,
    UserSystemSettingEntityService,
)
from app.modules.user.schemas import (
    user_account_to_response,
    user_system_setting_read_to_response,
    user_system_setting_to_read,
)
from app.modules.wallet.module_service import WalletModuleService


def _stable_auth_device_client_id(user_id: str, device_id: str) -> str:
    """
    为登录场景生成稳定的设备记录幂等 client_id。

    :param user_id: 用户 ``server_id``。
    :param device_id: 前端设备 ID。
    :return: 合成 client_id 字符串。
    """
    return "auth|{0}|{1}".format(user_id, device_id)


class AuthModuleService:
    """认证模块：用户名登录与启动数据聚合。"""

    def __init__(
        self,
        account_entity: UserAccountEntityService,
        device_entity: UserDeviceEntityService,
        system_setting_entity: UserSystemSettingEntityService,
        wallet_module_service: WalletModuleService,
        inventory_module_service: InventoryModuleService,
    ) -> None:
        self._accounts = account_entity
        self._devices = device_entity
        self._system_settings = system_setting_entity
        self._wallet_module_service = wallet_module_service
        self._inventory_module_service = inventory_module_service

    def login(self, request: LoginRequest) -> LoginResponse:
        """
        按用户名登录，绑定设备并返回启动所需基础数据。

        :param request: 登录请求。
        :return: 用户、系统设置、钱包与背包快照。
        :raises BizException: 用户不存在或已禁用。
        """
        account = self._accounts.get_by_username(request.username, active_only=True)
        if account is None:
            raise BizException(ErrorCode.USER_NOT_FOUND)
        if account.status != "normal":
            raise BizException(ErrorCode.USER_DISABLED)

        user_id = account.server_id
        device_client_id = _stable_auth_device_client_id(user_id, request.deviceId)
        self._devices.bind_or_update_device(
            user_id=user_id,
            client_id=device_client_id,
            device_id=request.deviceId,
            device_name=None,
            device_type=None,
        )

        setting_entity = self._system_settings.create_if_not_exists(user_id)
        wallet_response = self._load_wallet_response(user_id)
        inventory_items = self._load_inventory_response(user_id)

        return LoginResponse(
            user=user_account_to_response(account),
            systemSetting=user_system_setting_read_to_response(
                user_system_setting_to_read(setting_entity),
            ),
            wallet=wallet_response,
            inventory=inventory_items,
        )

    def _load_wallet_response(self, user_id: str) -> UserWalletResponse:
        """
        获取或创建用户钱包并转为 API 响应。

        :param user_id: 用户主键。
        :return: 钱包响应对象。
        """
        return self._wallet_module_service.get_user_wallet(user_id)

    def _load_inventory_response(self, user_id: str) -> List[UserPropBagResponse]:
        """
        查询用户背包快照并转为 API 响应列表。

        :param user_id: 用户主键。
        :return: 背包响应列表。
        """
        return self._inventory_module_service.list_user_inventory(user_id)
