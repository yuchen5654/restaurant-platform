# Conventions

Read this before writing any code. These are the naming, structure, and pattern rules that keep the codebase consistent across many build sessions.

---

## Directory layout

```
restaurant-platform/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI entry point, router registration
│   │   ├── config.py          # pydantic-settings, reads .env
│   │   ├── database.py        # engine, SessionLocal, get_db, Base
│   │   ├── models/            # SQLAlchemy ORM models (one file per domain)
│   │   ├── schemas/           # Pydantic request/response models
│   │   ├── routers/           # HTTP handlers — thin, delegate to services
│   │   ├── services/          # ALL business logic lives here
│   │   └── workers/           # Celery app + tasks
│   ├── alembic/
│   ├── requirements.txt
│   └── .env                   # never commit
├── frontend/
│   └── src/{components,pages,hooks,api}/
└── docker-compose.yml
```

---

## Layer responsibilities (strict)

- **models/** — data shape only. SQLAlchemy columns, relationships, and `@property` computed fields (like `food_cost_pct`). No business logic.
- **schemas/** — Pydantic models for API request/response validation. Separate from ORM models.
- **routers/** — thin HTTP layer. Parse request, call a service, return response. No business logic in routers.
- **services/** — all business logic. Depletion, food cost math, ingestion, alerts. Services take a `db: Session` and return data or ORM objects.
- **workers/** — Celery tasks that call services on a schedule.

### UUID normalisation in services

`UUID(as_uuid=True)` columns store Python `uuid.UUID` objects. A plain string never equals a UUID — `db.get()` misses the identity map and tenant comparisons (`col != "string"`) always evaluate True. Every service function that receives an ID from a router (where path parameters are strings) must normalise before use:

```python
import uuid as _uuid

def _to_uuid(val) -> _uuid.UUID:
    return val if isinstance(val, _uuid.UUID) else _uuid.UUID(str(val))

# then in the function:
obj = db.get(MyModel, _to_uuid(some_id))
if obj.restaurant_id != _to_uuid(restaurant_id): ...
```

Define `_to_uuid` once at the top of each service file that needs it.

If you're writing business logic in a router, stop — it belongs in a service.

---

## Naming

- **Files:** snake_case (`food_cost_service.py`, `inventory_service.py`).
- **Models:** PascalCase singular (`MenuItem`, `VendorInvoice`, `StagedIngestion`).
- **Tables:** snake_case plural (`menu_items`, `vendor_invoices`, `staged_ingestions`).
- **Service functions:** verb_noun (`process_invoice`, `deplete_from_sale`, `get_food_cost_summary`).
- **Routers:** prefix matches domain (`/menu-items`, `/sales`, `/ingestion`).
- **React components:** PascalCase (`KpiCard.tsx`, `ReviewIngestion.tsx`).
- **React pages:** PascalCase in `pages/` (`Dashboard.tsx`, `QuickSalesEntry.tsx`).

---

## Database conventions

- **Primary keys:** UUID, `default=uuid.uuid4`.
- **`restaurant_id`** foreign key on every restaurant-scoped table. Non-negotiable.
- **Timestamps:** `created_at` with `server_default=func.now()`. Add `updated_at` with `onupdate=func.now()` where records change.
- **Money:** `Numeric(10,2)` for totals, `Numeric(10,4)` for per-unit costs (4 decimal places matters for ingredient cost precision).
- **Time-series tables** (`sales_summaries`, `sales_by_item`): converted to TimescaleDB hypertables in the migration, partitioned on `business_date`.
- **Never overwrite point-in-time data.** Inventory counts, sales, invoice prices are append-only timestamped records.

---

## API conventions

- **Auth:** every data router injects `rid: str = Depends(get_current_restaurant_id)`.
- **Scoping:** every query filters by `restaurant_id == rid`. Verify ownership on single-record fetches (`if obj.restaurant_id != rid: raise HTTPException(404)`).
- **Status codes:** 201 for creates, 404 for not-found/wrong-tenant, 401 handled by auth dependency.
- **Test via `/docs`** (FastAPI auto-generated) before building frontend for an endpoint.

---

## Ingestion conventions (critical)

- Every automated path (CSV, OCR, voice, email) writes to `staged_ingestions` first — never straight to live tables.
- The operator review UI confirms or rejects.
- On confirm, `ingestion_commit_service.commit_staged_ingestion` translates staged data to live records using the **same** services as manual entry (`process_invoice`, `deplete_batch`).
- Fuzzy-match extracted ingredient names against the catalog (`difflib.get_close_matches`, cutoff 0.7). Auto-create the ingredient if no match.
- Confidence scores drive UI highlighting: green > 0.85, yellow 0.6–0.85, red < 0.6.

---

## Workflow per step

1. `git commit` the previous step before starting a new one (recoverability).
2. Read the step file + this conventions file.
3. Summarize what you'll build before writing code.
4. Build it. Run `alembic upgrade head` if the schema changed.
5. Update the checkbox in `CLAUDE.md`.
6. Log any non-obvious choice in `DECISIONS.md`.

---

## External services / env vars

Store in `.env` locally, AWS Secrets Manager in production. Never commit:

```
DATABASE_URL
SECRET_KEY                  # JWT signing
ANTHROPIC_API_KEY           # OCR + LLM
OPENAI_API_KEY              # Whisper voice transcription
TOAST_CLIENT_ID
TOAST_CLIENT_SECRET
SENDGRID_API_KEY            # inbound email parsing
REDIS_URL
```
