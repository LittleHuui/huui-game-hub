"""应用配置，集中管理环境相关变量。"""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从环境变量加载的运行时配置。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Game Hub"
    DATABASE_URL: str = "sqlite:///./game_hub.db"
    API_PREFIX: str = "/api/game-hub"
    DEBUG: bool = False
    AUTH_JWT_SECRET: Optional[str] = None
    AUTH_ACCESS_TOKEN_EXPIRE_SECONDS: int = 3600
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DECODE_RESPONSES: bool = True
    REDIS_ONLINE_USER_EXPIRE_SECONDS: int = 360
    RUNTIME_EVENT_LOG_LIMIT: int = 200


settings = Settings()
