"""启动模块 FastAPI 依赖注入。"""

from fastapi import Depends

from app.modules.boot.module_service import BootModuleService
from app.modules.game.deps import get_game_module_service
from app.modules.game.module_service import GameModuleService
from app.modules.inventory.deps import get_inventory_module_service
from app.modules.inventory.module_service import InventoryModuleService
from app.modules.match.deps import get_match_module_service
from app.modules.match.module_service import MatchModuleService
from app.modules.purchase.deps import get_purchase_module_service
from app.modules.purchase.module_service import PurchaseModuleService
from app.modules.score.deps import get_score_module_service
from app.modules.score.module_service import ScoreModuleService
from app.modules.sync.deps import get_sync_log_entity_service, get_sync_module_service
from app.modules.sync.entity_service import SyncLogEntityService
from app.modules.sync.module_service import SyncModuleService
from app.modules.user.deps import get_user_module_service
from app.modules.user.module_service import UserModuleService
from app.modules.wallet.deps import get_wallet_module_service
from app.modules.wallet.module_service import WalletModuleService


def get_boot_module_service(
    user_service: UserModuleService = Depends(get_user_module_service),
    game_service: GameModuleService = Depends(get_game_module_service),
    sync_log_entity: SyncLogEntityService = Depends(get_sync_log_entity_service),
    sync_service: SyncModuleService = Depends(get_sync_module_service),
    wallet_service: WalletModuleService = Depends(get_wallet_module_service),
    purchase_service: PurchaseModuleService = Depends(get_purchase_module_service),
    inventory_service: InventoryModuleService = Depends(get_inventory_module_service),
    match_service: MatchModuleService = Depends(get_match_module_service),
    score_service: ScoreModuleService = Depends(get_score_module_service),
) -> BootModuleService:
    """
    组装启动模块服务依赖。

    :param user_service: 用户模块服务。
    :param game_service: 游戏模块服务。
    :param sync_log_entity: 同步日志实体服务。
    :param sync_service: 同步模块服务。
    :param wallet_service: 钱包模块服务。
    :param purchase_service: 购买模块服务。
    :param inventory_service: 背包模块服务。
    :param match_service: 对局模块服务。
    :param score_service: 成绩模块服务。
    :return: ``BootModuleService`` 实例。
    """
    return BootModuleService(
        user_service,
        game_service,
        sync_log_entity,
        sync_service,
        wallet_service,
        purchase_service,
        inventory_service,
        match_service,
        score_service,
    )
