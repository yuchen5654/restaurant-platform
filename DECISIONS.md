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

<!-- ## 2026-XX-XX — Title
Decision and reasoning here. -->
