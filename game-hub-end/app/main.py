"""FastAPI 应用入口：注册路由、生命周期与全局中间能力。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router as api_router
from app.core.config import settings
from app.core.database import init_db
from app.common.exception_handlers import register_exception_handlers
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    应用生命周期：启动时初始化日志与数据库结构。

    :param _app: FastAPI 应用实例（当前未使用，保留签名便于后续扩展）。
    """
    setup_logging()
    init_db()
    yield


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

# WebSocket 预留：后续可使用 APIRouter.websocket(...) 或 app.add_api_websocket_route 注册实时通道。
