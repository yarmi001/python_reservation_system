import uuid
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from catalog_service.database import get_db
from catalog_service.models import Venue, Resource
from catalog_service.schemas import (
    VenueCreate, VenueUpdate, VenueResponse, VenueDetailResponse,
    ResourceCreate, ResourceUpdate, ResourceResponse
)
from catalog_service.dependencies import get_current_user, CurrentUser

from contextlib import asynccontextmanager
from catalog_service.database import engine
from catalog_service.models import Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Эта магия сама создаст таблицы venues и resources при запуске сервера!
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(title="Catalog Service API", docs_url="/api/docs", lifespan=lifespan)

# CORS для Swagger и фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 🏢 VENUES (ЗАВЕДЕНИЯ)
# ==========================================

@app.post("/venues", response_model=VenueResponse, status_code=status.HTTP_201_CREATED, tags=["Venues"])
async def create_venue(
    venue_in: VenueCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user) # [Authorize]
):
    """Создать новое заведение (владельцем становится текущий юзер)"""
    new_venue = Venue(
        **venue_in.model_dump(), # Аналог маппинга: разворачиваем все поля из DTO
        owner_id=uuid.UUID(current_user.id) # Берем ID из JWT
    )
    db.add(new_venue)
    await db.commit()
    await db.refresh(new_venue)
    return new_venue

@app.get("/venues", response_model=list[VenueResponse], tags=["Venues"])
async def get_venues(db: AsyncSession = Depends(get_db)):
    """Получить список всех заведений (Публичный эндпоинт, без Depends(get_current_user))"""
    result = await db.execute(select(Venue))
    return result.scalars().all()

@app.get("/venues/{venue_id}", response_model=VenueDetailResponse, tags=["Venues"])
async def get_venue(venue_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Получить заведение по ID вместе с его столиками (.Include(v => v.Resources))"""
    query = select(Venue).where(Venue.id == venue_id).options(selectinload(Venue.resources))
    result = await db.execute(query)
    venue = result.scalar_one_or_none()
    
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    return venue

@app.patch("/venues/{venue_id}", response_model=VenueResponse, tags=["Venues"])
async def update_venue(
    venue_id: uuid.UUID,
    venue_update: VenueUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Частично обновить заведение (может только владелец)"""
    # db.get() - это аналог db.Venues.FindAsync(id) в EF Core
    venue = await db.get(Venue, venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
        
    if str(venue.owner_id) != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Магия Pydantic: получаем только те поля, которые клиент реально прислал в JSON!
    update_data = venue_update.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(venue, key, value) # Обновляем свойства объекта
        
    await db.commit()
    await db.refresh(venue)
    return venue

@app.delete("/venues/{venue_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Venues"])
async def delete_venue(
    venue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Удалить заведение (может только владелец). Столики удалятся каскадно!"""
    venue = await db.get(Venue, venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
        
    if str(venue.owner_id) != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
        
    await db.delete(venue)
    await db.commit()
    return None # 204 No Content не требует тела ответа

# ==========================================
# 🪑 RESOURCES (СТОЛИКИ / ПОМЕЩЕНИЯ)
# ==========================================

@app.post("/venues/{venue_id}/resources", response_model=ResourceResponse, status_code=status.HTTP_201_CREATED, tags=["Resources"])
async def create_resource(
    venue_id: uuid.UUID,
    resource_in: ResourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Добавить столик в заведение (только для владельца)"""
    venue = await db.get(Venue, venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    if str(venue.owner_id) != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    new_resource = Resource(**resource_in.model_dump(), venue_id=venue_id)
    db.add(new_resource)
    await db.commit()
    await db.refresh(new_resource)
    return new_resource

@app.patch("/resources/{resource_id}", response_model=ResourceResponse, tags=["Resources"])
async def update_resource(
    resource_id: uuid.UUID,
    resource_update: ResourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Обновить столик. Ищем столик и проверяем владельца заведения."""
    # Загружаем ресурс сразу вместе с его заведением (.Include(r => r.Venue))
    query = select(Resource).where(Resource.id == resource_id).options(selectinload(Resource.venue))
    result = await db.execute(query)
    resource = result.scalar_one_or_none()

    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    if str(resource.venue.owner_id) != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    update_data = resource_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(resource, key, value)
        
    await db.commit()
    await db.refresh(resource)
    return resource

@app.delete("/resources/{resource_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Resources"])
async def delete_resource(
    resource_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Удалить столик"""
    query = select(Resource).where(Resource.id == resource_id).options(selectinload(Resource.venue))
    result = await db.execute(query)
    resource = result.scalar_one_or_none()

    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    if str(resource.venue.owner_id) != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    await db.delete(resource)
    await db.commit()
    return None