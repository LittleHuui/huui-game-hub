"""钱包模块 FastAPI 依赖注入。"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.user.entity_service import UserAccountEntityService
from app.modules.user.repository import UserAccountRepository
from app.modules.wallet.entity_service import UserWalletEntityService, WalletLedgerEntityService
from app.modules.wallet.module_service import WalletModuleService
from app.modules.wallet.repository import UserWalletRepository, WalletLedgerRepository


def get_wallet_module_service(db: Session = Depends(get_db)) -> WalletModuleService:
    """
    组装钱包模块服务依赖。

    :param db: 请求级数据库会话。
    :return: ``WalletModuleService`` 实例。
    """
    return WalletModuleService(
        UserWalletEntityService(UserWalletRepository(db)),
        WalletLedgerEntityService(WalletLedgerRepository(db)),
        UserAccountEntityService(UserAccountRepository(db)),
    )
