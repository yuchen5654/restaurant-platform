from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.auth import get_current_restaurant_id
from app.schemas.insights import (
    SettingsRead, SettingsPatch,
    VarianceRow, ContributionMarginRow, MenuEngResponse, MenuEngRow,
    PriceTrendRow, VendorCompareRow, ParRecommendationRow,
    SalesPatternsResponse, SensitivityRow, BreakEvenResponse,
)
from app.services import insights_service as svc

router = APIRouter(prefix='/insights', tags=['insights'])


# 11.1 Settings
@router.get('/settings', response_model=SettingsRead)
def get_settings(db: Session = Depends(get_db), rid: str = Depends(get_current_restaurant_id)):
    return svc.get_or_create_settings(db, rid)


@router.patch('/settings', response_model=SettingsRead)
def patch_settings(
    body: SettingsPatch,
    db:   Session = Depends(get_db),
    rid:  str     = Depends(get_current_restaurant_id),
):
    fields = {k: v for k, v in body.model_dump().items() if k in body.model_fields_set}
    return svc.update_settings(db, rid, fields)


# 11.2 Variance
@router.get('/variance', response_model=list[VarianceRow])
def variance(
    window_days: int = Query(7, ge=1, le=365),
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    return svc.get_variance_report(db, rid, window_days)


# 11.3 Contribution Margin
@router.get('/contribution-margin', response_model=list[ContributionMarginRow])
def contribution_margin(
    window_days: int = Query(28, ge=1, le=365),
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    return svc.get_contribution_margins(db, rid, window_days)


# 11.4 Menu Engineering
@router.get('/menu-engineering', response_model=MenuEngResponse)
def menu_engineering(
    window_days: int = Query(28, ge=1, le=365),
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    result = svc.get_menu_engineering(db, rid, window_days)
    return MenuEngResponse(
        items=[MenuEngRow(**i) for i in result['items']],
        popularity_threshold=result['popularity_threshold'],
        margin_threshold=result['margin_threshold'],
    )


# 11.5 Price Trends
@router.get('/price-trends', response_model=list[PriceTrendRow])
def price_trends(
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    return svc.get_price_trends(db, rid)


# 11.5 Vendor Comparison
@router.get('/vendor-comparison/{ingredient_id}', response_model=list[VendorCompareRow])
def vendor_comparison(
    ingredient_id: str,
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    return svc.get_vendor_comparison(db, rid, ingredient_id)


# 11.6 Par Recommendations
@router.get('/par-recommendations', response_model=list[ParRecommendationRow])
def par_recommendations(
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    return svc.get_par_recommendations(db, rid)


# 11.7 Sales Patterns
@router.get('/sales-patterns', response_model=SalesPatternsResponse)
def sales_patterns(
    window_days: int = Query(28, ge=1, le=365),
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    return svc.get_sales_patterns(db, rid, window_days)


# 11.8 Cost Sensitivity
@router.get('/cost-sensitivity', response_model=list[SensitivityRow])
def cost_sensitivity(
    shock_pct: float = Query(10.0, ge=1.0, le=100.0),
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    return svc.get_cost_sensitivity(db, rid, shock_pct)


# 11.9 Break-Even
@router.get('/break-even', response_model=BreakEvenResponse)
def break_even(
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    return svc.get_break_even(db, rid)
