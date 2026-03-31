from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from booking_service.models import BookingStatus

class BookingCreate(BaseModel):
    resource_id: UUID
    start_time: datetime
    end_time: datetime

class BookingResponse(BaseModel):
    id: UUID
    user_id: UUID
    resource_id: UUID
    start_time: datetime
    end_time: datetime
    status: BookingStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)