from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database import Base


class LaborEntry(Base):
    __tablename__ = 'labor_entries'

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    business_date = Column(DateTime(timezone=True), nullable=False)
    hours         = Column(Numeric(8, 2), nullable=False)
    labor_cost    = Column(Numeric(10, 2), nullable=False)
    role          = Column(String(50), nullable=True)
    source        = Column(String(20), default='manual')   # manual | csv
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
