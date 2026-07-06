# Restaurant Platform — Scaffold UPDATE Pack (July 2026)

> **⚠ This pack was created separately from the original scaffold**, after Steps 1–7, 5B, 6, and 9 were built and verified. It adds the **Insights Engine** (new Steps 11–13) and brings the control docs in line with what was actually built.

## What's in this pack

```
restaurant-platform-scaffold-update/
├── README.md                          ← this file (do NOT copy into the repo)
├── CLAUDE.md                          ← REPLACES repo-root CLAUDE.md
└── docs/
    ├── conventions.md                 ← REPLACES docs/conventions.md
    └── steps/
        ├── step-11-insights-core.md   ← NEW
        ├── step-12-insights-inputs.md ← NEW
        └── step-13-insights-network.md← NEW
```

Everything replaced or added is internally marked with an "⚠ UPDATE — inserted July 2026" banner so the separately-inserted material is always distinguishable from the original.

## How to apply (from the repo root `C:\Restaurant`)

1. Copy `CLAUDE.md` over the existing root `CLAUDE.md`.
2. Copy `docs/conventions.md` over the existing `docs/conventions.md`.
3. Copy the three new step files into `docs/steps/`.
4. Add a dated line to `DECISIONS.md`: *"2026-07-06 — Inserted Insights Engine (Steps 11–13) and updated CLAUDE.md/conventions.md to as-built state; see step files for scope."*
5. Commit: `git add -A && git commit -m "Docs update: Insights Engine (Steps 11-13), as-built corrections" && git push`

## What changed and why

- **CLAUDE.md** — Build Status now shows Steps 1–7/5B/6/9 complete with honest caveats (mock-verified Toast/OCR/voice; dormant AI pending API keys); stack corrected to as-built (Python 3.14, Vite/5173, dev login); Steps 11–13 added; "Known Caveats" section added; next-session pointer: **Step 11**.
- **conventions.md** — original rules kept; small as-built corrections folded in (hypertable composite PK, noon-UTC business_date, `_to_uuid`, PATCH `model_fields_set`, verify-and-push workflow); a new marked **Insights Engine Conventions** section appended (derived-not-stored, every-insight-ends-in-an-action, threshold settings, min-cohort privacy rule, divide-by-zero and coverage honesty).
- **Steps 11–13** — buildable specs, one session each, in the same self-contained format as steps 01–10:
  - **11 — Insights Core:** variance (flagship), contribution margin $, menu-engineering 2×2, price inflation/vendor compare, par optimization, daypart/DOW patterns, cost sensitivity, break-even. Existing data only.
  - **12 — New Inputs:** labor→prime cost, channels→channel profitability (+packaging as channel recipe lines), covers, waste reason codes, Toast comps/voids (gated on real credentials), weather, `restaurant_type` format modules.
  - **13 — Network & Action:** peer benchmarking (n≥5 privacy rule), price test-and-learn, alert explanations, and the **Daily Action List** — the "decisions, not dashboards" surface.

## Instruction to Claude Code (first session with this pack)

Open `CLAUDE.md`, confirm Build Status, then: **"Build Step 11 — read `docs/steps/step-11-insights-core.md` and `docs/conventions.md` first, summarize the plan, then implement."**

The companion strategy/engineering context lives in the updated `Restaurant_Platform_Blueprint.docx` and `Restaurant_Platform_Build_Guide.docx` (both received matching, marked UPDATE sections).
