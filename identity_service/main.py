import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, status, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.future import select
from identity_service.models import User
from identity_service.schemas import UserCreate, UserResponse, Token
from identity_service.security import get_password_hash, verify_password, create_access_token
from identity_service.database import get_db, engine, async_session_maker
from identity_service.dependencies import get_current_user
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("uvicorn")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Identity Service... Checking database connection.")
    try:
        async with async_session_maker() as db:
            await db.execute(text("SELECT 1"))
            logger.info("Successfully connected to the PostgreSQL database.")
    except Exception as e:
        logger.error(f"Failed to connect to the database: {e}")
        # Завершаем работу, если БД недоступна
        raise RuntimeError("Database connection failed. Application cannot start.") from e

    # --- Приложение готово к работе ---
    yield 
    # --- Приложение останавливается ---

    logger.info("Shutting down... Disposing database engine.")
    await engine.dispose()

app = FastAPI(
    title="Identity Service API",
    description="Микросервис авторизации (Users & Auth)",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # В Production тут будут конкретные домены, например ["http://localhost:8002", "https://myfrontend.com"]
    allow_credentials=True,
    allow_methods=["*"], # Разрешаем любые методы (GET, POST, OPTIONS и т.д.)
    allow_headers=["*"], # Разрешаем любые заголовки
)

@app.get("/health/liveness", tags=["Monitoring"], status_code=status.HTTP_200_OK)
async def liveness_check():
    """Эндпоинт для проверки жизнеспособности контейнера (Liveness probe)"""
    return {"status": "healthy", "service": "identity_service"}

@app.get("/health/readiness", tags=["Monitoring"])
async def readiness_check(db: AsyncSession = Depends(get_db)):
    try:
        # Проверяем жива ли база
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        # Пишем реальную ошибку с деталями во внутренние логи (разработчику)
        logger.error(f"Readiness check failed. Database unreachable: {e}")
        
        # Отдаем наружу (Docker/клиенту) статус 503 и безопасное, общее сообщение
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is unhealthy. Database is unreachable."
        )
    
@app.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Auth"]
)

async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """Регистрация нового пользователя"""
    query = select(User).where(User.email == user_in.email)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Email is already registered"
        )
        
    # 2. Создаем пользователя (БЕЗ полей role и is_active - защита от Mass Assignment)
    new_user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password)
        # БД сама подставит role="user" и is_active=True
    )
    
    db.add(new_user)
    
    # 3. Безопасное сохранение с обработкой коллизий (Race Conditions)
    try:
        await db.commit()
        await db.refresh(new_user) # Загружаем сгенерированный ID и created_at из БД
    except IntegrityError as e:
        # ОБЯЗАТЕЛЬНО: Если commit упал, сессия становится невалидной. Нужно откатить транзакцию.
        await db.rollback() 
        logger.warning(f"Registration conflict for email {user_in.email}. Details: {e}")
        
        # 409 Conflict - правильный HTTP статус при нарушении уникальности (Unique Constraint)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists."
        )
    except Exception as e:
        # Ловим любые другие ошибки базы (например, отвалилась сеть в момент коммита)
        await db.rollback()
        logger.error(f"Unexpected error during user registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please try again later."
        )

    return new_user

@app.post("/auth/login", response_model=Token, tags=["Auth"])
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """
    Аутентификация пользователя и выдача JWT токена

    ВНИМАНИЕ: Поле 'username' формы должно содержать email пользователя.

    Требуемый формат запроса: application/x-www-form-urlencoded (OAuth2PasswordRequestForm).
    """
    query = select(User).where(User.email == form_data.username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    return Token(access_token=access_token, token_type="bearer")

@app.get("/users/me", response_model=UserResponse, tags=["Users"])
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Получить информацию о текущем пользователе (только для авторизованных)"""
    return current_user