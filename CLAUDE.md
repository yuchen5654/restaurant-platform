# Restaurant Platform

Multi-tenant restaurant data & analytics platform for independent operators (1–5 locations, $500K–$3M revenue, owner-operated). Unifies sales, inventory, labor, and customer data that today lives scattered across Toast, MarketMan, 7shifts, and delivery platforms.

---

## How to work on this project

1. **The build is broken into steps** in `docs/steps/`. Each step file is self-contained.
2. **Before building ANY step, read its step file first** (`docs/steps/step-XX-*.md`), plus `docs/conventions.md`.
3. **Read `docs/architecture.md`** if you need the big-picture "why" behind a decision.
4. **Log any non-obvious decision** you make mid-build in `DECISIONS.md` (with the date and the reasoning).
5. **Update the Build Status checkboxes below** the moment a step is complete.
6. **One step per session.** Do not attempt multiple steps at once — scope each session to a single step file.
7. **Summarize the step before writing code.** When asked to build a step, first restate what it involves and what files you'll create, then proceed.

---

## Build Status

- [x] Step 1 — Project setup & DB init (`step-01-setup.md`)
- [x] Step 2 — Core schema, multi-tenant (`step-02-schema.md`)
- [ ] Step 3 — Recipe engine & depletion (`step-03-recipe-engine.md`)
- [ ] Step 4 — REST API layer (`step-04-api.md`)
- [ ] Step 5 — Toast POS integration (`step-05-toast.md`)
- [ ] Step 5B — Universal ingestion layer (`step-05b-ingestion.md`)
- [ ] Step 6 — Alert engine (`step-06-alerts.md`)
- [ ] Step 7 — React frontend (`step-07-frontend.md`)
- [ ] Step 8 — LightGBM forecasting (`step-08-forecasting.md`)
- [ ] Step 9 — LLM Q&A layer (`step-09-llm.md`)
- [ ] Step 10 — AWS deployment (`step-10-aws.md`)

Status key: `[ ]` not started · `[~]` in progress · `[x]` complete

---

## Hard Rules (never violate)

- **`restaurant_id` on every data model.** Multi-tenant isolation is non-negotiable. Every query must be scoped to the authenticated restaurant.
- **All ingestion follows stage → review → confirm.** Never auto-commit OCR/voice/email/CSV-extracted data straight to live tables. It always lands in `staged_ingestions` first for operator confirmation.
- **Point-in-time data is append-only.** Never overwrite an inventory count, a sale, or an invoice price. Append a new timestamped record.
- **Run `alembic upgrade head` after every schema change.** Never `ALTER TABLE` by hand.
- **Layer separation:** business logic in `app/services/`, HTTP handlers in `app/routers/`, ORM models in `app/models/`, Pydantic schemas in `app/schemas/`.
- **Negative stock is a signal, not a bug.** Log it visibly — it means a count, invoice, or waste entry is missing. Do not silently clamp and move on.

---

## Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.12 + FastAPI |
| Database | PostgreSQL + TimescaleDB |
| Background jobs | Celery + Redis |
| Ingestion (OCR) | Anthropic Claude Vision API |
| Ingestion (voice) | OpenAI Whisper |
| Ingestion (email) | SendGrid Inbound Parse |
| Frontend | React 18 + TypeScript + Recharts + Tailwind |
| ML (Phase 2) | LightGBM |
| LLM (Phase 3) | Anthropic Claude API |
| Hosting | AWS (RDS + EC2 + S3 + CloudFront) |

---

## Local Dev

```bash
docker compose up -d                          # Postgres + TimescaleDB + Redis
cd backend && source venv/bin/activate
uvicorn app.main:app --reload                 # API at http://localhost:8000
# Interactive API docs: http://localhost:8000/docs

# Celery (separate terminals):
celery -A app.workers.celery_app worker --loglevel=info
celery -A app.workers.celery_app beat --loglevel=info

# Frontend:
cd frontend && npm start                      # http://localhost:3000
```

---

## Phasing

- **Phase 1 (Steps 1–7 + 5B):** Working MVP a real restaurant can use. ~70–92 hours.
- **Phase 2 (Step 8):** ML demand forecasting. Needs 60+ days of live data first.
- **Phase 3 (Step 9):** LLM Q&A and review intelligence.
- **Deploy (Step 10):** After Phase 1 is validated by real users.
