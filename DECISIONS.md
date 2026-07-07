# Decisions Log

A running record of non-obvious choices made during the build. When Claude Code (or you) makes a decision that future-you might question, write it here with the date and reasoning. This file is how the project remembers *why* things are the way they are across many sessions.

Format: `## YYYY-MM-DD — Short title` then the decision and the reasoning.

---

## Seed decisions (made during planning, before any code)

### Multi-tenant single database, not database-per-restaurant
One PostgreSQL database with `restaurant_id` on every table, scoped at the API auth layer. Database-per-tenant would mean managing hundreds of separate Postgres instances — operationally unworkable at scale. Row-level tenant isolation is the standard SaaS pattern.

### TimescaleDB instead of a separate time-series database
TimescaleDB is a PostgreSQL extension, so we get relational structure and time-series partitioning in one engine. No need to run and sync a separate TSDB. `sales_summaries` and `sales_by_item` are hypertables.

### Online ordering is NOT built natively in Phase 1
We integrate with existing platforms (Toast, DoorDash, Uber Eats) and pull order data back in. A white-label ordering page is a Phase 2 add-on only. Building native ordering means a two-sided network problem (restaurants AND diners) that kills early-stage focus.

### LightGBM, not a neural network, for forecasting
Independent restaurants have small noisy datasets (60–365 daily rows). Gradient-boosted trees train in seconds, don't overfit tiny data the way deep nets do, and give interpretable feature importances. Per-restaurant models beat a single generalized model because patterns are highly location-specific.

### LLM Q&A is structured-context, NOT vector RAG
Our data is structured SQL, not unstructured documents. The pattern is: run SQL queries → assemble a structured context block → pass to Claude → reason over it. The database provides facts; the LLM provides synthesis. Never let the LLM invent numbers.

### Every ingestion path ends in stage → review → confirm
OCR misreads, voice mishears, CSV columns misalign. All automated extraction lands in `staged_ingestions` and the operator confirms before it commits. The commit service reuses the same `process_invoice` / `deplete_batch` functions as manual entry, so there's one path through the system.

---

## Build decisions (add new entries below as you go)

## 2026-06-27 — Python 3.14 instead of 3.12; package versions bumped

The machine has Python 3.14.4 installed; the step file specified 3.12. Rather than install a second interpreter, we bumped all packages to their latest Python-3.14-compatible releases. Specific incompatibilities fixed:
- `psycopg2-binary` 2.9.9 → 2.9.12 (first release with a 3.14 wheel)
- `sqlalchemy` 2.0.30 → 2.0.51 (2.0.30 hit `__firstlineno__` clash introduced in CPython 3.14)
- `alembic` 1.13.1 → 1.18.5 (requires SQLAlchemy ≥ 2.0.36 at this version)
- `pydantic` 2.7.1 → 2.13.4 / `pydantic-settings` 2.2.1 → 2.14.2 (pydantic-core 2.7.x had no 3.14 wheel)
- `pillow` 10.3.0 → ≥12.0.0 (resolved to 12.2.0; first series with 3.14 wheels)
- `fastapi` 0.111.0 → 0.138.1 (required by pydantic 2.13 dependency constraints)
- `numpy` 1.26 → ≥2.0 (resolved to 2.5.0; numpy 1.x never shipped 3.14 wheels)
- `pandas` 2.2.0 → ≥2.2.0 (resolved to 3.0.3)
- `lightgbm` 4.3.0 → ≥4.3.0 (resolved to 4.6.0)
The API surface of all bumped packages is backwards-compatible for the patterns used in this project.

## 2026-06-27 — alembic.ini sqlalchemy.url set to local dev DB

`alembic.ini` has `sqlalchemy.url` set to the local dev connection string (`postgresql://rp_user:localdevpassword@localhost/restaurant_platform`). This is intentional for local dev only — production will override via env var / Secrets Manager. The `.env` file (gitignored) takes precedence at runtime through `app/config.py`.

## 2026-06-27 — Composite PK (id, business_date) on hypertables

TimescaleDB requires every unique constraint (including the primary key) to include the partition column. `sales_summaries` and `sales_by_item` therefore use a composite primary key `(id, business_date)` instead of `id` alone. The ORM models reflect this by marking `business_date` as `primary_key=True` alongside `id`. Neither table is referenced by a foreign key from any other table, so there is no cascade impact. This is the standard TimescaleDB pattern for UUID-keyed hypertables.

## 2026-06-27 — Services normalise IDs to UUID before db.get() and tenant checks

SQLAlchemy's `UUID(as_uuid=True)` columns store Python `uuid.UUID` objects in the identity map. Passing a plain string to `db.get()` or comparing with `!=` against a UUID column always mismatches — `db.get()` misses the identity map and the tenant check `restaurant_id != "string"` always evaluates True. All service functions now run IDs through `_to_uuid()` before lookup and comparison. This is consistent across `inventory_service`, `depletion_service`, and (pre-emptively) any future service that accepts IDs from router path parameters.

## 2026-06-27 — log_waste adds visible warning on below-zero stock

The step file used `max(0, ...)` to clamp stock silently. The hard rule says "do not silently clamp." `log_waste` now logs a WARNING before clamping, consistent with `deplete_from_sale`. The clamping itself is retained so `current_stock` never stores a negative value in the DB; the warning surfaces the data quality issue.

## 2026-06-28 — Replaced passlib with direct bcrypt calls

`passlib` 1.7.4 (last release 2020) is incompatible with `bcrypt` >= 4.0, which removed the `__about__` attribute passlib reads at startup. Since `bcrypt` 5.x is installed for Python 3.14, passlib always errors. Replaced with two thin helpers (`hash_password` / `verify_password`) in `auth.py` that call `bcrypt.hashpw` / `bcrypt.checkpw` directly. Removed `passlib[bcrypt]` from `requirements.txt`; `bcrypt>=5.0.0` remains.

## 2026-06-28 — Pydantic schemas for recipe/sales request bodies (not raw dicts)

The step file suggests raw `dict` request bodies for the first pass. Conventions require Pydantic schemas in `app/schemas/`. Used `MenuItemCreate`, `RecipeLineCreate` (in `schemas/recipe.py`) and `SaleItem`, `SalesBatch` (in `schemas/sales.py`) from the start — avoids a second pass and gives validation for free. `SaleItem`/`SalesBatch` were already Pydantic models in the step file; moved them to the schemas layer to keep routers thin.

## 2026-06-28 — datetime query params must be passed via httpx params dict (not f-string URL)

`+00:00` in ISO datetime strings is decoded as a space when embedded directly in query-string URLs. Pass datetime params via `httpx.get(..., params={...})` so the client URL-encodes the `+` correctly. This applies to any endpoint accepting `datetime` query params.

## 2026-06-28 — Extracted _process_normalized() from ingest_toast_day

The mapping/depletion logic was pulled into a separate sync helper `_process_normalized()` inside `pos_ingestion_service`. This keeps the async HTTP concerns (token + fetch) isolated from the business logic and makes the mapping/depletion path independently testable without needing async mocking of the entire pipeline. `ingest_toast_day` remains async and calls `_process_normalized` after resolving the HTTP calls.

## 2026-06-28 — Celery task uses asyncio.run() per restaurant

`pull_all_toast_restaurants` is a standard synchronous Celery task that calls `asyncio.run(ingest_toast_day(...))` for each restaurant. Each call creates and tears down a fresh event loop. This is correct in a default Celery prefork worker (no running loop), and simpler than configuring Celery's asyncio pool. If the worker count scales significantly, switching to Celery's `asyncio` task class or gathering all restaurant coroutines in one `asyncio.run()` call is a straightforward upgrade.

## 2026-06-28 — mock.patch targets toast_service, not pos_ingestion_service

`ingest_toast_day` imports `get_toast_token` and `fetch_toast_orders` via a deferred local import from `toast_service`. Patches must target `app.services.toast_service.<name>` (where the names live at call time), not `app.services.pos_ingestion_service.<name>` (where they are not module-level attributes).

## 2026-06-28 — JSON columns store native Python objects (never json.dumps)

SQLAlchemy `JSON` columns serialise Python dicts and lists automatically. Calling `json.dumps()` before storing produces a column value that is a JSON string (a string inside JSON), which reads back as a plain string rather than a dict. All ingestion services store native Python objects directly in `extracted_data` and `confidence_scores`. The commit service therefore reads them as dicts/lists without any `json.loads()` call.

## 2026-06-28 — OpenAI client uses lazy init (not module-level)

`openai.OpenAI()` raises at instantiation time if `OPENAI_API_KEY` is not set. Module-level init would break the app import in dev environments without the key. The voice ingestion service uses lazy `_get_whisper()` / `_get_claude()` helpers so the client is only created on first API call. Anthropic's SDK does not raise at init time, but the pattern is applied consistently.

## 2026-06-28 — Email ingestion identifies restaurant by invoice_email_id

The Restaurant model already had an `invoice_email_id` field (String 50). The email webhook routes inbound SendGrid parses to the correct restaurant by matching the local-part of the `To` address against this field. Each restaurant gets a unique short identifier (e.g. `mybistro`) and configures SendGrid to forward `mybistro@parse.<domain>` to the webhook. No schema change needed.

## 2026-06-28 — Commit service sets staged.status before calling sub-service

In `commit_staged_ingestion`, `staged.status = 'confirmed'` is set before calling `_commit_invoice` / `_commit_count` / `_commit_sales`. This means the sub-service's internal `db.commit()` persists the status change atomically with the live data write. A final `db.commit()` is called if the session is still active (safety net for any sub-path that didn't commit).

## 2026-06-28 — Auto-create ingredient when fuzzy match fails

When the commit service finds no fuzzy match (cutoff 0.7) for an extracted ingredient name, it auto-creates the ingredient with the extracted unit and cost=0. This is per conventions.md §ingestion. The new ingredient appears in the operator's catalog immediately and can be priced on the next invoice. The alternative (skipping) would silently lose data from confirmed ingestions.

## 2026-06-28 — TimescaleDB partition indexes stripped from autogenerated migration

`alembic revision --autogenerate` detected the TimescaleDB partition indexes on `sales_by_item` and `sales_summaries` as "removed" (they're not in Base.metadata but exist in the DB). The `drop_index` calls were removed from the migration before running `alembic upgrade head`. Same fix as previous steps.

## 2026-06-28 — food_cost_spike filters menu_item_id IS NOT NULL

The food cost % query only sums rows where `menu_item_id` is set. Unmapped POS items (raw_pos_name rows) have `food_cost = 0` because depletion never ran for them — including them would dilute the true food cost percentage and hide spikes. Only fully-mapped, depleted sales rows are used for the trailing average and today's figure.

## 2026-06-28 — Alert model uses extra_data not metadata for JSON column

SQLAlchemy's `DeclarativeBase` already has a `metadata` class attribute (`MetaData`). Adding a column named `metadata` shadows it at the class level, breaking Alembic and the ORM mapper. The JSON catch-all column is named `extra_data` instead.

## 2026-06-28 — Vite instead of create-react-app

CRA has not received updates since 2022 and is broken with Node 22+. Vite (v5) is the React team's recommended replacement — faster HMR, smaller build output, actively maintained. The resulting project structure and all imported packages (axios, react-query, react-router-dom, Tailwind, Recharts) are identical to what the step file specified.

## 2026-06-28 — Vite dev server runs on port 5173; CORS updated to match

Vite defaults to port 5173, not 3000. Rather than forcing 5173 to 3000 (non-standard), `http://localhost:5173` was added alongside `http://localhost:3000` in `app/main.py` CORS origins. Both ports remain in the allowlist so a CRA fallback on 3000 would still work.

## 2026-06-28 — Three new backend routers for frontend data needs

The five frontend pages required endpoints not yet in the API: ingredient listing (needed by InventoryCount, RecipeBuilder, WasteLog), batch inventory count submission, and waste logging. Added `app/routers/inventory.py` with `ingredients_router` (`/ingredients/`), `counts_router` (`/inventory-counts/`), and `waste_router` (`/waste/`). All three delegate to existing services and follow the same auth/UUID conventions.

## 2026-06-28 — tsconfig noUnusedLocals/noUnusedParameters set to false

Strict unused-variable checking is incompatible with idiomatic React event handlers and query data typed as `any`. Set both flags to false to allow clean builds without fighting TypeScript on scaffolding patterns. The remaining strict flags (strict, isolatedModules, noFallthroughCasesInSwitch) are left enabled.

## 2026-06-28 — Recharts pinned to v2 (deprecation noted)

Step 7 specifies `recharts`. npm resolved to v2.15.4 which is deprecated in favour of v3. Pinned to v2 for now since v3 has a migration guide and the dashboard table doesn't use Recharts yet (charts are a Phase 2 / Step 8 addition). Upgrade to v3 before adding chart components.

## 2026-06-28 — ReviewIngestion.tsx extracted_data fix (5B Part 2)

Step 5B Part 2's `ReviewIngestion.tsx` calls `JSON.parse(staged.extracted_data)`. Our backend stores `extracted_data` as a native JSON column (Python dict), so the API response already delivers a parsed object. The fix for the next session: use `staged.extracted_data` directly, no `JSON.parse`.

## 2026-06-28 — ReviewIngestion uses extracted_data directly (no JSON.parse)

The step file called `JSON.parse(staged.extracted_data)` because it assumed the JSON column was stored as a string. Our backend stores native Python dicts in the `JSON` column, so FastAPI serialises `extracted_data` as a proper JSON object in the API response — the frontend receives it already parsed. Removing `JSON.parse` prevents a runtime error ("unexpected token" when parsing an already-parsed object).

## 2026-06-28 — ReviewIngestion is a page component using useParams, not a prop-based component

The step file defines `ReviewIngestion({ stagedId }: { stagedId: string })` as a component that receives its ID via props. Since it's wired as a page route (`/ingestion/review/:id`), it reads the ID from `useParams<{ id: string }>()` instead. This avoids an awkward wrapper and matches React Router conventions.

## 2026-06-28 — confirm endpoint accepts optional corrected_data body

The ReviewIngestion UI lets operators edit extracted line items before confirming. Those edits must reach the commit service. Updated `POST /ingestion/staged/{id}/confirm` to accept `_ConfirmBody(corrected_data: Any = None)` and pass it through to `commit_staged_ingestion`. When `corrected_data` is None (no edits), the service falls back to `staged.extracted_data` unchanged.

## 2026-06-28 — QuickSalesEntry uses noon UTC for business_date

`new Date('yyyy-MM-dd')` parses as midnight UTC. In timezones behind UTC this can shift the date back by one day when the string is round-tripped. Using `new Date(date + 'T12:00:00Z')` anchors to noon UTC, which is unambiguously within the target calendar date in every timezone from UTC-11 to UTC+11.

## 2026-06-28 — LLM context adds low-stock alerts beyond the step file spec

The step file assembles food-cost summary (7d, 30d) and top-15 items. The service also includes `check_low_stock()` output and unread alert count. These are zero-cost SQL calls that materially improve answer quality — an operator asking "what should I focus on?" gets a complete picture without a second question. Adding them at context-assembly time costs nothing; the LLM is already being called.

## 2026-06-28 — claude-sonnet-4-6 chosen for Q&A (not Opus)

The step file specifies `claude-sonnet-4-6` for structured Q&A. Sonnet is well-suited for reasoning over pre-assembled structured context: it doesn't need deep reasoning, just accurate synthesis of SQL-fetched facts. Keeping Opus for heavier workloads and Sonnet for daily Q&A is an appropriate cost-quality split. The model can be changed per route without structural changes.

## 2026-06-28 — No adaptive thinking on Sonnet Q&A endpoint

Per verified SDK syntax (anthropic 0.112.0): `thinking: {"type": "adaptive"}` is supported on Sonnet 4.6 but not needed here — the context is pre-structured SQL facts, not a reasoning-heavy task. Not setting `thinking` keeps latency and token count low. Add it if operators ask questions that require multi-step inference.

## 2026-06-28 — ANTHROPIC_API_KEY required in .env for LLM service

`app/services/llm_service.py` reads the key via `anthropic.Anthropic()` which checks `ANTHROPIC_API_KEY` at first API call. The key must be added to `backend/.env`: `ANTHROPIC_API_KEY=sk-ant-...`. Without it, `POST /ai/ask` returns 502. Context assembly (SQL queries) is fully functional without the key.

## 2026-07-06 — Inserted Insights Engine (Steps 11–13) and updated CLAUDE.md/conventions.md to as-built state; see step files for scope.

Scaffold update pack applied: CLAUDE.md replaced with version that shows accurate Build Status (Steps 1–7/5B/6/9 complete, 8/10 gated, 11–13 new), Known Caveats section added, and stack corrected to as-built (Python 3.14, Vite on port 5173, dev login). Steps 11–13 step files added to docs/steps/. README.md replaced with scaffold-pack README (contains "how to apply" instructions for this pack). Conventions.md Insights Engine section (derived-not-stored, every insight ends in recommended_action, thresholds in restaurant_settings, divide-by-zero and coverage honesty) folded into conventions.md separately.

## 2026-07-06 — Added depletion_events append-only log table (Step 11)

`deplete_from_sale` only mutated `current_stock` — there was no queryable record of when and how much of each ingredient was consumed. Variance analysis (theoretical vs. actual) requires summing depletion between two inventory count timestamps, which needs a log. Added `DepletionEvent` to `inventory.py` and modified `deplete_from_sale` to insert one row per recipe line per sale. This is append-only and never updated; it gives any future window-based analysis a complete depletion history from the migration date forward.

## 2026-07-06 — restaurant_settings created lazily on first read (Step 11)

Rather than requiring operators to create a settings row before using any insight endpoint, `get_or_create_settings` creates the row with defaults (`target_food_cost_pct=30`, `menu_eng_popularity_factor=0.70`, `par_min_cover_days=4`, `par_max_cover_days=21`) on the first call. This keeps every endpoint self-contained — no setup step needed.

## 2026-07-06 — Variance uses bracketing count pattern, data_gap for missing counts (Step 11)

Opening count = latest count ≤ window_start; closing count = latest count within the window. If either bracket is missing, the ingredient returns `data_gap=True` rather than a partial or incorrect figure. This follows the "coverage honesty" convention — showing a gap is better than showing a wrong number.

## 2026-07-06 — Daypart coverage_pct distinguishes manual vs. timestamped sales (Step 11)

Manual QuickSalesEntry sets business_date to noon UTC (`T12:00:00Z`). POS-ingested sales carry real order timestamps. The daypart aggregator treats rows where `hour==12 and minute==0` as "date-only" (manual) and excludes them from daypart buckets; `coverage_pct` = timestamped/total tells the operator how reliable the daypart chart is. Verified: real-datetime test sales → coverage_pct=1.0; all-manual → coverage_pct=0.0.

## 2026-07-06 — Hand-written Alembic migration (no autogenerate) for Step 11 tables (Step 11)

Used `alembic revision --autogenerate` requires a live DB connection; Docker wasn't running when the migration was authored. Wrote the migration by hand (`c4a1f2b3d5e6_add_insights_tables.py`) targeting `restaurant_settings` and `depletion_events`. Hand-written migrations also avoid the recurring TimescaleDB `drop_index` artifact in autogenerated output. Applied cleanly with no modifications needed.

## 2026-07-06 — Daypart coverage uses noon-UTC heuristic; proper fix deferred to Step 12 (Step 11)

`get_sales_patterns` detects manual (date-only) entries by checking whether `business_date.hour == 12 and business_date.minute == 0`. This works because `QuickSalesEntry.tsx` anchors manual dates to `T12:00:00Z`. It is fragile: a POS order that genuinely arrives at noon UTC is misclassified as manual, and any future ingestion path that sets a different convention will break it silently. The correct fix is an explicit `source` or `has_timestamp` boolean column on `sales_by_item` / `sales_summaries` — to be added alongside the `channel` column in Step 12 when new ingestion sources (delivery platforms, labor imports) are introduced. Until then the heuristic is documented here so the fragility is visible.

**Superseded 2026-07-06 (Step 12):** Coverage now uses `source == 'toast'`. CSV imports set `source='csv'` and are date-only like manual entries — they must not count as timestamped. See Step 12 daypart entry below.

## 2026-07-06 — Daypart coverage switched from noon-UTC heuristic to source=='toast' (Step 12)

`get_sales_patterns` now classifies a `SalesByItem` row as "timestamped" (eligible for daypart bucketing) only when `source == 'toast'`. Manual entries and CSV imports are both date-only and must not count. `source != 'manual'` would wrongly include CSV rows. The only current source that provides real intraday timestamps is Toast. Any future POS integration delivering real timestamps should set `source='<pos_name>'` (not `'manual'` or `'csv'`) and will qualify for daypart analysis automatically.

## 2026-07-06 — commission_rate stored as fraction, not percentage (Step 12)

`channel_fees.commission_rate` is `Numeric(5,4)`, max value 9.9999. Storing a percentage (e.g. 15) overflows. Storing the fraction (0.1500 = 15%) fits within range and matches financial convention. Pydantic validates `0 ≤ rate ≤ 1` at the API layer. All arithmetic uses the fraction directly (`commission = revenue × rate`); displays multiply by 100.

## 2026-07-06 — RevPASH deferred; shipping "revenue per seat per day" instead (Step 12)

True RevPASH (Revenue Per Available Seat Hour) requires `daily_open_hours` per day — a setting that doesn't exist yet. `get_covers_insight` returns `revenue_per_seat_per_day = total_revenue / (seat_count × window_days)` and labels it exactly that. Revenue ÷ (covers × seat_count) is not RevPASH and not meaningful. When `RestaurantSettings.daily_open_hours` is added, replace the denominator with `seat_count × open_hours × window_days` and relabel to RevPASH.

## 2026-07-06 — Prime Cost KPI replaces "Items Tracked" on Dashboard (Step 12)

"Items Tracked" (count of menu items with recent sales) was an operational metric with no actionable interpretation at the dashboard level. Prime Cost % (food + labor as % of revenue) is the most important combined cost signal in foodservice — anything above 62% typically means fixed costs cannot be covered. The card alerts (red) at >62% and shows target "62%". Approved before build and logged in the plan.

## 2026-07-06 — Toast comps/voids not yet auto-imported as SaleAdjustment (Step 12)

The `SaleAdjustment` table and manual entry path are live. Toast's `appliedDiscounts` and `voidedPayments` are not yet parsed into `sale_adjustments` during the nightly pull — the Toast payload taxonomy varies by POS config and requires a sample payload from a real customer to map correctly. When adding: parse `appliedDiscounts[].appliedDiscountReason` → `adjustment_type='comp'` or `'discount'`, set `source='toast'`.

## 2026-07-06 — Weather fetch uses Open-Meteo archive API; no API key required (Step 12)

`fetch_weather_for_restaurant` calls `archive-api.open-meteo.com/v1/archive` (historical daily data, no auth). The nightly Celery task runs at 4:00am UTC — after the Toast pull (3:00am) and alerts (3:30am) — and fetches yesterday's weather for all restaurants with `lat/lon` set. Verification scripts insert `weather_days` rows directly to avoid live HTTP calls in tests. The 1-day lag (fetching yesterday) is acceptable: operators compare weather to prior-day sales patterns, not same-day.

## 2026-07-06 — Channel strings are free-form; QuickSalesEntry dropdown is the canonical set (Step 12)

`channel_fees.channel` and `sales_by_item.channel` are plain `String(30)` — no enum constraint. Fee matching in `get_channel_profitability` is an exact string lookup (`fees.get(channel, 0.0)`). The QuickSalesEntry dropdown (dine_in, takeout, delivery, catering, bar) is the canonical set operators should also use when creating channel fees. A fee created for `'delivery'` matches sales tagged `channel='delivery'` exactly. Future UI for fee management should present the same canonical list or a free-text field with autocomplete from existing fee rows.

## 2026-07-06 — Consolidated DECISIONS.md into root (this file)

docs/DECISIONS.md was created during Step 12 in the mistaken belief that no root DECISIONS.md existed. Root DECISIONS.md is canonical per the scaffold layout. docs/DECISIONS.md has been deleted; its Step 12 entries and improved Step 11 write-ups are merged here.

## 2026-07-06 — BenchmarkStats has no restaurant_id (deliberate Step 13 exception) 

`benchmark_stats` is the one table in the schema with no `restaurant_id`. It stores anonymous cross-restaurant percentiles (p25/p50/p75 + n). Attaching a restaurant_id would either (a) expose which restaurant's data contributed to which percentile (privacy violation) or (b) require a separate fan-out join that defeats the purpose. Each operator sees their own value vs anonymised percentiles — the underlying individual values are never stored or exposed. This is documented in `app/services/benchmark_service.py` and explicitly called out in the hard rule enforcement: n < 5 → row never written.

## 2026-07-06 — Minimum cohort of 5 enforced at write time, not read time (Step 13)

`run_benchmark_computation` checks `len(values) >= 5` before writing a `BenchmarkStats` row. This is earlier than a read-time guard because it eliminates the attack surface entirely — there is no row to query, no endpoint to probe. A read-time check would still persist the data; the write-time guard is the correct layer. `get_benchmarks` will return `benchmarks: []` with a "not enough peer data yet" caveat when no rows exist, matching the graceful empty state in the frontend.

## 2026-07-06 — Price events auto-logged at PATCH time, not during commit service (Step 13)

`MenuPriceEvent` rows are created inside the `PATCH /menu-items/{id}` route handler the moment `menu_price` changes. Alternative considered: a separate event-sourcing step inside `ingestion_commit_service`. Rejected because menu price changes are a deliberate operator action through the API — not a CSV/voice/OCR ingestion. Hooking the PATCH endpoint is the correct layer: explicit, tested, and not subject to ingestion-pipeline variability.

## 2026-07-06 — Benchmark Celery task runs at 4:30am, after weather (Step 13)

Beat schedule order: Toast pull 3:00am → alerts 3:30am → weather 4:00am → benchmarks 4:30am. Benchmarks are last because they call `get_prime_cost` and `get_covers_insight` per restaurant — the most DB-intensive aggregation. Running after Toast (which populates sales data) and weather ensures all inputs are fresh. The 30-minute gap between weather and benchmarks is ample for the weather task to complete even on large restaurant counts.

## 2026-07-06 — Action list drawn from insights at call time, not pre-computed (Step 13)

`get_daily_actions` calls the existing insight services inline (variance, pars, channel, prime cost, etc.). This avoids a separate "actions" precompute table and stays consistent with the Step 11/12 principle of deriving insights at query time. The downside is latency — 7 sub-queries per request. For an operator-facing dashboard that refreshes every 5 minutes, this is acceptable. If p95 exceeds 500ms in production, pre-compute in the nightly benchmark task.

## 2026-07-06 — Action list action for price experiments uses verdict string match (Step 13)

`get_daily_actions` surfaces a price-experiment action only when `verdict == 'volume dropped significantly — consider reverting'`. This is an exact string comparison. The verdict strings are defined in `price_experiment_service.py` and must not be changed without updating the action service. If the verdict set grows, centralise them into a module-level constant dict.

<!-- ## 2026-XX-XX — Title
Decision and reasoning here. -->
