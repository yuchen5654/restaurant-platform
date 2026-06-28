from sqlalchemy import Column, String, Numeric, Integer, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base


class Vendor(Base):
    __tablename__ = 'vendors'

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id  = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    name           = Column(String(200), nullable=False)
    contact_email  = Column(String(200))
    contact_phone  = Column(String(30))
    lead_time_days = Column(Integer, default=2)
    delivery_days  = Column(String(50))

    ingredients = relationship('Ingredient', back_populates='vendor')
    invoices    = relationship('VendorInvoice', back_populates='vendor')


class Ingredient(Base):
    __tablename__ = 'ingredients'

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id         = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    vendor_id             = Column(UUID(as_uuid=True), ForeignKey('vendors.id'))
    name                  = Column(String(200), nullable=False)
    category              = Column(String(100))
    unit                  = Column(String(20), nullable=False)
    current_cost_per_unit = Column(Numeric(10, 4), nullable=False)
    par_level             = Column(Numeric(10, 3))
    reorder_qty           = Column(Numeric(10, 3))
    current_stock         = Column(Numeric(10, 3), default=0)
    created_at            = Column(DateTime(timezone=True), server_default=func.now())
    updated_at            = Column(DateTime(timezone=True), onupdate=func.now())

    vendor       = relationship('Vendor', back_populates='ingredients')
    restaurant   = relationship('Restaurant', back_populates='ingredients')
    recipe_lines = relationship('RecipeLine', back_populates='ingredient')


class InventoryCount(Base):
    __tablename__ = 'inventory_counts'

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id   = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    ingredient_id   = Column(UUID(as_uuid=True), ForeignKey('ingredients.id'), nullable=False)
    counted_at      = Column(DateTime(timezone=True), nullable=False)
    quantity        = Column(Numeric(10, 3), nullable=False)
    counted_by_user = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    notes           = Column(Text)


class WasteLog(Base):
    __tablename__ = 'waste_logs'

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    ingredient_id = Column(UUID(as_uuid=True), ForeignKey('ingredients.id'), nullable=False)
    logged_at     = Column(DateTime(timezone=True), nullable=False)
    quantity      = Column(Numeric(10, 3), nullable=False)
    reason        = Column(String(50))  # spoilage|prep_waste|over_portion|theft|comp|dropped
    cost_at_time  = Column(Numeric(10, 4))
    notes         = Column(Text)


class VendorInvoice(Base):
    __tablename__ = 'vendor_invoices'

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id  = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    vendor_id      = Column(UUID(as_uuid=True), ForeignKey('vendors.id'), nullable=False)
    invoice_number = Column(String(100))
    received_at    = Column(DateTime(timezone=True), nullable=False)
    total_amount   = Column(Numeric(10, 2))

    vendor     = relationship('Vendor', back_populates='invoices')
    line_items = relationship('InvoiceLineItem', back_populates='invoice')


class InvoiceLineItem(Base):
    __tablename__ = 'invoice_line_items'

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id        = Column(UUID(as_uuid=True), ForeignKey('vendor_invoices.id'), nullable=False)
    ingredient_id     = Column(UUID(as_uuid=True), ForeignKey('ingredients.id'), nullable=False)
    quantity_received = Column(Numeric(10, 3), nullable=False)
    unit_cost         = Column(Numeric(10, 4), nullable=False)
    extended_cost     = Column(Numeric(10, 2))

    invoice = relationship('VendorInvoice', back_populates='line_items')
