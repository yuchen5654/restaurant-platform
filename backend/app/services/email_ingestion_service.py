import json
import logging
import re

import anthropic
from sqlalchemy.orm import Session

from app.models.ingestion import StagedIngestion
from app.models.restaurant import Restaurant

logger = logging.getLogger(__name__)

client = anthropic.Anthropic()

EMAIL_PARSE_PROMPT = (
    'Parse this email received by a restaurant. Determine if it is: '
    '(a) an invoice or delivery receipt, (b) an inventory count, or (c) unknown. '
    'Return ONLY valid JSON with keys: '
    '"type" (invoice|count|unknown), "confidence" (0.0-1.0), and "data". '
    'For invoice, data contains: vendor_name, invoice_number (or null), '
    'received_date (YYYY-MM-DD or null), total_amount (number or null), '
    'line_items (array of: ingredient_name, quantity, unit, unit_cost, confidence 0-1). '
    'For count, data contains: count_date (YYYY-MM-DD or null), '
    'items (array of: ingredient_name, quantity, unit or null, confidence 0-1). '
    'No markdown or preamble.'
)

_IMPORT_TYPE = {'invoice': 'invoice', 'count': 'inventory_count', 'unknown': 'invoice'}


def extract_email_id(to_address: str) -> str | None:
    """Return the local-part before @ from the first address in a to header."""
    match = re.search(r'([^<\s,@]+)@', to_address)
    return match.group(1) if match else None


def find_restaurant_by_email_id(db: Session, email_id: str) -> Restaurant | None:
    return (
        db.query(Restaurant)
        .filter(Restaurant.invoice_email_id == email_id)
        .first()
    )


def parse_email_body(text: str) -> dict:
    resp = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=1000,
        messages=[{
            'role': 'user',
            'content': EMAIL_PARSE_PROMPT + '\n\nEMAIL:\n' + text[:3000],
        }],
    )
    raw = resp.content[0].text.strip()
    if raw.startswith('```'):
        raw = '\n'.join(raw.split('\n')[1:-1])
    return json.loads(raw)


def stage_email_ingestion(
    db: Session,
    restaurant_id: str,
    from_addr: str,
    subject: str,
    body: str,
) -> StagedIngestion:
    parsed      = parse_email_body(body)
    data_type   = parsed.get('type', 'unknown')
    import_type = _IMPORT_TYPE.get(data_type, 'invoice')
    staged = StagedIngestion(
        restaurant_id     = restaurant_id,
        ingestion_type    = 'email',
        import_type       = import_type,
        raw_input         = f'From: {from_addr}\nSubject: {subject}\n\n{body[:1500]}',
        extracted_data    = parsed.get('data', {}),
        confidence_scores = {'overall': parsed.get('confidence', 0.5)},
    )
    db.add(staged)
    db.commit()
    db.refresh(staged)
    return staged
