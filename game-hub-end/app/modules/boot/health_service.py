"""存活与依赖就绪探测，不装配用户或同步业务。"""

import asyncio
from typing import Optional
from sqlalchemy import text
from app.core.database import session_scope
from app.core.logging import get_logger
from app.core.redis.redis_client import RedisClient
from app.core.time_utils import now_ms
from app.game_runtime import get_game_module_registry
from app.modules.boot.schemas import HealthCheckResponse
from app.modules.room import background_coordinator

logger = get_logger(__name__)
READINESS_DEPENDENCY_TIMEOUT_SECONDS = 3


def _probe_database() -> bool:
    """在独立线程中打开短会话，探测后无论成功失败都释放会话。"""
    with session_scope() as session:
        session.execute(text("SELECT 1"))
    return True


class HealthService:
    """提供存活与有界就绪探测；慢数据库探测保持单次在途。"""

    def __init__(self, redis: RedisClient) -> None:
        """注入 Redis 探测端口并初始化数据库探测状态。"""
        self._redis = redis
        self._database_probe = None  # type: Optional[asyncio.Future]

    async def health_live(self) -> HealthCheckResponse:
        """返回进程存活状态，不访问外部依赖。"""
        return HealthCheckResponse(status="ok", serverTime=now_ms())

    async def _database_ready(self) -> bool:
        """隔离同步数据库探测；超时后保留在途探测避免重复占用线程。"""
        if self._database_probe is None:
            self._database_probe = asyncio.get_running_loop().run_in_executor(None, _probe_database)
        probe = self._database_probe
        try:
            return bool(await asyncio.wait_for(asyncio.shield(probe), READINESS_DEPENDENCY_TIMEOUT_SECONDS))
        finally:
            if probe.done() and self._database_probe is probe:
                self._database_probe = None

    async def health_ready(self) -> HealthCheckResponse:
        """并行探测数据库与 Redis，汇总后台协调器和注册表状态。"""
        components = {"database": False, "redis": False,
                      "roomBackgroundCoordinator": False, "gameModuleRegistryFrozen": False}
        results = await asyncio.gather(
            self._database_ready(),
            asyncio.wait_for(self._redis.ping(), READINESS_DEPENDENCY_TIMEOUT_SECONDS),
            return_exceptions=True,
        )
        for name, result in zip(("database", "redis"), results):
            if isinstance(result, BaseException):
                logger.warning("readiness %s check failed: %s", name, type(result).__name__)
            else:
                components[name] = bool(result)
        try:
            components["roomBackgroundCoordinator"] = background_coordinator.is_room_background_ready()
            components["gameModuleRegistryFrozen"] = get_game_module_registry().is_frozen
        except Exception:
            logger.exception("readiness runtime check failed")
        return HealthCheckResponse(status="ok" if all(components.values()) else "unready",
                                   serverTime=now_ms(), components=components)
