"""Structured-context LLM Q&A service.

Architecture: NOT vector RAG.
  1. Run SQL queries against live data.
  2. Assemble a structured context block.
  3. Pass context + question to Claude.
  4. Return grounded, synthesised answer.

The database provides facts; the LLM provides synthesis.
"""
import json
import logging
from datetime import datetime, timedelta, timezone

import anthropic
from sqlalchemy.orm import Session

from app.services.food_cost_service import get_food_cost_summary, get_item_profitability
from app.models.alerts import Alert
from app.models.inventory import Ingredient

logger = logging.getLogger(__name__)

# Module-level client — reads ANTHROPIC_API_KEY from env at first API call.
client = anthropic.Anthropic()

SYSTEM_PROMPT = (
    'You are an expert restaurant operations analyst. '
    'Answer using only the data provided in the context block. '
    'Never guess or invent numbers. '
    'If the data is insufficient to answer, say so explicitly. '
    'Format percentages to 1 decimal place and dollar amounts with commas. '
    'Be concise and actionable — focus on what the operator should do next.'
)


def assemble_context(db: Session, restaurant_id: str) -> str:
    """Query live data and build the structured context block passed to Claude."""
    now   = datetime.now(timezone.utc)
    fc_7d  = get_food_cost_summary(db, restaurant_id, now - timedelta(days=7),  now)
    fc_30d = get_food_cost_summary(db, restaurant_id, now - timedelta(days=30), now)
    items  = get_item_profitability(db, restaurant_id, now - timedelta(days=30), now, 15)

    # Low-stock ingredients (par_level set and at or below par)
    from app.services.alert_service import check_low_stock
    low_stock = check_low_stock(db, restaurant_id)

    # Unread alert count
    unread_alerts = (
        db.query(Alert)
        .filter(Alert.restaurant_id == restaurant_id, Alert.is_read.is_(False))
        .count()
    )

    return (
        f"RESTAURANT DATA (as of {now.strftime('%Y-%m-%d %H:%M UTC')})\n\n"
        f"FOOD COST — LAST 7 DAYS:\n{json.dumps(fc_7d, indent=2)}\n\n"
        f"FOOD COST — LAST 30 DAYS:\n{json.dumps(fc_30d, indent=2)}\n\n"
        f"TOP 15 ITEMS BY GROSS PROFIT (last 30 days):\n{json.dumps(items, indent=2)}\n\n"
        f"LOW-STOCK ALERTS ({len(low_stock)} items):\n{json.dumps(low_stock, indent=2)}\n\n"
        f"UNREAD ALERTS: {unread_alerts}"
    )


def ask_restaurant_question(
    db: Session,
    restaurant_id: str,
    question: str,
    conversation_history: list[dict] | None = None,
) -> str:
    """Answer a natural-language question using live restaurant data as context."""
    context  = assemble_context(db, restaurant_id)
    messages = list(conversation_history or [])
    messages.append({
        'role':    'user',
        'content': f'{context}\n\nOPERATOR QUESTION: {question}',
    })

    logger.info('LLM ask — restaurant=%s question=%r', restaurant_id, question[:80])

    resp = client.messages.create(
        model      = 'claude-sonnet-4-6',
        max_tokens = 1000,
        system     = SYSTEM_PROMPT,
        messages   = messages,
    )
    answer = resp.content[0].text
    logger.info('LLM answer — input_tokens=%d output_tokens=%d',
                resp.usage.input_tokens, resp.usage.output_tokens)
    return answer
