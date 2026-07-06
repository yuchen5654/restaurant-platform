from sqlalchemy import Column, Numeric, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database import Base


class WeatherDay(Base):
    __tablename__ = 'weather_days'
    __table_args__ = (
        UniqueConstraint('restaurant_id', 'business_date', name='uq_weather_restaurant_date'),
    )

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    business_date = Column(Date, nullable=False)
    precip_mm     = Column(Numeric(6, 2), nullable=True)
    tmax          = Column(Numeric(5, 2), nullable=True)
    tmin          = Column(Numeric(5, 2), nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
