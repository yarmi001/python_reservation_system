from pathlib import Path
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Определяем абсолютный путь до корня проекта
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # Required variables (приложение упадет при старте, если их нет)
    IDENTITY_DB_URL: str
    SECRET_KEY: SecretStr  # SecretStr скроет значение при выводе в консоль (***)
    
    # Optional variables
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Настройки Pydantic: читаем из .env, игнорируем лишние переменные окружения
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()