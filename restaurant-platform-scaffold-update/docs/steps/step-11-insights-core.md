# Step 11 — Insights Core (existing data only)

> **⚠ UPDATE — this step was inserted July 2026, separately from the original 10-step plan**, after Steps 1–7, 5B, 6, and 9 were completed. Read `docs/conventions.md` (including its Insights Engine update section) before building.

**Estimated effort:** 10–14 hours. **Prerequisites:** Steps 1–7 complete (they are). **New external inputs required:** none.

## What You're Building

An `insights_service.py` + `/insights/*` router + `InsightsPage.tsx` delivering eight analyses computed entirely from data already in the schema: variance, contribution margin, menu engineering, price inflation & vendor comparison, par optimization, daypart/DOW patterns, cost sensitivity, and break-even. Plus a `restaurant_settings` table for thresholds and fixed costs.

Summarize this plan back before writing code. Build in the order below — each item is independently verifiable.

---

## 11.1 Schema: `restaurant_settings`

One row per restaurant (created lazily with defaults on first read):

```
restaurant_settings
  id UUID PK
  restaurant_id UUID FK, unique, indexed
  monthly_fixed_costs Numeric(12,2) NULL     # rent+salaries+insurance+utilities, operator-entered
  target_food_cost_pct Numeric(5,2) DEFAULT 30.0
  menu_eng_popularity_factor Numeric(4,2) DEFAULT 0.70
  par_min_cover_days Integer DEFAULT 4
  par_max_cover_days Integer DEFAULT 21
  created_at / updated_at
```

Alembic migration; remember to strip spurious hypertable `drop_index` lines. Endpoints: `GET /insights/settings`, `PATCH /insights/settings` (use `model_fields_set`).

## 11.2 Theoretical vs. Actual Variance  ★ the flagship

**Concept.** Between two physical counts of an ingredient: `actual_usage = opening_count + received (invoice lines) − closing_count`. `theoretical_usage = sum of depletion records in the same window`. `variance = actual − theoretical` (positive = unexplained loss). Value at current ingredient cost.

**Service:** `get_variance_report(db, rid, window_days=7) -> list[VarianceRow]`
- For each ingredient with ≥2 counts in/bounding the window: find bracketing counts (opening = latest count ≤ window start, closing = latest count ≤ window end; if either missing → `data_gap`).
- Received = sum of invoice line quantities for that ingredient between the two count timestamps.
- Theoretical = sum of depletion quantities between the two count timestamps (depletion records exist from Step 3; if depletion is only reflected in `current_stock` mutations rather than a log table, ADD a `depletion_events` append-only table now — log each `deplete_from_sale` line — and note in DECISIONS.md; variance then works for all future windows).
- Return per-ingredient: theoretical_qty, actual_qty, variance_qty, variance_value ($, at current unit cost), variance_pct, `recommended_action` (e.g., "investigate: 7.2 lb / $25.20 of Chicken Breast unexplained this week — check portioning and waste logging") when |variance_value| exceeds max($10, 5% of theoretical value).

**Endpoint:** `GET /insights/variance?window_days=7`.

## 11.3 Contribution Margin ($)

`get_contribution_margins(db, rid, window_days=28)` — per menu item: units sold, price, plate_cost (recipe engine), margin_dollars = price − plate_cost, total_margin = margin_dollars × units. Sort by total_margin desc. This powers 11.4.

**Endpoint:** `GET /insights/contribution-margin?window_days=28`.

## 11.4 Menu Engineering 2×2

Using 11.3 rows for the window:
- `popularity_threshold = popularity_factor × (total_units / item_count)` (classic Kasavana-Smith 70% rule; factor from settings).
- `margin_threshold = mean(margin_dollars)` (unit margin, not total).
- Classify: high/high **Star** → "protect & feature"; high pop/low margin **Plowhorse** → "re-portion or nudge price"; low pop/high margin **Puzzle** → "reposition on menu / re-describe"; low/low **Dog** → "candidate to cut".

**Endpoint:** `GET /insights/menu-engineering?window_days=28` → items with quadrant + action + the thresholds used.

## 11.5 Price Inflation & Vendor Comparison

Invoice lines are append-only with unit costs — the history already exists.
- `get_price_trends(db, rid)` — per ingredient: current avg unit cost (last 3 purchases), % change vs 30/60/90d ago; flag > +10%/60d with action listing top-3 affected menu items by margin impact (via recipe lines).
- `get_vendor_comparison(db, rid, ingredient_id)` — per vendor: last price, avg price 90d, purchase count.

**Endpoints:** `GET /insights/price-trends`, `GET /insights/vendor-comparison/{ingredient_id}`.

## 11.6 Par-Level Optimization

`get_par_recommendations(db, rid)` — per ingredient: `daily_velocity` = avg daily depletion (28d). `cover_days = par_level / velocity` (guard zero velocity → `data_gap`). Flag `cover_days < par_min_cover_days` → "par too low — stockout risk; suggest par = velocity × 7" and `cover_days > par_max_cover_days` (perishables) → "par too high — spoilage/cash risk". Include `suggested_par`.

**Endpoint:** `GET /insights/par-recommendations`.

## 11.7 Daypart / Day-of-Week Patterns

Toast-ingested sales carry order timestamps; manual quick-sales are date-only.
- DOW: revenue + units by weekday (28d), index vs. mean ("Friday = 1.8× average").
- Daypart (only rows WITH timestamps): breakfast <11, lunch 11–15, afternoon 15–17, dinner 17–22, late ≥22. Include `coverage_pct` = timestamped_rows/total; render honestly per conventions.

**Endpoint:** `GET /insights/sales-patterns?window_days=28`.

## 11.8 Cost Sensitivity

`get_cost_sensitivity(db, rid, shock_pct=10)` — per ingredient: `exposure = Σ over recipes(qty × unit_cost × shock) × units_sold_28d` = margin dollars lost per 28d if that ingredient rises `shock_pct`%. Rank; top entries get action "most exposed to {ingredient} — consider a hedge item or portion review".

**Endpoint:** `GET /insights/cost-sensitivity?shock_pct=10`.

## 11.9 Break-Even

If `monthly_fixed_costs` set: `daily_breakeven = (monthly_fixed_costs / 30.4) / blended_gross_margin_pct` where blended margin = 1 − blended food cost (30d, from `food_cost_service`). Compare to avg daily revenue (28d) → surplus/shortfall per day. If not set → `data_gap: "enter monthly fixed costs in settings"`.

**Endpoint:** `GET /insights/break-even`.

## 11.10 Frontend — `InsightsPage.tsx` (+ dashboard cards)

- Route `/insights`, nav item "Insights".
- Tabs or stacked cards: Variance (table, red rows over threshold), Menu Engineering (Recharts scatter, quadrant lines at thresholds, colored by quadrant), Margins (bar, $), Price Trends (line + flags), Pars (table with suggested values), Patterns (DOW bar + daypart bar with coverage badge), Sensitivity (ranked bar), Break-even (single KPI vs. actual).
- Every card renders `recommended_action` prominently and exposes the "how computed" inputs on hover/expand.
- Dashboard: add two `KpiCard`s — "Unexplained variance (7d)" and "Break-even vs. actual".

## Verification (throwaway script, then delete)

Seed a temp restaurant: 2 ingredients, counts at T0/T7, invoices in between, recipes, 28d of sales (some timestamped), a price step-up in invoices. Assert: variance math to the cent on a hand-computed case; quadrant assignment for 4 crafted items; inflation flag fires; par flags fire both directions; daypart coverage_pct correct; break-even matches hand calc; **cross-tenant scoping** (second restaurant sees none of it — expect 404/empty). Frontend: `npm run build` → 0 TS errors; browser check with dev login. Clean up seed data, delete the script, tick the Step 11 box in CLAUDE.md, log decisions (esp. if `depletion_events` was added), commit, push.
