from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime

class ResourceBase(BaseModel):
    name: str = Field(..., max_length=255, description="Name of the resource.")
    capacity: int = Field(default=1, ge=1, description="Maximum number of people the room can accommodate.")

class ResourceCreate(ResourceBase):
    pass

class ResourceUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    capacity: int | None = Field(None, ge=1)

class ResourceResponse(ResourceBase):
    id: UUID
    venue_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class VenueBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    address: str = Field(..., max_length=500)

class VenueCreate(VenueBase):
    pass

class VenueUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    address: str | None = Field(None, max_length=500)

class VenueResponse(VenueBase):
    id: UUID
    owner_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class VenueDetailResponse(VenueResponse):
    resources: list[ResourceResponse] = Field(default_factory=list)