from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from pydantic import SecretStr

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    CATALOG_DB_URL: str
    SECRET_KEY: SecretStr
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / '.env',
        env_file_encoding = 'utf-8',
        extra = 'ignore'
    )

settings = Settings()  