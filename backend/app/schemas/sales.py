from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel

_CHANNELS = Literal['dine_in', 'takeout', 'delivery', 'catering', 'bar']


class SaleItem(BaseModel):
    menu_item_id:  str
    quantity_sold: int
    gross_revenue: float
    channel:       _CHANNELS = 'dine_in'


class SalesBatch(BaseModel):
    business_date: datetime
    items:         list[SaleItem]
    covers:        Optional[int] = None   # guests served this batch; upserted into SalesSummary
