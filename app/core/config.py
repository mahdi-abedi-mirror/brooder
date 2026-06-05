from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str
    API_KEY: str
    # داشبورد کاربری
    DASHBOARD_USERNAME: str = "admin"
    DASHBOARD_PASSWORD: str = "changeme123"
    SESSION_EXPIRE_HOURS: int = 12
    # تلگرام
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    DEBUG: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
