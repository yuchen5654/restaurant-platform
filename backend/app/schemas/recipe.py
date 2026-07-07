from decimal import Decimal
from typing import Optional
from pydantic import BaseModel


class MenuItemCreate(BaseModel):
    name: str
    category: Optional[str] = None
    menu_price: Decimal
    pos_name: Optional[str] = None
    pos_item_id: Optional[str] = None


class MenuItemPatch(BaseModel):
    name:       Optional[str]     = None
    category:   Optional[str]     = None
    menu_price: Optional[Decimal] = None
    is_active:  Optional[bool]    = None


class RecipeLineCreate(BaseModel):
    ingredient_id: str
    quantity: Decimal
    unit: str
    notes: Optional[str] = None
