# Step 12 — Insights Requiring New Inputs

> **⚠ UPDATE — inserted July 2026, separately from the original 10-step plan.** Prerequisite: Step 11 complete. Read `docs/conventions.md` incl. the Insights update section.

**Estimated effort:** 12–16 hours. Each sub-part is independent — they can be built and verified in any order, one session each if preferred.

## What You're Building

The inputs (and the insights they unlock) that Step 11 couldn't reach: labor → prime cost; sales channels → channel profitability; covers → average check/RevPASH/per-guest consumption; waste reasons → decomposition; Toast comp/void fields → leak detection; weather → overlays. Plus a `restaurant_type` field that toggles format-specific insight cards.

---

## 12.1 Labor → Prime Cost (highest value here)

**Schema:** `labor_entries` (id, restaurant_id, business_date, hours Numeric(8,2), labor_cost Numeric(10,2), role String NULL, source Enum[manual,csv], created_at). Append-only.

**Ingestion:** reuse Step 5B's CSV column-mapper flow (a new `ingestion_type='labor'` in staged ingestions; map columns → date/hours/cost; stage → review → commit). Plus a simple manual `POST /labor/`.

**Insights (`insights_service`):**
- `labor_pct` = labor cost / revenue (window).
- `prime_cost_pct` = (food cost $ + labor $) / revenue — the headline. Action if > 62%: "prime cost above healthy range — biggest lever: {food|labor} at X%".
- `sales_per_labor_hour` = revenue / hours, by DOW.

**Endpoints:** `GET /insights/prime-cost?window_days=28`. **Frontend:** Prime Cost KPI on Dashboard (replaces nothing — add), labor CSV import via existing Ingestion Hub, Labor card on Insights page.

## 12.2 Sales Channels → Channel Profitability

**Schema:** `channel` Enum on sales rows (dine_in, takeout, delivery_doordash, delivery_ubereats, delivery_grubhub, other) DEFAULT dine_in; `channel_fees` table (restaurant_id, channel, commission_pct). Toast orders carry dining option/source — map it during POS ingestion; QuickSalesEntry gets a channel dropdown.

**Packaging cost:** model as channel-specific recipe lines — add `channel` NULL column to `recipe_lines`; NULL = all channels; a line with channel='delivery_*' (e.g., container, bag) costs only on those channels. Plate cost function gains an optional channel arg.

**Insight:** per channel: revenue, food+packaging cost, commission (revenue × pct), net contribution $ and per-order. Action when a channel's per-order contribution < $0: "items sold via {channel} lose ${x}/order after commission — raise delivery menu prices or trim the delivery menu". Also monthly commission burden total.

**Endpoint:** `GET /insights/channel-profitability?window_days=28`.

## 12.3 Covers (guest counts)

`covers Integer NULL` on `sales_summaries`. Toast provides guest counts; QuickSalesEntry gets an optional field. Unlocks: average check (revenue/covers), RevPASH later (needs seats in settings — add `seat_count` to restaurant_settings), and per-guest consumption for buffet mode (theoretical depletion value ÷ covers). Include coverage_pct.

## 12.4 Waste Reason Codes → Decomposition

Extend existing waste endpoint/model with `reason Enum(spoilage, prep, plate, error)` (required going forward; old rows NULL → "unclassified"). Insight: waste $ by reason (28d) with per-reason actions (spoilage→check pars/FIFO; prep→yield review; plate→portion sizes; error→remake tracking).

## 12.5 Comps / Voids / Discounts (Toast-gated)

Extend POS ingestion to capture void/comp/discount amounts + employee + time from Toast payloads into a `sale_adjustments` append-only table. **Standing caveat:** current Toast parsing is mock-verified — before building this, print one REAL order payload and confirm field names; log findings in DECISIONS.md. Insight: adjustments by employee/shift/daypart vs. baseline; flag > 3× baseline. If real Toast credentials are still unavailable, build the table + report against seeded data and mark the ingestion TODO.

## 12.6 Weather Overlay

Nightly Celery task fetches yesterday's weather (Open-Meteo — no API key) for the restaurant's lat/lon (add to restaurant_settings) into `weather_days` (restaurant_id, business_date, precip_mm, tmax, tmin). Join into `/insights/sales-patterns` response ("rainy days average −12%"). Purely additive.

## 12.7 `restaurant_type` → Format Modules

`restaurant_type Enum(dine_in, takeout_delivery, qsr, buffet_ayce, cafe, bar, other)` on restaurant_settings. Frontend: InsightsPage renders format-specific cards conditionally — dine_in: RevPASH + average check; takeout_delivery: channel profitability front-and-center; buffet_ayce: per-guest consumption + pricing adequacy (guest cost vs. price by daypart); bar: variance card relabeled "pour cost & shrinkage"; qsr: patterns emphasized. No forked logic — same services, conditional presentation.

## Verification

Throwaway script per sub-part (seed → assert → clean): prime cost hand-check; channel report with a crafted losing delivery item incl. packaging line + commission; waste decomposition sums; adjustments baseline flag; weather join present. Cross-tenant scoping on every new endpoint. `npm run build` 0 TS errors + browser check. Update CLAUDE.md checkbox, DECISIONS.md, commit, push.
