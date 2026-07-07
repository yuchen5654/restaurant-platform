from typing import Optional
from pydantic import BaseModel


class SettingsRead(BaseModel):
    monthly_fixed_costs:        Optional[float]
    target_food_cost_pct:       float
    menu_eng_popularity_factor: float
    par_min_cover_days:         int
    par_max_cover_days:         int
    seat_count:                 Optional[int]
    lat:                        Optional[float]
    lon:                        Optional[float]
    restaurant_type:            Optional[str]

    class Config:
        from_attributes = True


class SettingsPatch(BaseModel):
    monthly_fixed_costs:        Optional[float] = None
    target_food_cost_pct:       Optional[float] = None
    menu_eng_popularity_factor: Optional[float] = None
    par_min_cover_days:         Optional[int]   = None
    par_max_cover_days:         Optional[int]   = None
    seat_count:                 Optional[int]   = None
    lat:                        Optional[float] = None
    lon:                        Optional[float] = None
    restaurant_type:            Optional[str]   = None


class VarianceRow(BaseModel):
    ingredient_id:      str
    ingredient_name:    str
    unit:               str
    theoretical_qty:    Optional[float]
    actual_qty:         Optional[float]
    variance_qty:       Optional[float]
    variance_value:     Optional[float]
    variance_pct:       Optional[float]
    data_gap:           bool
    recommended_action: Optional[str]


class ContributionMarginRow(BaseModel):
    menu_item_id:   str
    name:           str
    category:       Optional[str]
    units_sold:     int
    price:          float
    plate_cost:     float
    margin_dollars: float
    total_margin:   float


class MenuEngRow(BaseModel):
    menu_item_id:       str
    name:               str
    category:           Optional[str]
    units_sold:         int
    margin_dollars:     float
    quadrant:           str   # Star | Plowhorse | Puzzle | Dog
    recommended_action: str


class MenuEngResponse(BaseModel):
    items:                list[MenuEngRow]
    popularity_threshold: float
    margin_threshold:     float


class PriceTrendRow(BaseModel):
    ingredient_id:      str
    ingredient_name:    str
    current_avg_cost:   Optional[float]
    change_30d_pct:     Optional[float]
    change_60d_pct:     Optional[float]
    change_90d_pct:     Optional[float]
    flag:               bool
    top_affected_items: list[str]
    recommended_action: Optional[str]


class VendorCompareRow(BaseModel):
    vendor_id:      str
    vendor_name:    str
    last_price:     float
    avg_price_90d:  float
    purchase_count: int


class ParRecommendationRow(BaseModel):
    ingredient_id:      str
    ingredient_name:    str
    unit:               str
    current_par:        Optional[float]
    daily_velocity:     Optional[float]
    cover_days:         Optional[float]
    suggested_par:      Optional[float]
    data_gap:           bool
    recommended_action: Optional[str]


class DowRow(BaseModel):
    weekday:     int    # 0=Mon … 6=Sun
    weekday_name: str
    revenue:     float
    units:       int
    index:       float  # vs mean


class DaypartRow(BaseModel):
    daypart:      str
    revenue:      float
    units:        int


class WeatherRow(BaseModel):
    business_date: str
    precip_mm:     Optional[float]
    tmax:          Optional[float]
    tmin:          Optional[float]


class SalesPatternsResponse(BaseModel):
    dow:          list[DowRow]
    daypart:      list[DaypartRow]
    coverage_pct: float   # fraction of Toast-sourced rows (has real timestamps)
    weather:      list[WeatherRow] = []


class SensitivityRow(BaseModel):
    ingredient_id:      str
    ingredient_name:    str
    exposure_dollars:   float
    recommended_action: str


class BreakEvenResponse(BaseModel):
    daily_breakeven:    Optional[float]
    avg_daily_revenue:  Optional[float]
    daily_surplus:      Optional[float]
    data_gap:           Optional[str]


# ---------------------------------------------------------------------------
# Step 12 schemas
# ---------------------------------------------------------------------------

class PrimeCostDowRow(BaseModel):
    weekday:              int
    weekday_name:         str
    sales_per_labor_hour: Optional[float]


class PrimeCostResponse(BaseModel):
    food_cost_pct:            Optional[float]
    labor_pct:                Optional[float]
    prime_cost_pct:           Optional[float]
    flag_over_62:             bool
    sales_per_labor_hour_by_dow: list[PrimeCostDowRow]
    data_gap:                 Optional[str]


class ChannelProfitabilityRow(BaseModel):
    channel:          str
    revenue:          float
    food_cost:        float
    commission:       float
    net_contribution: float
    per_order_net:    float
    action:           Optional[str]


class CoversResponse(BaseModel):
    avg_check:               Optional[float]
    revenue_per_seat_per_day: Optional[float]
    seat_count:              Optional[int]
    data_gap:                Optional[str]


class WasteDecompRow(BaseModel):
    reason:              str
    waste_dollars:       float
    waste_qty:           float
    recommended_action:  Optional[str]


class AdjustmentReportRow(BaseModel):
    adjustment_type:     str
    total_amount:        float
    count:               int
    pct_of_revenue:      Optional[float]
    flag_high:           bool
    recommended_action:  Optional[str]


# ---------------------------------------------------------------------------
# Step 13 schemas
# ---------------------------------------------------------------------------

class PriceExperimentRow(BaseModel):
    event_id:              str
    menu_item_id:          str
    item_name:             str
    old_price:             float
    new_price:             float
    price_change_pct:      Optional[float]
    changed_at:            str
    before_days:           int
    after_days:            int
    before_units_per_day:  float
    after_units_per_day:   float
    units_delta_pct:       Optional[float]
    before_margin_per_day: float
    after_margin_per_day:  float
    margin_delta_pct:      Optional[float]
    verdict:               str


class BenchmarkMetricRow(BaseModel):
    metric:      str
    own_value:   Optional[float]
    p25:         Optional[float]
    p50:         Optional[float]
    p75:         Optional[float]
    n:           Optional[int]
    cohort_used: Optional[str]


class BenchmarkResponse(BaseModel):
    own:        dict
    benchmarks: list[BenchmarkMetricRow]
    cohort:     Optional[str]
    stat_date:  Optional[str]
    caveat:     str


class ActionItem(BaseModel):
    severity:        str   # high | medium | low
    text:            str
    source_insight:  str
    link_route:      str


class DailyActionsResponse(BaseModel):
    actions:    list[ActionItem]
    empty_msg:  Optional[str]  # set when actions is empty
