import uuid
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.adjustments import SaleAdjustment
from app.routers.auth import get_current_restaurant_id

router = APIRouter(prefix='/adjustments', tags=['adjustments'])


class AdjustmentCreate(BaseModel):
    business_date:   datetime
    adjustment_type: Literal['comp', 'void', 'discount']
    amount:          float
    employee_str:    Optional[str] = None
    daypart:         Optional[str] = None
    notes:           Optional[str] = None
    source:          str = 'manual'


@router.post('/', status_code=201)
def create_adjustment(
    body: AdjustmentCreate,
    db:   Session = Depends(get_db),
    rid:  str     = Depends(get_current_restaurant_id),
):
    adj = SaleAdjustment(
        restaurant_id   = uuid.UUID(rid),
        business_date   = body.business_date,
        adjustment_type = body.adjustment_type,
        amount          = body.amount,
        employee_str    = body.employee_str,
        daypart         = body.daypart,
        notes           = body.notes,
        source          = body.source,
    )
    db.add(adj)
    db.commit()
    db.refresh(adj)
    return {'id': str(adj.id)}
