from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.auth import get_current_restaurant_id
from app.schemas.insights import (
    SettingsRead, SettingsPatch,
    VarianceRow, ContributionMarginRow, MenuEngResponse, MenuEngRow,
    PriceTrendRow, VendorCompareRow, ParRecommendationRow,
    SalesPatternsResponse, SensitivityRow, BreakEvenResponse,
    PrimeCostResponse, ChannelProfitabilityRow, CoversResponse,
    WasteDecompRow, AdjustmentReportRow,
    PriceExperimentRow, BenchmarkResponse, BenchmarkMetricRow,
    ActionItem, DailyActionsResponse,
)
from app.services import insights_service as svc
from app.services import labor_service, channel_service, waste_decomposition_service
from app.services import price_experiment_service, benchmark_service, action_service

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


# 12.1 Prime Cost
@router.get('/prime-cost', response_model=PrimeCostResponse)
def prime_cost(
    window_days: int = Query(28, ge=1, le=365),
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    return labor_service.get_prime_cost(db, rid, window_days)


# 12.2 Channel Profitability
@router.get('/channel-profitability', response_model=list[ChannelProfitabilityRow])
def channel_profitability(
    window_days: int = Query(28, ge=1, le=365),
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    return channel_service.get_channel_profitability(db, rid, window_days)


# 12.3 Covers / Revenue-per-Seat
@router.get('/covers', response_model=CoversResponse)
def covers(
    window_days: int = Query(28, ge=1, le=365),
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    return svc.get_covers_insight(db, rid, window_days)


# 12.4 Waste Decomposition
@router.get('/waste-decomposition', response_model=list[WasteDecompRow])
def waste_decomposition(
    window_days: int = Query(28, ge=1, le=365),
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    return waste_decomposition_service.get_waste_decomposition(db, rid, window_days)


# 12.5 Adjustment Report
@router.get('/adjustments', response_model=list[AdjustmentReportRow])
def adjustment_report(
    window_days: int = Query(28, ge=1, le=365),
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    return svc.get_adjustment_report(db, rid, window_days)


# 13.1 Peer Benchmarks
@router.get('/benchmarks', response_model=BenchmarkResponse)
def benchmarks(
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    result = benchmark_service.get_benchmarks(db, rid)
    return BenchmarkResponse(
        own        = result['own'],
        benchmarks = [BenchmarkMetricRow(**r) for r in result['benchmarks']],
        cohort     = result['cohort'],
        stat_date  = result['stat_date'],
        caveat     = result['caveat'],
    )


# 13.2 Price Experiments
@router.get('/price-experiments', response_model=list[PriceExperimentRow])
def price_experiments(
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    return price_experiment_service.get_price_experiments(db, rid)


# 13.4 Daily Actions
@router.get('/actions', response_model=DailyActionsResponse)
def daily_actions(
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    actions = action_service.get_daily_actions(db, rid)
    return DailyActionsResponse(
        actions   = [ActionItem(**a) for a in actions],
        empty_msg = action_service._EMPTY_MSG if not actions else None,
    )
