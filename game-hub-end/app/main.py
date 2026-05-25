"""FastAPI 应用入口：注册路由、生命周期与全局中间能力。"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router as api_router
from app.core.config import settings
from app.core.database import init_db
from app.core.redis.redis_client import redis_client
from app.core.websocket.message_dispatcher import realtime_router
from app.common.exception_handlers import register_exception_handlers
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    应用生命周期：启动时初始化日志、数据库结构与 Redis 连通性检查。

    :param _app: FastAPI 应用实例（当前未使用，保留签名便于后续扩展）。
    """
    setup_logging()
    init_db()
    await _check_redis_connection()
    yield


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
