# Step 13 — Network & Action Layer

> **⚠ UPDATE — inserted July 2026, separately from the original 10-step plan.** Prerequisites: Step 11 complete; Step 12 helpful but only 13.1 depends on it loosely. Read `docs/conventions.md` incl. the Insights update section.

**Estimated effort:** 10–14 hours. This step turns insights into (a) the multi-tenant moat and (b) daily decisions.

## What You're Building

Anonymized peer benchmarking (privacy-ruled nightly aggregation), price test-and-learn event tracking, alert *explanations*, and the Daily Action List — the "decisions, not dashboards" surface.

---

## 13.1 Peer Benchmarking (the moat)

**Schema:** `benchmark_stats` — the ONE deliberate precompute table (see conventions): `metric` (food_cost_pct, prime_cost_pct, avg_check, waste_pct_of_cogs, …), `cohort` (restaurant_type or 'all'), `stat_date`, `p25/p50/p75 Numeric`, `n Integer`. **No restaurant_id — this table is intentionally cross-tenant and anonymous.**

**Nightly Celery task** `compute_benchmarks`: for each metric × cohort, compute each restaurant's 28d value via existing services, then store ONLY percentiles + n. **Minimum-cohort rule (hard):** if n < 5, do not write the row. Never store or expose per-restaurant values.

**Endpoint:** `GET /insights/benchmarks` — the caller's own 28d values vs. their cohort's p25/p50/p75 (+ 'all' fallback if their cohort has no row). Response includes n and a plain caveat when only 'all' is available. Action strings like "your food cost (31.4%) is above the 75th percentile of comparable operators (29.8%)".

**Frontend:** Benchmarks card; renders a "not enough peer data yet" state gracefully (expected until multiple live tenants exist — build now, shine later).

## 13.2 Price Test-and-Learn

**Schema:** `menu_price_events` (restaurant_id, menu_item_id, old_price, new_price, changed_at). **Auto-log**: hook the menu-item PATCH service — any price change appends an event (no operator action needed).

**Insight:** `GET /insights/price-experiments` — per event older than 14d: units/day and margin $/day for up to 28d before vs. after (clamped by neighboring events), % deltas, verdict string: margin$ up → "the raise worked"; units down > 15% AND margin$ down → "consider reverting". Include both windows' raw numbers per conventions.

**Frontend:** Price Experiments card listing events with before/after mini-bars + verdict.

## 13.3 Alert Explanations

Extend the alert engine (Step 6): when `check_food_cost_spike` fires, attach top drivers — computed by simple decomposition, **rules not ML**:
- price-driven: ingredients whose current avg unit cost > 28d avg (weighted by usage share of the day's theoretical cost);
- mix-driven: high-food-cost items' share of units today vs. 28d norm;
- adjustment-driven (if 12.5 built): comps/voids today vs. baseline.
Store as `explanation JSON` on the alert; render as sub-bullets under the dashboard alert banner ("driven by: chicken +14% price; burger mix 31% vs 24% norm").

## 13.4 Daily Action List (the endgame surface)

**Service:** `get_daily_actions(db, rid)` assembles, in priority order, deduped `Action` items (`severity, text, source_insight, link_route`) from: unread high alerts (with 13.3 explanations) → variance over threshold → par stockout risks ("order 10 lb chicken — 2 days cover left") → losing channels (12.2) → price-experiment verdicts ready → prime cost over range (12.1) → menu-engineering Dogs older than 60d. Cap 7 items; if none: "No actions needed — all metrics in range." (Never invent busywork.)

**Endpoint:** `GET /insights/actions`. **Frontend:** the FIRST card on `Dashboard.tsx` — "Today's actions" — each row linking to its insight tab. This card is the product thesis in UI form.

**(Post-Step-8 hook, do not build now):** when forecasting exists, prepend prep/order suggestions derived from predicted demand. Leave a commented TODO.

## Verification

Seed TWO cohort restaurants + assert min-cohort rule (n<5 → no row; then seed to 5 with distinct values → percentiles correct; each restaurant sees only own-vs-percentile, never another's value). Price event: seed sales before/after a PATCH-triggered event → verdict math hand-checked. Explanation: engineer a price-driven spike → driver attribution names the right ingredient. Actions: seed conditions for 3 sources → ordered, deduped, capped list; empty state message when clean. Cross-tenant scoping everywhere. `npm run build` 0 TS errors + browser check. Update CLAUDE.md, DECISIONS.md, commit, push.
