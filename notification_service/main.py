import logging
from faststream import FastStream
from faststream.rabbit import RabbitBroker
from pydantic import BaseModel, Field
from redis import event

from notification_service.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)

broker = RabbitBroker(settings.RABBITMQ_URL)
app = FastStream(broker)

class BookingNotificationEvent(BaseModel):
    booking_id: str
    user_id: str
    status: str
    resource_id: str | None = None
    start_time: str | None = None

@broker.subscriber("booking_notifications")
async def handle_booking_notification(event: BookingNotificationEvent):
    """
    Обработчик событий из RabbitMQ.
    FastStream автоматически достает JSON из очереди и валидирует его через Pydantic!
    """
    logger.info("-" * 50)
    logger.info(f"📥 Received event for booking: {event.booking_id} | Status: {event.status.upper()}")

    if event.status == "confirmed":
        logger.info(f"📧 [EMAIL SENT] to User {event.user_id}")
        logger.info(f"   Subject: Booking Confirmed!")
        logger.info(f"   Body: Your table is reserved for {event.start_time}.")

    elif event.status == "cancelled":
        logger.info(f"📧 [EMAIL SENT] to User {event.user_id}")
        logger.info(f"   Subject: Booking Cancelled")
        logger.info(f"   Body: Your booking has been cancelled. Please contact support if this is a mistake.")
    else:
        logger.info(f"Unknown status updated")
    
    logger.info("-" * 50)
    