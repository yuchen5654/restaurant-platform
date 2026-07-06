from typing import Optional
from pydantic import BaseModel


class SettingsRead(BaseModel):
    monthly_fixed_costs:        Optional[float]
    target_food_cost_pct:       float
    menu_eng_popularity_factor: float
    par_min_cover_days:         int
    par_max_cover_days:         int

    class Config:
        from_attributes = True


class SettingsPatch(BaseModel):
    monthly_fixed_costs:        Optional[float] = None
    target_food_cost_pct:       Optional[float] = None
    menu_eng_popularity_factor: Optional[float] = None
    par_min_cover_days:         Optional[int]   = None
    par_max_cover_days:         Optional[int]   = None


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


class SalesPatternsResponse(BaseModel):
    dow:          list[DowRow]
    daypart:      list[DaypartRow]
    coverage_pct: float   # fraction of sales rows with timestamps


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
