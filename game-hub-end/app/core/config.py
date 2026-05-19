"""应用配置，集中管理环境相关变量。"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从环境变量加载的运行时配置。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Game Hub"
    DATABASE_URL: str = "sqlite:///./game_hub.db"
    API_PREFIX: str = "/api/game-hub"
    DEBUG: bool = False


settings = Settings()
