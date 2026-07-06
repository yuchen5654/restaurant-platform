from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database import Base


class ChannelFee(Base):
    __tablename__ = 'channel_fees'

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id   = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    channel         = Column(String(30), nullable=False)
    # Stored as a fraction: 0.1500 = 15%. Validated 0–1 at the Pydantic layer.
    commission_rate = Column(Numeric(5, 4), nullable=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())


class SaleAdjustment(Base):
    __tablename__ = 'sale_adjustments'

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id   = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    business_date   = Column(DateTime(timezone=True), nullable=False)
    adjustment_type = Column(String(30), nullable=False)  # comp | void | discount
    amount          = Column(Numeric(10, 2), nullable=False)
    employee_str    = Column(String(200), nullable=True)
    daypart         = Column(String(30), nullable=True)
    source          = Column(String(30), nullable=False, default='manual')
    notes           = Column(Text, nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
