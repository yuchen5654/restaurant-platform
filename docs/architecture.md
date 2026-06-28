# Architecture

The stable "why" behind the platform. This rarely changes — read it when you need the big picture, not the implementation detail (that lives in the step files).

---

## The problem

Independent restaurants generate huge amounts of operational data daily but can't see it. Sales live in Toast, inventory in MarketMan or a spreadsheet, labor in 7shifts, delivery orders trapped inside DoorDash. An owner who wants their food cost % for last Tuesday has to manually cross-reference three systems. Most don't — they guess, or wait for the monthly P&L.

Enterprise chains solved this with $10M+ data lakes. No clean solution exists for the 1–5 location independent — the most common restaurant in America. That's the gap.

---

## Three-layer architecture

### Layer 1 — Data Recording (the input surface)
Where staff interact daily. Design principle: **absolute simplicity** — any friction means data doesn't get entered. Must accommodate every operator from a fully-integrated Toast user to a cash-only diner with a paper notebook. This is why the ingestion layer (Step 5B) supports POS API, CSV, photo OCR, voice, email parsing, and manual entry — four tiers of input methods.

### Layer 2 — Data Storage (the moat)
Multi-tenant PostgreSQL + TimescaleDB. Point-in-time append-only records. The **recipe engine** is the core: `MenuItem → RecipeLine → Ingredient`. Each sale auto-depletes ingredient stock and computes food cost. Each invoice price update cascades through every affected recipe. Once a restaurant's menu is mapped in, the platform knows their economics better than they do — live, no manual math.

### Layer 3 — Analytics (the value)
- **Phase 1:** Pure-math dashboards (food cost %, labor %, profitability ranking, variance) + rule-based alerts. No ML needed.
- **Phase 2:** LightGBM demand forecasting, smart reorder suggestions.
- **Phase 3:** Claude API natural-language Q&A over structured data, review sentiment, menu recommendations.

The discipline of separating "this is just math" from "this genuinely needs a model" keeps the build focused and prevents over-engineering.

---

## The recipe engine (most important concept)

```
MenuItem ("Grilled Salmon Dinner", price $28)
   │
   ├── RecipeLine: 6 oz salmon      ──► Ingredient (salmon, $1.20/oz)   ──► Vendor
   ├── RecipeLine: 2 oz olive oil   ──► Ingredient (olive oil, $0.30/oz)
   └── RecipeLine: 4 oz asparagus   ──► Ingredient (asparagus, $0.25/oz)
```

- Sale of the dish → deduct recipe quantities from stock, add ingredient costs to that day's food cost.
- New invoice price for salmon → flows to every recipe containing salmon, food cost reports update automatically.

This live connected model is what separates the platform from a dashboard that just charts whatever you import.

---

## Competitive moat

1. **Neutrality** — works with any POS, any inventory tool, any labor system. Toast can't credibly offer this; they want lock-in.
2. **Data accumulation** — after 2 years of recipe costs, sales history, and waste logs, the switching cost is enormous. The history only exists inside our system.
3. **Universal ingestion** — accommodates every operator regardless of tech stack. Competitors serve tech-forward operators only.

---

## Data flow (end to end)

```
INPUT (any of: POS API, CSV, photo, voice, email, manual)
   │
   ▼
[ automated paths → staged_ingestions → operator review/confirm ]
   │
   ▼
COMMIT via shared services (process_invoice / deplete_batch / log_waste)
   │
   ▼
LIVE TABLES (ingredients, sales_by_item, inventory_counts, ...)
   │
   ├──► Dashboards (food_cost_service, profitability)
   ├──► Alerts (alert_service, nightly Celery)
   ├──► Forecasting (forecasting_service, weekly Celery)  [Phase 2]
   └──► LLM Q&A (llm_service, structured context)         [Phase 3]
```
