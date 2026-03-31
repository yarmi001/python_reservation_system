import uuid
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_

# Импорт брокера сообщений (Аналог MassTransit)
from faststream.rabbit import RabbitBroker

from booking_service.config import settings
from booking_service.database import get_db, engine
from booking_service.models import Base, Booking, BookingStatus
from booking_service.schemas import BookingCreate, BookingResponse
from booking_service.dependencies import get_current_user, CurrentUser

logger = logging.getLogger("uvicorn")

# 1. Создаем объект брокера RabbitMQ
broker = RabbitBroker(settings.RABBITMQ_URL)

# 2. Жизненный цикл приложения (Startup / Shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Booking Service...")
    # Auto-create tables (EnsureCreated)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Connecting to RabbitMQ
    await broker.connect()
    logger.info("Connected to RabbitMQ!")
    
    yield # Application is running
    
    # Proper shutdown on stop
    await broker.disconnect()
    await engine.dispose()

app = FastAPI(title="Booking Service API", docs_url="/api/docs", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 📅 BOOKINGS (БРОНИРОВАНИЕ)
# ==========================================

@app.post("/bookings", response_model=BookingResponse, status_code=status.HTTP_201_CREATED, tags=["Bookings"])
async def create_booking(
    booking_in: BookingCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Create a new booking with overlap check"""
    
    # 1. Basic date validation
    # Ensure datetimes are timezone-aware and in UTC
    if booking_in.start_time.tzinfo is None or booking_in.start_time.tzinfo.utcoffset(booking_in.start_time) is None:
        raise HTTPException(status_code=400, detail="Start time must be timezone-aware (UTC).")
    if booking_in.end_time.tzinfo is None or booking_in.end_time.tzinfo.utcoffset(booking_in.end_time) is None:
        raise HTTPException(status_code=400, detail="End time must be timezone-aware (UTC).")

    # Convert to UTC if not already
    start_time_utc = booking_in.start_time.astimezone(timezone.utc)
    end_time_utc = booking_in.end_time.astimezone(timezone.utc)

    if start_time_utc >= end_time_utc:
        raise HTTPException(status_code=400, detail="Start time must be before end time.")
        
    if start_time_utc < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Cannot book in the past.")

    # 2. Overlap check
    # There is an overlap if (existing_start < new_end) and (existing_end > new_start)
    overlap_query = select(Booking).where(
        Booking.resource_id == booking_in.resource_id,
        Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.PENDING]),
        and_(
            Booking.start_time < booking_in.end_time,
            Booking.end_time > booking_in.start_time
        )
    )
    result = await db.execute(overlap_query)
    if result.scalars().first():
        raise HTTPException(status_code=409, detail="Resource is already booked for this time slot.")

    # 3. Save to DB
    try:
        user_uuid = uuid.UUID(current_user.id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format. Must be a valid UUID.")

    new_booking = Booking(
        user_id=user_uuid,
        resource_id=booking_in.resource_id,
        start_time=booking_in.start_time,
        end_time=booking_in.end_time,
        status=BookingStatus.CONFIRMED # In real world, could be PENDING until payment
    )
    db.add(new_booking)
    await db.commit()
    await db.refresh(new_booking)

    # 4. Send event to RabbitMQ (asynchronously)
    # Prepare event payload
    event_payload = {
        "booking_id": str(new_booking.id),
        "user_id": current_user.id,
        "resource_id": str(new_booking.resource_id),
        "start_time": new_booking.start_time.isoformat(),
        "status": new_booking.status.value
    }
    # Publish to "booking_notifications" queue
    await broker.publish(event_payload, queue="booking_notifications")

    return new_booking


@app.get("/bookings/me", response_model=list[BookingResponse], tags=["Bookings"])
async def get_my_bookings(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Get all bookings for the current user"""
    try:
        user_uuid = uuid.UUID(current_user.id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format. Must be a valid UUID.")
    query = select(Booking).where(Booking.user_id == user_uuid)
    result = await db.execute(query)
    return result.scalars().all()


@app.patch("/bookings/{booking_id}/cancel", response_model=BookingResponse, tags=["Bookings"])
async def cancel_booking(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Cancel a booking"""
    # Fetch the booking
    booking = await db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    try:
        booking_user_id = uuid.UUID(str(booking.user_id))
        current_user_id = uuid.UUID(str(current_user.id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format. Must be a valid UUID.")

    if booking_user_id != current_user_id:
        raise HTTPException(status_code=403, detail="You can only cancel your own bookings.")

    booking.status = BookingStatus.CANCELLED
    await db.commit()
    await db.refresh(booking)

    # Notify via RabbitMQ about cancellation
    await broker.publish(
        {"booking_id": str(booking.id), "status": BookingStatus.CANCELLED.value, "user_id": current_user.id}, 
        queue="booking_notifications"
    )

    return booking