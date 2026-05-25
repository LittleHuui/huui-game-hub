"""API 路由聚合。"""

from fastapi import APIRouter

from app.core.config import settings
from app.modules.admin_config.api import router as admin_config_router
from app.modules.auth.api import auth_router
from app.modules.boot.api import boot_router
from app.modules.inventory.api import inventory_router
from app.modules.game.api import router as game_router
from app.modules.prop.api import router as prop_router
from app.modules.purchase.api import purchase_router
from app.modules.match.api import router as match_router
from app.modules.online.api import online_router
from app.modules.ranking.api import router as ranking_router
from app.modules.system.api import router as system_router
from app.modules.user.api import router as user_router
from app.modules.wallet.api import router as wallet_router

router = APIRouter(prefix=settings.API_PREFIX, tags=["game-hub"])

router.include_router(boot_router)
router.include_router(auth_router)
router.include_router(user_router)
router.include_router(wallet_router)
router.include_router(inventory_router)
router.include_router(prop_router)
router.include_router(purchase_router)
router.include_router(game_router)
router.include_router(match_router)
router.include_router(ranking_router)
router.include_router(system_router)
router.include_router(online_router)
router.include_router(admin_config_router)
