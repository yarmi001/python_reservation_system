import bcrypt
import jwt 
from datetime import datetime, timedelta, timezone
from identity_service.config import settings

# Validate critical settings at startup
if not hasattr(settings, "SECRET_KEY") or not callable(getattr(settings.SECRET_KEY, "get_secret_value", None)):
    raise RuntimeError("SECRET_KEY is not properly configured in settings.")
if not hasattr(settings, "ALGORITHM") or not settings.ALGORITHM:
    raise RuntimeError("ALGORITHM is not properly configured in settings.")

def get_password_hash(password: str) -> str:
    """Хэширует пароль с помощью bcrypt (с автоматической генерацией соли)"""
    # bcrypt требует пароль в виде байтов (encode), а возвращает хэш в байтах, поэтому используем .decode('utf-8') перед сохранением в БД
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str | bytes) -> bool:
    """Проверяет, соответствует ли введенный пароль хэшу в базе данных"""
    password_byte = plain_password.encode('utf-8')
    hashed_bytes = (
        hashed_password.encode('utf-8') 
        if isinstance(hashed_password, str) 
        else hashed_password
    )
    return bcrypt.checkpw(password_byte, hashed_bytes)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Создает JWT токен с данными и временем истечения"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": int(expire.timestamp())})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY.get_secret_value(), algorithm=settings.ALGORITHM)
    return encoded_jwt