from datetime import datetime
from pydantic import BaseModel


class SaleItem(BaseModel):
    menu_item_id: str
    quantity_sold: int
    gross_revenue: float
    channel: str = 'dine_in'


class SalesBatch(BaseModel):
    business_date: datetime
    items: list[SaleItem]
