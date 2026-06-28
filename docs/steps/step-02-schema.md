# Step 2 — Core Database Schema (Multi-Tenant Foundation)

**Estimated time:** 4–6 hours
**Phase:** 1 (Foundation)
**Depends on:** Step 1.

---

## Goal

The complete database schema. Multi-tenancy (`restaurant_id` on every table) and point-in-time integrity (append-only, timestamped) are the two governing principles. Getting this right now prevents painful refactors later.

## 2.1 Restaurant & User — `app/models/restaurant.py`

```python
from sqlalchemy import Column, String, Boolean, DateTime, Numeric, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.database import Base

class Restaurant(Base):
    __tablename__ = 'restaurants'
    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                 = Column(String(200), nullable=False)
    address              = Column(Text)
    timezone             = Column(String(50), default='America/New_York')
    toast_location_guid  = Column(String(100))
    square_location_id   = Column(String(100))
    invoice_email_id     = Column(String(50))   # short id for inbound invoice email (Step 5B)
    food_cost_target_pct = Column(Numeric(5,2), default=30.00)
    labor_cost_target_pct= Column(Numeric(5,2), default=28.00)
    created_at           = Column(DateTime(timezone=True), server_default=func.now())
    is_active            = Column(Boolean, default=True)
    users       = relationship('User', back_populates='restaurant')
    ingredients = relationship('Ingredient', back_populates='restaurant')
    menu_items  = relationship('MenuItem', back_populates='restaurant')

class User(Base):
    __tablename__ = 'users'
    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id   = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    email           = Column(String(200), unique=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    role            = Column(String(20), default='owner')  # owner | manager | staff
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    restaurant      = relationship('Restaurant', back_populates='users')
```

## 2.2 Vendor & Inventory — `app/models/inventory.py`

```python
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
    ingredients    = relationship('Ingredient', back_populates='vendor')
    invoices       = relationship('VendorInvoice', back_populates='vendor')

class Ingredient(Base):
    __tablename__ = 'ingredients'
    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id        = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    vendor_id            = Column(UUID(as_uuid=True), ForeignKey('vendors.id'))
    name                 = Column(String(200), nullable=False)
    category             = Column(String(100))
    unit                 = Column(String(20), nullable=False)  # lb, oz, each, liter ...
    current_cost_per_unit= Column(Numeric(10,4), nullable=False)
    par_level            = Column(Numeric(10,3))
    reorder_qty          = Column(Numeric(10,3))
    current_stock        = Column(Numeric(10,3), default=0)
    created_at           = Column(DateTime(timezone=True), server_default=func.now())
    updated_at           = Column(DateTime(timezone=True), onupdate=func.now())
    vendor               = relationship('Vendor', back_populates='ingredients')
    restaurant           = relationship('Restaurant', back_populates='ingredients')
    recipe_lines         = relationship('RecipeLine', back_populates='ingredient')

class InventoryCount(Base):
    __tablename__ = 'inventory_counts'
    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id   = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    ingredient_id   = Column(UUID(as_uuid=True), ForeignKey('ingredients.id'), nullable=False)
    counted_at      = Column(DateTime(timezone=True), nullable=False)
    quantity        = Column(Numeric(10,3), nullable=False)
    counted_by_user = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    notes           = Column(Text)

class WasteLog(Base):
    __tablename__ = 'waste_logs'
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    ingredient_id = Column(UUID(as_uuid=True), ForeignKey('ingredients.id'), nullable=False)
    logged_at     = Column(DateTime(timezone=True), nullable=False)
    quantity      = Column(Numeric(10,3), nullable=False)
    reason        = Column(String(50))  # spoilage|prep_waste|over_portion|theft|comp|dropped
    cost_at_time  = Column(Numeric(10,4))
    notes         = Column(Text)

class VendorInvoice(Base):
    __tablename__ = 'vendor_invoices'
    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id  = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    vendor_id      = Column(UUID(as_uuid=True), ForeignKey('vendors.id'), nullable=False)
    invoice_number = Column(String(100))
    received_at    = Column(DateTime(timezone=True), nullable=False)
    total_amount   = Column(Numeric(10,2))
    vendor         = relationship('Vendor', back_populates='invoices')
    line_items     = relationship('InvoiceLineItem', back_populates='invoice')

class InvoiceLineItem(Base):
    __tablename__ = 'invoice_line_items'
    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id        = Column(UUID(as_uuid=True), ForeignKey('vendor_invoices.id'), nullable=False)
    ingredient_id     = Column(UUID(as_uuid=True), ForeignKey('ingredients.id'), nullable=False)
    quantity_received = Column(Numeric(10,3), nullable=False)
    unit_cost         = Column(Numeric(10,4), nullable=False)
    extended_cost     = Column(Numeric(10,2))
    invoice           = relationship('VendorInvoice', back_populates='line_items')
```

## 2.3 Recipe engine — `app/models/recipe.py`

```python
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from app.database import Base

class MenuItem(Base):
    __tablename__ = 'menu_items'
    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id   = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    name            = Column(String(200), nullable=False)
    category        = Column(String(100))
    menu_price      = Column(Numeric(8,2), nullable=False)
    is_active       = Column(Boolean, default=True)
    pos_name        = Column(String(200))
    pos_item_id     = Column(String(100))
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    restaurant      = relationship('Restaurant', back_populates='menu_items')
    recipe_lines    = relationship('RecipeLine', back_populates='menu_item',
                                   cascade='all, delete-orphan')

    @property
    def theoretical_food_cost(self):
        return sum(rl.line_cost for rl in self.recipe_lines if rl.line_cost is not None)

    @property
    def food_cost_pct(self):
        if not self.menu_price or float(self.menu_price) == 0:
            return None
        return round(self.theoretical_food_cost / float(self.menu_price) * 100, 2)

class RecipeLine(Base):
    __tablename__ = 'recipe_lines'
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    menu_item_id  = Column(UUID(as_uuid=True), ForeignKey('menu_items.id'), nullable=False)
    ingredient_id = Column(UUID(as_uuid=True), ForeignKey('ingredients.id'), nullable=False)
    quantity      = Column(Numeric(10,4), nullable=False)
    unit          = Column(String(20), nullable=False)
    notes         = Column(Text)
    menu_item     = relationship('MenuItem', back_populates='recipe_lines')
    ingredient    = relationship('Ingredient', back_populates='recipe_lines')

    @property
    def line_cost(self):
        if self.ingredient and self.ingredient.current_cost_per_unit:
            return float(self.quantity) * float(self.ingredient.current_cost_per_unit)
        return None
```

## 2.4 Sales & time-series — `app/models/sales.py`

```python
from sqlalchemy import Column, String, Numeric, Integer, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.database import Base

class SalesSummary(Base):
    __tablename__ = 'sales_summaries'
    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id   = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    business_date   = Column(DateTime(timezone=True), nullable=False)
    daypart         = Column(String(30))
    gross_revenue   = Column(Numeric(12,2), default=0)
    net_revenue     = Column(Numeric(12,2), default=0)
    covers          = Column(Integer, default=0)
    transactions    = Column(Integer, default=0)
    comps_total     = Column(Numeric(10,2), default=0)
    voids_total     = Column(Numeric(10,2), default=0)
    labor_cost      = Column(Numeric(10,2))
    source          = Column(String(30), default='manual')
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

class SalesByItem(Base):
    __tablename__ = 'sales_by_item'
    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id   = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    menu_item_id    = Column(UUID(as_uuid=True), ForeignKey('menu_items.id'))  # null = unmapped
    business_date   = Column(DateTime(timezone=True), nullable=False)
    quantity_sold   = Column(Integer, default=0)
    gross_revenue   = Column(Numeric(10,2), default=0)
    food_cost       = Column(Numeric(10,2), default=0)
    raw_pos_name    = Column(String(200))

class PosItemMapping(Base):
    __tablename__ = 'pos_item_mappings'
    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id  = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    pos_system     = Column(String(30))
    pos_item_name  = Column(String(300), nullable=False)
    menu_item_id   = Column(UUID(as_uuid=True), ForeignKey('menu_items.id'))
    is_ignored     = Column(Boolean, default=False)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
```

## 2.5 TimescaleDB hypertable migration

Generate the migration, then add to the END of `upgrade()` after the CREATE TABLE statements:

```python
op.execute("""
    SELECT create_hypertable('sales_summaries', 'business_date',
        chunk_time_interval => INTERVAL '1 month', if_not_exists => TRUE);
""")
op.execute("""
    SELECT create_hypertable('sales_by_item', 'business_date',
        chunk_time_interval => INTERVAL '1 month', if_not_exists => TRUE);
""")
op.create_index('ix_sales_summaries_rid_date', 'sales_summaries',
                ['restaurant_id','business_date'])
op.create_index('ix_sales_by_item_rid_date', 'sales_by_item',
                ['restaurant_id','business_date'])
```

```bash
alembic revision --autogenerate -m 'initial_schema'
# add the hypertable lines above to the migration's upgrade()
alembic upgrade head
```

---

## Done when

All tables exist in the database (`\dt` in psql shows them) and the two hypertables are registered (check with `SELECT * FROM timescaledb_information.hypertables;`).

## Then

Update checkbox in `CLAUDE.md`, `git commit`, move to `step-03-recipe-engine.md`.
