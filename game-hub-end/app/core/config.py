"""应用配置，集中管理环境相关变量。"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从环境变量加载的运行时配置。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Game Hub"
    DATABASE_URL: str = "sqlite:///./game_hub.db"
    API_PREFIX: str = "/api/game-hub"
    DEBUG: bool = False
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = "123456"
    REDIS_DECODE_RESPONSES: bool = True
    REDIS_ONLINE_USER_EXPIRE_SECONDS: int = 360


settings = Settings()
