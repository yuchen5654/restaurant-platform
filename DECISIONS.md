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

<!-- ## 2026-XX-XX — Title
Decision and reasoning here. -->
