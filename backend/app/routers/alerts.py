import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.alerts import Alert
from app.routers.auth import get_current_restaurant_id
from app.schemas.alerts import AlertOut

router = APIRouter(prefix='/alerts', tags=['alerts'])


def _to_uuid(val) -> _uuid.UUID:
    return val if isinstance(val, _uuid.UUID) else _uuid.UUID(str(val))


@router.get('', response_model=list[AlertOut])
def list_alerts(
    unread_only: bool    = True,
    limit:       int     = 50,
    db:          Session = Depends(get_db),
    rid:         str     = Depends(get_current_restaurant_id),
):
    q = db.query(Alert).filter(Alert.restaurant_id == _to_uuid(rid))
    if unread_only:
        q = q.filter(Alert.is_read.is_(False))
    return q.order_by(Alert.created_at.desc()).limit(limit).all()


@router.post('/{alert_id}/read', response_model=AlertOut)
def mark_read(
    alert_id: str,
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    alert = db.get(Alert, _to_uuid(alert_id))
    if not alert or alert.restaurant_id != _to_uuid(rid):
        raise HTTPException(404)
    alert.is_read = True
    db.commit()
    db.refresh(alert)
    return alert
