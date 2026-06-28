from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database import Base


class Alert(Base):
    __tablename__ = 'alerts'

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    alert_type    = Column(String(50), nullable=False)  # food_cost_spike | low_stock | inventory_variance
    severity      = Column(String(20), nullable=False)  # high | medium | low
    message       = Column(Text, nullable=False)
    extra_data    = Column(JSON)      # alert-type-specific fields (e.g. ingredient_id)
    is_read       = Column(Boolean, default=False, nullable=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
