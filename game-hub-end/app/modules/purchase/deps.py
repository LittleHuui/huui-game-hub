"""购买模块 FastAPI 依赖注入。"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.inventory.deps import get_inventory_module_service
from app.modules.inventory.entity_service import UserPropBagEntityService
from app.modules.inventory.module_service import InventoryModuleService
from app.modules.inventory.repository import UserPropBagRepository
from app.modules.prop.deps import get_prop_module_service
from app.modules.prop.module_service import PropModuleService
from app.modules.purchase.entity_service import PropPurchaseRecordEntityService
from app.modules.purchase.module_service import PurchaseModuleService
from app.modules.purchase.repository import PropPurchaseRecordRepository
from app.modules.user.entity_service import UserAccountEntityService
from app.modules.user.repository import UserAccountRepository
from app.modules.wallet.deps import get_wallet_module_service
from app.modules.wallet.module_service import WalletModuleService


def get_purchase_module_service(
    db: Session = Depends(get_db),
    prop_module: PropModuleService = Depends(get_prop_module_service),
    wallet_module: WalletModuleService = Depends(get_wallet_module_service),
    inventory_module: InventoryModuleService = Depends(get_inventory_module_service),
) -> PurchaseModuleService:
    """
    组装购买模块服务依赖。

    :param db: 请求级数据库会话。
    :param prop_module: 道具定义模块服务。
    :param wallet_module: 钱包模块服务。
    :param inventory_module: 背包模块服务。
    :return: ``PurchaseModuleService`` 实例。
    """
    return PurchaseModuleService(
        PropPurchaseRecordEntityService(PropPurchaseRecordRepository(db)),
        prop_module,
        wallet_module,
        inventory_module,
        UserPropBagEntityService(UserPropBagRepository(db)),
        UserAccountEntityService(UserAccountRepository(db)),
    )
