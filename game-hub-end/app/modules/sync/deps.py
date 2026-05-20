"""同步模块 FastAPI 依赖注入。"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.inventory.deps import get_inventory_module_service
from app.modules.inventory.module_service import InventoryModuleService
from app.modules.match.deps import get_match_module_service
from app.modules.match.module_service import MatchModuleService
from app.modules.purchase.deps import get_purchase_module_service
from app.modules.purchase.module_service import PurchaseModuleService
from app.modules.score.deps import get_score_module_service
from app.modules.score.module_service import ScoreModuleService
from app.modules.sync.entity_service import SyncLogEntityService
from app.modules.sync.module_service import SyncModuleService
from app.modules.sync.repository import SyncLogRepository
from app.modules.user.deps import get_user_module_service
from app.modules.user.module_service import UserModuleService
from app.modules.wallet.deps import get_wallet_module_service
from app.modules.wallet.module_service import WalletModuleService


def get_sync_log_repository(db: Session = Depends(get_db)) -> SyncLogRepository:
    """
    组装同步日志仓储依赖。

    :param db: 请求级数据库会话。
    :return: ``SyncLogRepository`` 实例。
    """
    return SyncLogRepository(db)


def get_sync_log_entity_service(
    repository: SyncLogRepository = Depends(get_sync_log_repository),
) -> SyncLogEntityService:
    """
    组装同步日志实体服务依赖。

    :param repository: 同步日志仓储。
    :return: ``SyncLogEntityService`` 实例。
    """
    return SyncLogEntityService(repository)


def get_sync_module_service(
    user_module: UserModuleService = Depends(get_user_module_service),
    wallet_module: WalletModuleService = Depends(get_wallet_module_service),
    purchase_module: PurchaseModuleService = Depends(get_purchase_module_service),
    inventory_module: InventoryModuleService = Depends(get_inventory_module_service),
    match_module: MatchModuleService = Depends(get_match_module_service),
    score_module: ScoreModuleService = Depends(get_score_module_service),
) -> SyncModuleService:
    """
    组装同步模块服务依赖。

    :param user_module: 用户模块服务。
    :param wallet_module: 钱包模块服务。
    :param purchase_module: 购买模块服务。
    :param inventory_module: 背包模块服务。
    :param match_module: 对局模块服务。
    :param score_module: 成绩模块服务。
    :return: ``SyncModuleService`` 实例。
    """
    return SyncModuleService(
        user_module,
        wallet_module,
        purchase_module,
        inventory_module,
        match_module,
        score_module,
    )
