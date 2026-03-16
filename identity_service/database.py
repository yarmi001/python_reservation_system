from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from identity_service.config import settings

engine = create_async_engine(
    settings.IDENTITY_DB_URL, 
    echo=False,
    pool_size=5,  # Максимальное количество соединений в пуле
    max_overflow=10,  # Максимальное количество дополнительных соединений сверх pool_size
    pool_pre_ping=True,  # Проверять соединение перед использованием
    )

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Отключаем автоматическое истечение срока действия объектов
    autoflush=False,  # Отключаем автоматическую синхронизацию с базой данных при каждом изменении объекта   
)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()