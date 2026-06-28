# Step 9 — LLM Natural Language Q&A Layer

**Estimated time:** 8–10 hours
**Phase:** 3 (AI Reasoning)
**Depends on:** clean data history from Phase 1.

---

## Goal

Conversational interface for plain-English questions. **Architecture: NOT vector RAG.** Run SQL queries → assemble structured context → pass to Claude → reason over it. The database provides facts; the LLM provides synthesis.

## `app/services/llm_service.py`

```python
import anthropic, json
from sqlalchemy.orm import Session
from app.services.food_cost_service import get_food_cost_summary, get_item_profitability
from datetime import datetime, timedelta, timezone

client = anthropic.Anthropic()

SYSTEM_PROMPT = ('You are an expert restaurant operations analyst. '
    'Answer using only the data provided. Never guess or invent numbers. '
    'If the data is insufficient, say so. Format percentages to 1 decimal, '
    'dollars with commas. Be concise and actionable.')

def assemble_context(db: Session, restaurant_id: str) -> str:
    now = datetime.now(timezone.utc)
    fc_7d  = get_food_cost_summary(db, restaurant_id, now-timedelta(days=7), now)
    fc_30d = get_food_cost_summary(db, restaurant_id, now-timedelta(days=30), now)
    items  = get_item_profitability(db, restaurant_id, now-timedelta(days=30), now, 15)
    return (f"RESTAURANT DATA (as of {now.strftime('%Y-%m-%d %H:%M UTC')})\n\n"
            f"FOOD COST 7D: {json.dumps(fc_7d, indent=2)}\n\n"
            f"FOOD COST 30D: {json.dumps(fc_30d, indent=2)}\n\n"
            f"TOP ITEMS BY PROFIT 30D: {json.dumps(items, indent=2)}")

def ask_restaurant_question(db: Session, restaurant_id: str, question: str,
                            conversation_history: list[dict] = None) -> str:
    context  = assemble_context(db, restaurant_id)
    messages = list(conversation_history or [])
    messages.append({'role':'user','content': f'{context}\n\nOPERATOR QUESTION: {question}'})
    resp = client.messages.create(
        model='claude-sonnet-4-6', max_tokens=1000,
        system=SYSTEM_PROMPT, messages=messages)
    return resp.content[0].text
```

## `app/routers/ai.py`

```python
from fastapi import APIRouter, Depends
from app.database import get_db
from app.routers.auth import get_current_restaurant_id
from app.services.llm_service import ask_restaurant_question
from pydantic import BaseModel

router = APIRouter(prefix='/ai', tags=['ai'])

class QuestionRequest(BaseModel):
    question: str
    conversation_history: list[dict] = []

@router.post('/ask')
def ask(req: QuestionRequest, db=Depends(get_db), rid=Depends(get_current_restaurant_id)):
    return {'answer': ask_restaurant_question(db, rid, req.question, req.conversation_history)}
```

Register `app.include_router(ai.router)` in main.py. Optionally add `review_service.py` for review sentiment summarization (same pattern, returns JSON with sentiment + insights).

## Done when
`POST /ai/ask` with a question returns a grounded answer using real food cost data.

## Then
Update checkbox, `git commit`, move to `step-10-aws.md`.
