from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.routers.auth import get_current_restaurant_id
from app.schemas.sales import SalesBatch
from app.services.depletion_service import deplete_batch
from app.services.food_cost_service import get_food_cost_summary, get_item_profitability

router = APIRouter(prefix='/sales', tags=['sales'])


@router.post('/record-batch', status_code=201)
def record_batch(
    batch: SalesBatch,
    db: Session = Depends(get_db),
    rid: str = Depends(get_current_restaurant_id),
):
    sales = [
        {'menu_item_id': i.menu_item_id, 'quantity': i.quantity_sold, 'revenue': i.gross_revenue}
        for i in batch.items
    ]
    records = deplete_batch(db, rid, sales, batch.business_date)
    return {'recorded': len(records), 'business_date': batch.business_date.isoformat()}


@router.get('/food-cost')
def food_cost(
    date_from: datetime,
    date_to: datetime,
    db: Session = Depends(get_db),
    rid: str = Depends(get_current_restaurant_id),
):
    return get_food_cost_summary(db, rid, date_from, date_to)


@router.get('/item-profitability')
def profitability(
    date_from: datetime,
    date_to: datetime,
    limit: int = 20,
    db: Session = Depends(get_db),
    rid: str = Depends(get_current_restaurant_id),
):
    return get_item_profitability(db, rid, date_from, date_to, limit)
