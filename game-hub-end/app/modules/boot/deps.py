"""启动上下文与健康探测依赖装配。"""

from functools import lru_cache
from fastapi import Depends
from app.core.redis.redis_client import redis_client
from app.modules.boot.health_service import HealthService
from app.modules.boot.module_service import BootModuleService
from app.modules.game_config.deps import get_game_module_service
from app.modules.game_config.module_service import GameModuleService
from app.modules.user.deps import get_user_module_service
from app.modules.user.module_service import UserModuleService


@lru_cache(maxsize=1)
def get_health_service() -> HealthService:
    """复用探测状态，避免慢数据库导致每个请求新建探测线程。"""
    return HealthService(redis_client)


def get_boot_module_service(
    user_service: UserModuleService = Depends(get_user_module_service),
    game_service: GameModuleService = Depends(get_game_module_service),
) -> BootModuleService:
    """装配启动上下文的必要用户与游戏服务。"""
    return BootModuleService(user_service, game_service)
