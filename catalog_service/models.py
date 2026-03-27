import uuid
from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, DateTime, func, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from catalog_service.database import Base

class Venue(Base):
    """Заведение (Ресторан, Коворкинг, Автосервис)"""
    __tablename__ = "venues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    address: Mapped[str] = mapped_column(String(500), nullable=False)

    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    resources: Mapped[list["Resource"]] = relationship("Resource", back_populates="venue", cascade="all, delete-orphan")

class Resource(Base):
    """Конкретный ресурс для бронирования (Столик, Комната, Мастер)"""
    __tablename__ = "resources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False) # Например: "Столик у окна"
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1) # Вместимость
    
    # Внешний ключ на таблицу venues
    venue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venues.id", ondelete="CASCADE"), nullable=False)

    # Навигационное свойство обратно к заведению
    venue: Mapped["Venue"] = relationship("Venue", back_populates="resources")