"""FastAPI 应用入口：注册路由、生命周期与全局中间能力。"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Awaitable, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router as api_router
from app.core.auth.config_validator import validate_auth_settings
from app.core.config import settings
from app.core.database import init_db
from app.core.redis.redis_client import redis_client
from app.core.websocket.connection_manager import connection_manager
from app.realtime.router import realtime_router
from app.modules.room.background_coordinator import initialize_room_background, shutdown_room_background
from app.common.exception_handlers import register_exception_handlers
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)
STARTUP_TIMEOUT_SECONDS = 30
SHUTDOWN_COMPONENT_TIMEOUT_SECONDS = 30


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    应用生命周期：启动时初始化日志、数据库结构与 Redis 连通性检查。

    :param _app: FastAPI 应用实例（当前未使用，保留签名便于后续扩展）。
    """
    setup_logging()
    validate_auth_settings(settings)
    should_start_room_background = os.environ.get("APP_SKIP_ROOM_BACKGROUND") != "true"
    try:
        await asyncio.wait_for(_initialize_dependencies(should_start_room_background), STARTUP_TIMEOUT_SECONDS)
        yield
    finally:
        if should_start_room_background:
            await _close_component(shutdown_room_background, "room background")
        await _close_component(connection_manager.stop, "realtime connections")
        await _close_component(redis_client.close, "redis")


async def _initialize_dependencies(start_background: bool) -> None:
    """在统一启动期限内初始化依赖，同步数据库工作移出事件循环。"""
    await asyncio.get_running_loop().run_in_executor(None, init_db)
    await redis_client.reconnect()
    await _check_redis_connection()
    await connection_manager.start()
    if start_background:
        await initialize_room_background()


async def _close_component(close: Callable[[], Awaitable[None]], name: str) -> None:
    """有界关闭单个组件，某组件失败时继续释放其余资源。"""
    try:
        await asyncio.wait_for(close(), SHUTDOWN_COMPONENT_TIMEOUT_SECONDS)
    except Exception:
        logger.exception("shutdown failed: %s", name)


async def _check_redis_connection() -> None:
    """
    执行启动期 Redis ping 检查并记录结果。

    :return: 无。
    """
    info = redis_client.get_connection_info_for_log()
    try:
        await redis_client.ping()
        logger.info(
            "Redis connected, host=%s port=%s db=%s",
            info["host"],
            info["port"],
            info["db"],
        )
    except Exception:
        logger.exception(
            "Redis connection failed, host=%s port=%s db=%s",
            info["host"],
            info["port"],
            info["db"],
        )


app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(api_router)
app.include_router(realtime_router)
