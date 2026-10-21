"""认证模块 FastAPI 依赖注入。"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.auth.deps import get_authenticated_user
from app.core.auth.schemas import AuthenticatedUser
from app.core.database import get_db
from app.modules.auth.module_service import AuthModuleService
from app.modules.inventory.deps import get_inventory_module_service
from app.modules.inventory.module_service import InventoryModuleService
from app.modules.user.entity_service import (
    UserAccountEntityService,
    UserDeviceEntityService,
    UserSystemSettingEntityService,
)
from app.modules.user.repository import (
    UserAccountRepository,
    UserDeviceRepository,
    UserSystemSettingRepository,
)
from app.modules.wallet.deps import get_wallet_module_service
from app.modules.wallet.module_service import WalletModuleService


def get_auth_module_service(
    db: Session = Depends(get_db),
    wallet_module_service: WalletModuleService = Depends(get_wallet_module_service),
    inventory_module_service: InventoryModuleService = Depends(get_inventory_module_service),
) -> AuthModuleService:
    """
    组装认证模块服务依赖。

    :param db: 请求级数据库会话。
    :param wallet_module_service: 钱包模块服务。
    :param inventory_module_service: 背包模块服务。
    :return: ``AuthModuleService`` 实例。
    """
    return AuthModuleService(
        UserAccountEntityService(UserAccountRepository(db)),
        UserDeviceEntityService(UserDeviceRepository(db)),
        UserSystemSettingEntityService(UserSystemSettingRepository(db)),
        wallet_module_service,
        inventory_module_service,
    )


def get_authenticated_account(
    auth_user: AuthenticatedUser = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    """Resolve a normal user account for authenticated HTTP requests."""
    account_service = UserAccountEntityService(UserAccountRepository(db))
    account = account_service.get_by_server_id(auth_user.userId, active_only=True)
    if account is None or account.status != "normal":
        raise BizException(ErrorCode.AUTH_UNAUTHORIZED)
    return account
