from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    BOOKING_DB_URL: str
    RABBITMQ_URL: str
    SECRET_KEY: SecretStr
    ALGORITHM: str = "HS256"

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()