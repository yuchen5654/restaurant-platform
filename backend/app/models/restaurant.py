from sqlalchemy import Column, String, Boolean, DateTime, Numeric, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base


class Restaurant(Base):
    __tablename__ = 'restaurants'

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                  = Column(String(200), nullable=False)
    address               = Column(Text)
    timezone              = Column(String(50), default='America/New_York')
    toast_location_guid   = Column(String(100))
    square_location_id    = Column(String(100))
    invoice_email_id      = Column(String(50))
    food_cost_target_pct  = Column(Numeric(5, 2), default=30.00)
    labor_cost_target_pct = Column(Numeric(5, 2), default=28.00)
    created_at            = Column(DateTime(timezone=True), server_default=func.now())
    is_active             = Column(Boolean, default=True)

    users        = relationship('User', back_populates='restaurant')
    ingredients  = relationship('Ingredient', back_populates='restaurant')
    menu_items   = relationship('MenuItem', back_populates='restaurant')


class User(Base):
    __tablename__ = 'users'

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id   = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    email           = Column(String(200), unique=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    role            = Column(String(20), default='owner')  # owner | manager | staff
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    restaurant = relationship('Restaurant', back_populates='users')
