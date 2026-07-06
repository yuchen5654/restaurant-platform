# Architecture & Design Decisions

Non-obvious decisions made during implementation. Include date and reasoning so future sessions can judge edge cases.

---

## Step 11

### 2026-07-02 — Noon-UTC heuristic for sales timestamp coverage (SUPERSEDED by Step 12)

**Decision:** `QuickSalesEntry` records sales at `new Date(date + 'T12:00:00Z')` (noon UTC) to avoid date-boundary drift when a user's local timezone offset would otherwise shift the date. The `get_sales_patterns` coverage calculation originally identified "timestamped" rows as those where `hour != 12 or minute != 0`, treating noon-UTC as the sentinel for "manual/date-only".

**Why fragile:** CSV-imported sales also produce date-only records but with arbitrary times. A real Toast row that happens to arrive at exactly noon UTC would be misclassified.

**Superseded:** Step 12 adds `source` column to `sales_by_item`. Coverage now uses `source == 'toast'`. See Step 12 entry below.

---

### 2026-07-02 — Depletion log table added (Step 11 prerequisite)

**Decision:** Added `depletion_events` append-only table during Step 11 build (not in the original step plan). Without it, the theoretical-vs-actual variance analysis had no record of what *should* have been consumed — it only had the mutated `current_stock` field.

**Why:** Variance = actual usage − theoretical usage. Theoretical requires a per-sale depletion log, not just an aggregate stock level.

---

## Step 12

### 2026-07-06 — Daypart coverage switched to `source == 'toast'`

**Decision:** `get_sales_patterns` counts a `SalesByItem` row as "timestamped" (eligible for daypart bucketing) only when `source == 'toast'`. Manual entries and CSV-imported sales both use date-only business_dates and must not count.

**Why:** CSV sales land with `source='csv'` and are date-only — same as manual. `source != 'manual'` would incorrectly include them. The only source that ships real intraday timestamps is Toast.

**How to apply:** Any future POS integration that provides real timestamps should set `source='<pos_name>'` (not `'manual'` or `'csv'`); it will automatically qualify for daypart analysis.

---

### 2026-07-06 — commission_rate stored as fraction, not percentage

**Decision:** `channel_fees.commission_rate` is `Numeric(5,4)` storing a fraction: `0.1500 = 15%`. Pydantic validators enforce `0 ≤ rate ≤ 1`.

**Why:** `Numeric(5,4)` has max value 9.9999. Storing 15 (percent) would overflow. Storing 0.15 (fraction) is within range and consistent with financial conventions.

**How to apply:** All displays should multiply by 100 to show percentage. All arithmetic (e.g. commission = revenue × rate) uses the fraction directly.

---

### 2026-07-06 — RevPASH deferred; shipping "revenue per seat per day" instead

**Decision:** `get_covers_insight` returns `revenue_per_seat_per_day = total_revenue / (seat_count × window_days)` and labels it exactly that. True RevPASH (Revenue Per Available Seat Hour) requires `daily_open_hours` per day — deferred because that setting doesn't exist yet.

**Why:** Revenue ÷ (covers × seat_count) is not RevPASH and is not meaningful. Revenue ÷ seat_count (daily average) is a useful proxy and clearly labeled.

**How to apply:** When `RestaurantSettings.daily_open_hours` is added (future step), replace the denominator with `seat_count × open_hours × window_days` and relabel to RevPASH.

---

### 2026-07-06 — Prime Cost KPI replaces "Items Tracked" on Dashboard

**Decision:** The Dashboard's fourth KPI card was "Items Tracked" (count of menu items with sales in 30d). Replaced with "Prime Cost %" (food cost + labor cost as % of revenue, 28d window).

**Why:** "Items Tracked" is an operational metric with no actionable interpretation on the dashboard. Prime Cost is the most important combined cost metric in foodservice; anything above 62% typically indicates the business cannot cover fixed costs and profit. Flagging it on the dashboard gives operators an immediate signal.

**How to apply:** The card alerts (red) when `prime_cost_pct > 62`. Target shown as "62%".

---

### 2026-07-06 — Toast comps/voids not yet auto-imported as SaleAdjustment

**Decision:** Toast's `appliedDiscounts` and `voidedPayments` fields are not yet parsed into `sale_adjustments` during the nightly Toast pull. The `SaleAdjustment` table and `AdjustmentsTab` are built; manual entry and CSV ingestion work. Toast auto-import is deferred.

**Why:** The Toast pull currently ingests order-level totals into `sales_summaries`. Mapping per-check discounts/voids to `sale_adjustments` requires understanding Toast's discount taxonomy (which varies by POS config). Shipping the table and manual path first; auto-import can be added when a real Toast customer provides a sample payload.

**How to apply:** When adding Toast comp/void ingestion, parse `appliedDiscounts[].appliedDiscountReason` and map to `adjustment_type` = `'comp'` or `'discount'`; set `source='toast'`.

---

### 2026-07-06 — Weather fetch uses Open-Meteo archive API; no key required

**Decision:** `fetch_weather_for_restaurant` calls `archive-api.open-meteo.com/v1/archive` (historical data, no API key). The nightly Celery task fetches yesterday's weather for restaurants with lat/lon set in `RestaurantSettings`. Verification scripts insert `weather_days` rows directly — no live HTTP calls in tests.

**Why:** Open-Meteo's archive API is free and keyless for non-commercial use. The 1-day lag (fetching yesterday) is acceptable — operators compare weather to the prior day's sales pattern.

---
