from sqlalchemy import Column, String, Numeric, Integer, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database import Base


class SalesSummary(Base):
    __tablename__ = 'sales_summaries'

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    business_date = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    daypart       = Column(String(30))
    gross_revenue = Column(Numeric(12, 2), default=0)
    net_revenue   = Column(Numeric(12, 2), default=0)
    covers        = Column(Integer, default=0)
    transactions  = Column(Integer, default=0)
    comps_total   = Column(Numeric(10, 2), default=0)
    voids_total   = Column(Numeric(10, 2), default=0)
    labor_cost    = Column(Numeric(10, 2))
    source        = Column(String(30), default='manual')
    channel       = Column(String(30), default='dine_in')
    created_at    = Column(DateTime(timezone=True), server_default=func.now())


class SalesByItem(Base):
    __tablename__ = 'sales_by_item'

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    menu_item_id  = Column(UUID(as_uuid=True), ForeignKey('menu_items.id'))  # null = unmapped
    business_date = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    quantity_sold = Column(Integer, default=0)
    gross_revenue = Column(Numeric(10, 2), default=0)
    food_cost     = Column(Numeric(10, 2), default=0)
    raw_pos_name  = Column(String(200))
    source        = Column(String(30), default='manual')
    channel       = Column(String(30), default='dine_in')


class PosItemMapping(Base):
    __tablename__ = 'pos_item_mappings'

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    pos_system    = Column(String(30))
    pos_item_name = Column(String(300), nullable=False)
    menu_item_id  = Column(UUID(as_uuid=True), ForeignKey('menu_items.id'))
    is_ignored    = Column(Boolean, default=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
