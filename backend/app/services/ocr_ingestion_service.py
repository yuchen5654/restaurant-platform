import base64
import io
import json
import logging

import anthropic
from PIL import Image
from sqlalchemy.orm import Session

from app.models.ingestion import StagedIngestion

logger = logging.getLogger(__name__)

# Module-level client — reads ANTHROPIC_API_KEY env var on first API call.
client = anthropic.Anthropic()

INVOICE_PROMPT = (
    'Extract ALL line items from this vendor invoice or delivery receipt. '
    'Return ONLY valid JSON with keys: vendor_name, invoice_number, '
    'received_date (YYYY-MM-DD), total_amount, and line_items '
    '(array of: ingredient_name, quantity, unit, unit_cost, confidence 0-1). '
    'Use null for any field you cannot read clearly. No markdown or preamble.'
)
COUNT_PROMPT = (
    'Extract all items from this inventory count sheet (handwritten or printed). '
    'Return ONLY valid JSON with keys: count_date (YYYY-MM-DD or null), '
    'and items (array of: ingredient_name, quantity, unit or null, confidence 0-1). '
    'No markdown or preamble.'
)


def prep_image(image_bytes: bytes) -> tuple[str, str]:
    """Resize if over ~1.8 MB; return (base64_data, media_type)."""
    img = Image.open(io.BytesIO(image_bytes))
    fmt = img.format or 'JPEG'
    if len(image_bytes) > 1_800_000:
        img.thumbnail((2000, 2000), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format=fmt)
        image_bytes = buf.getvalue()
    media_map = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp'}
    return base64.standard_b64encode(image_bytes).decode(), media_map.get(fmt, 'image/jpeg')


def extract_from_image(image_bytes: bytes, extract_type: str) -> dict:
    """Call Claude Vision and return the parsed JSON result."""
    b64, mtype = prep_image(image_bytes)
    prompt     = INVOICE_PROMPT if extract_type == 'invoice' else COUNT_PROMPT
    resp = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=2000,
        messages=[{
            'role': 'user',
            'content': [
                {
                    'type': 'image',
                    'source': {'type': 'base64', 'media_type': mtype, 'data': b64},
                },
                {'type': 'text', 'text': prompt},
            ],
        }],
    )
    raw = resp.content[0].text.strip()
    if raw.startswith('```'):
        raw = '\n'.join(raw.split('\n')[1:-1])
    return json.loads(raw)


def stage_image_upload(
    db: Session,
    restaurant_id: str,
    image_bytes: bytes,
    extract_type: str,
) -> StagedIngestion:
    extracted = extract_from_image(image_bytes, extract_type)
    items_key = 'line_items' if extract_type == 'invoice' else 'items'
    items     = extracted.get(items_key, [])
    avg_conf  = (
        sum(i.get('confidence', 0.8) for i in items) / len(items)
        if items else 0.5
    )
    staged = StagedIngestion(
        restaurant_id     = restaurant_id,
        ingestion_type    = 'ocr_' + extract_type,
        import_type       = 'invoice' if extract_type == 'invoice' else 'inventory_count',
        raw_input         = f'Image upload ({extract_type})',
        extracted_data    = extracted,
        confidence_scores = {'avg_item_confidence': avg_conf},
    )
    db.add(staged)
    db.commit()
    db.refresh(staged)
    return staged
