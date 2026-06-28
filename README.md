# Restaurant Platform — Build Scaffold

This is the project scaffold for building the Restaurant Data & Analytics Platform with Claude Code. It's structured for a long, multi-session build where you'll revisit steps many times.

## What's here

```
.
├── CLAUDE.md              ← Claude Code reads this automatically every session.
│                            Control center: build status, hard rules, stack.
├── DECISIONS.md           ← Running log of choices made mid-build (the "why").
├── docs/
│   ├── architecture.md    ← The stable big-picture "why". Read for context.
│   ├── conventions.md     ← Naming, structure, patterns. Read before coding.
│   └── steps/             ← One file per build step. The "how".
│       ├── step-01-setup.md
│       ├── step-02-schema.md
│       ├── step-03-recipe-engine.md
│       ├── step-04-api.md
│       ├── step-05-toast.md
│       ├── step-05b-ingestion.md        (Part 1: schema, CSV, OCR, voice)
│       ├── step-05b-ingestion-part2.md  (Part 2: email, UI, commit, router)
│       ├── step-06-alerts.md
│       ├── step-07-frontend.md
│       ├── step-08-forecasting.md
│       ├── step-09-llm.md
│       └── step-10-aws.md
└── README.md              ← this file
```

## How to use it

1. **Drop this whole folder into your project root** (or `git init` here and build inside it).

2. **Start each Claude Code session scoped to one step:**
   ```bash
   claude "Read docs/steps/step-01-setup.md and docs/conventions.md.
   Summarize what you'll build, then implement it."
   ```

3. **After each step:**
   - `git commit` the work (so any step is recoverable)
   - Update the checkbox in `CLAUDE.md`
   - Log any non-obvious decision in `DECISIONS.md`

4. **When revisiting a step** (debugging, refactoring), just point Claude Code at that one step file again:
   ```bash
   claude "Re-read docs/steps/step-05b-ingestion.md. The OCR confidence
   scoring isn't matching the spec — fix it to match."
   ```

## Why this structure

- **CLAUDE.md is Claude Code's memory between sessions.** It has no memory otherwise. Keeping the build status and rules current here is what prevents drift over a long build.
- **Split step files keep context focused.** When you're on Step 5B, Claude Code reads only Step 5B — not the whole 40-page guide. Scoped, surgical, repeatable.
- **DECISIONS.md answers "why is it like this?"** three months later, when the reasoning would otherwise be lost.

## Build order

Steps 1 → 2 → 3 → 4 → 5 → 5B → 6 → 7 complete **Phase 1** (a working MVP, ~70–92 hrs).
Step 8 is **Phase 2** (needs 60+ days of live data first).
Step 9 is **Phase 3**.
Step 10 deploys to production after Phase 1 is validated.

## First command to run

If starting fresh, let Claude Code bootstrap its understanding:
```bash
claude "Read CLAUDE.md, docs/architecture.md, and docs/conventions.md.
Tell me what this project is and what Step 1 involves. Don't write code yet."
```
