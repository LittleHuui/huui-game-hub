"""背包模块 FastAPI 依赖注入。"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.inventory.entity_service import PropUsageRecordEntityService, UserPropBagEntityService
from app.modules.inventory.module_service import InventoryModuleService
from app.modules.inventory.repository import PropUsageRecordRepository, UserPropBagRepository
from app.modules.purchase.entity_service import PropPurchaseRecordEntityService
from app.modules.purchase.repository import PropPurchaseRecordRepository
from app.modules.user.entity_service import UserAccountEntityService
from app.modules.user.repository import UserAccountRepository


def get_inventory_module_service(db: Session = Depends(get_db)) -> InventoryModuleService:
    """
    组装背包模块服务依赖。

    :param db: 请求级数据库会话。
    :return: ``InventoryModuleService`` 实例。
    """
    return InventoryModuleService(
        UserPropBagEntityService(UserPropBagRepository(db)),
        PropPurchaseRecordEntityService(PropPurchaseRecordRepository(db)),
        PropUsageRecordEntityService(PropUsageRecordRepository(db)),
        UserAccountEntityService(UserAccountRepository(db)),
    )
