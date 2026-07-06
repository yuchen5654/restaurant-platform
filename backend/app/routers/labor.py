from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.auth import get_current_restaurant_id
from app.services import labor_service

router = APIRouter(prefix='/labor', tags=['labor'])


class LaborEntryCreate(BaseModel):
    business_date: datetime
    hours:         float
    labor_cost:    float
    role:          Optional[str] = None
    source:        str = 'manual'


@router.post('/', status_code=201)
def create_labor_entry(
    body: LaborEntryCreate,
    db:   Session = Depends(get_db),
    rid:  str     = Depends(get_current_restaurant_id),
):
    entry = labor_service.create_labor_entry(db, rid, body.model_dump())
    return {'id': str(entry.id)}
