from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base


class MenuItem(Base):
    __tablename__ = 'menu_items'

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    name          = Column(String(200), nullable=False)
    category      = Column(String(100))
    menu_price    = Column(Numeric(8, 2), nullable=False)
    is_active     = Column(Boolean, default=True)
    pos_name      = Column(String(200))
    pos_item_id   = Column(String(100))
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    restaurant   = relationship('Restaurant', back_populates='menu_items')
    recipe_lines = relationship('RecipeLine', back_populates='menu_item',
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
    quantity      = Column(Numeric(10, 4), nullable=False)
    unit          = Column(String(20), nullable=False)
    channel       = Column(String(30), nullable=True)   # NULL = all channels
    notes         = Column(Text)

    menu_item  = relationship('MenuItem', back_populates='recipe_lines')
    ingredient = relationship('Ingredient', back_populates='recipe_lines')

    @property
    def line_cost(self):
        if self.ingredient and self.ingredient.current_cost_per_unit:
            return float(self.quantity) * float(self.ingredient.current_cost_per_unit)
        return None
