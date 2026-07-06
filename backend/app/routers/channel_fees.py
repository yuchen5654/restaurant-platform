from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.auth import get_current_restaurant_id
from app.services import channel_service

router = APIRouter(prefix='/channel-fees', tags=['channel-fees'])


class ChannelFeeCreate(BaseModel):
    channel:         str
    commission_rate: float

    @field_validator('commission_rate')
    @classmethod
    def _validate_rate(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError('commission_rate must be 0–1 (fraction, e.g. 0.15 = 15%)')
        return v


class ChannelFeePatch(BaseModel):
    commission_rate: float

    @field_validator('commission_rate')
    @classmethod
    def _validate_rate(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError('commission_rate must be 0–1 (fraction, e.g. 0.15 = 15%)')
        return v


def _fee_out(f) -> dict:
    return {'id': str(f.id), 'channel': f.channel, 'commission_rate': float(f.commission_rate)}


@router.get('/')
def list_fees(db: Session = Depends(get_db), rid: str = Depends(get_current_restaurant_id)):
    return [_fee_out(f) for f in channel_service.get_channel_fees(db, rid)]


@router.post('/', status_code=201)
def create_fee(
    body: ChannelFeeCreate,
    db:   Session = Depends(get_db),
    rid:  str     = Depends(get_current_restaurant_id),
):
    fee = channel_service.create_channel_fee(db, rid, body.channel, body.commission_rate)
    return _fee_out(fee)


@router.patch('/{fee_id}')
def patch_fee(
    fee_id: str,
    body:   ChannelFeePatch,
    db:     Session = Depends(get_db),
    rid:    str     = Depends(get_current_restaurant_id),
):
    fee = channel_service.update_channel_fee(db, rid, fee_id, body.commission_rate)
    if not fee:
        raise HTTPException(status_code=404, detail='Channel fee not found')
    return _fee_out(fee)
