from sqlalchemy import Column, Integer, Numeric, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database import Base


class RestaurantSettings(Base):
    __tablename__ = 'restaurant_settings'

    id                         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id              = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'),
                                       nullable=False, unique=True, index=True)
    monthly_fixed_costs        = Column(Numeric(12, 2), nullable=True)
    target_food_cost_pct       = Column(Numeric(5, 2), default=30.0)
    menu_eng_popularity_factor = Column(Numeric(4, 2), default=0.70)
    par_min_cover_days         = Column(Integer, default=4)
    par_max_cover_days         = Column(Integer, default=21)
    seat_count                 = Column(Integer, nullable=True)
    lat                        = Column(Numeric(9, 6), nullable=True)
    lon                        = Column(Numeric(9, 6), nullable=True)
    restaurant_type            = Column(String(30), default='dine_in')
    created_at                 = Column(DateTime(timezone=True), server_default=func.now())
    updated_at                 = Column(DateTime(timezone=True), onupdate=func.now())
