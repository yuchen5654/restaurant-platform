# Step 5B — Universal Data Ingestion Layer

**Estimated time:** 12–18 hours
**Phase:** 1 (Foundation)
**Depends on:** Step 5.

> **This is the biggest step.** Consider splitting it across two sessions: (A) the backend services (schema, CSV, OCR, voice, email, commit service, router), and (B) the React review UI + quick entry forms.

---

## Goal

Accommodate every type of restaurant operator — from fully-automated POS API users to OCR photo uploads to voice inventory counting to manual entry. Every method feeds into one **stage → review → confirm** pattern before committing to the database.

**Architecture:** Input → Extract → Normalize → Stage → Review/Confirm → Commit. Every method writes to `staged_ingestions` first. The operator confirms. The commit service reuses the same `process_invoice` / `deplete_batch` functions as manual entry, so there's one path through the system.

---

## 5B.1 Schema — `app/models/ingestion.py`

```python
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.database import Base

class CsvColumnMapping(Base):
    """Saves column mapping per import type per restaurant — future imports one-click."""
    __tablename__ = 'csv_column_mappings'
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    import_type   = Column(String(50))   # sales | inventory_count | invoice | labor
    source_label  = Column(String(100))  # e.g. 'Toast Export', 'DoorDash Payout'
    mapping       = Column(JSON)          # {'csv_col_name': 'platform_field_name', ...}
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())

class StagedIngestion(Base):
    """Holding record for any ingestion method awaiting operator confirmation.
    All paths (CSV, OCR, voice, email) write here first."""
    __tablename__ = 'staged_ingestions'
    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id     = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    ingestion_type    = Column(String(50))   # csv | ocr_invoice | ocr_count | voice | email
    import_type       = Column(String(50))   # sales | inventory_count | invoice | labor
    raw_input         = Column(Text)         # transcript, truncated CSV, or image ref
    extracted_data    = Column(JSON)         # structured extraction result
    confidence_scores = Column(JSON)         # per-field confidence 0.0-1.0
    status            = Column(String(20), default='pending')  # pending|confirmed|rejected
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    confirmed_at      = Column(DateTime(timezone=True))
    confirmed_by      = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    image_s3_key      = Column(String(300))  # link to uploaded photo for side-by-side review
```

Add both tables to a new migration: `alembic revision --autogenerate -m 'add_ingestion_tables'` then `alembic upgrade head`.

---

## 5B.2 CSV import — `app/services/csv_ingestion_service.py`

```python
import csv, io, json
from sqlalchemy.orm import Session
from app.models.ingestion import CsvColumnMapping, StagedIngestion

FIELD_SCHEMAS = {
    'sales':           ['business_date','menu_item_name','quantity_sold','gross_revenue'],
    'inventory_count': ['ingredient_name','quantity','unit','counted_at'],
    'invoice':         ['vendor_name','ingredient_name','quantity_received','unit','unit_cost'],
    'labor':           ['employee_name','role','hours','pay_rate'],
}

def parse_csv(content: str):
    reader  = csv.DictReader(io.StringIO(content))
    headers = list(reader.fieldnames or [])
    rows    = [dict(r) for r in reader]
    return headers, rows

def apply_mapping(rows, mapping):
    return [{mapping[k]: v.strip() for k,v in row.items() if k in mapping} for row in rows]

def stage_csv_import(db: Session, restaurant_id: str, import_type: str,
                     file_content: str, mapping: dict,
                     save_mapping: bool=True, label: str='') -> StagedIngestion:
    headers, rows = parse_csv(file_content)
    mapped_rows   = apply_mapping(rows, mapping)

    required = FIELD_SCHEMAS.get(import_type, [])
    if mapped_rows:
        missing = [f for f in required if f not in mapped_rows[0]]
        if missing:
            raise ValueError(f'Missing required fields after mapping: {missing}')

    staged = StagedIngestion(
        restaurant_id     = restaurant_id,
        ingestion_type    = 'csv',
        import_type       = import_type,
        raw_input         = file_content[:2000],
        extracted_data    = json.dumps(mapped_rows),
        confidence_scores = json.dumps({f: 1.0 for f in required}),
    )
    db.add(staged)

    if save_mapping and label:
        existing = db.query(CsvColumnMapping).filter(
            CsvColumnMapping.restaurant_id == restaurant_id,
            CsvColumnMapping.import_type   == import_type,
            CsvColumnMapping.source_label  == label,
        ).first()
        if existing:
            existing.mapping = mapping
        else:
            db.add(CsvColumnMapping(restaurant_id=restaurant_id,
                import_type=import_type, source_label=label, mapping=mapping))

    db.commit(); db.refresh(staged)
    return staged
```

---

## 5B.3 OCR photo upload — `app/services/ocr_ingestion_service.py`

```python
import anthropic, base64, json, io
from PIL import Image
from sqlalchemy.orm import Session
from app.models.ingestion import StagedIngestion

client = anthropic.Anthropic()

INVOICE_PROMPT = (
    'Extract ALL line items from this vendor invoice or delivery receipt. '
    'Return ONLY valid JSON with keys: vendor_name, invoice_number, received_date (YYYY-MM-DD), '
    'total_amount, and line_items (array of: ingredient_name, quantity, unit, unit_cost, confidence 0-1). '
    'Use null for any field you cannot read clearly. No markdown or preamble.'
)
COUNT_PROMPT = (
    'Extract all items from this inventory count sheet (handwritten or printed). '
    'Return ONLY valid JSON with keys: count_date (YYYY-MM-DD or null), '
    'and items (array of: ingredient_name, quantity, unit or null, confidence 0-1). '
    'No markdown or preamble.'
)

def prep_image(image_bytes: bytes):
    img = Image.open(io.BytesIO(image_bytes))
    fmt = img.format or 'JPEG'
    if len(image_bytes) > 1_800_000:
        img.thumbnail((2000, 2000), Image.LANCZOS)
        buf = io.BytesIO(); img.save(buf, format=fmt); image_bytes = buf.getvalue()
    media_map = {'JPEG':'image/jpeg','PNG':'image/png','WEBP':'image/webp'}
    return base64.standard_b64encode(image_bytes).decode(), media_map.get(fmt,'image/jpeg')

def extract_from_image(image_bytes: bytes, extract_type: str) -> dict:
    b64, mtype = prep_image(image_bytes)
    prompt     = INVOICE_PROMPT if extract_type == 'invoice' else COUNT_PROMPT
    resp = client.messages.create(
        model='claude-sonnet-4-6', max_tokens=2000,
        messages=[{'role':'user','content':[
            {'type':'image','source':{'type':'base64','media_type':mtype,'data':b64}},
            {'type':'text','text':prompt},
        ]}],
    )
    raw = resp.content[0].text.strip()
    if raw.startswith('```'): raw = '\n'.join(raw.split('\n')[1:-1])
    return json.loads(raw)

def stage_image_upload(db: Session, restaurant_id: str,
                       image_bytes: bytes, extract_type: str) -> StagedIngestion:
    extracted = extract_from_image(image_bytes, extract_type)
    items_key = 'line_items' if extract_type=='invoice' else 'items'
    items     = extracted.get(items_key, [])
    avg_conf  = sum(i.get('confidence',0.8) for i in items)/len(items) if items else 0.5
    staged = StagedIngestion(
        restaurant_id     = restaurant_id,
        ingestion_type    = 'ocr_'+extract_type,
        import_type       = 'invoice' if extract_type=='invoice' else 'inventory_count',
        raw_input         = 'Image upload ('+extract_type+')',
        extracted_data    = json.dumps(extracted),
        confidence_scores = json.dumps({'avg_item_confidence': avg_conf}),
    )
    db.add(staged); db.commit(); db.refresh(staged)
    return staged
```

**Pro tip:** upload the original photo to S3, store the key in `staged.image_s3_key`, and show a pre-signed URL alongside the extracted form. A side-by-side view (photo left, editable form right) dramatically reduces errors and builds trust.

---

## 5B.4 Voice counting — `app/services/voice_ingestion_service.py`

```python
import openai, anthropic, json, io
from sqlalchemy.orm import Session
from app.models.ingestion import StagedIngestion

whisper = openai.OpenAI()
claude  = anthropic.Anthropic()

PARSE_PROMPT = (
    'Parse this spoken inventory count from a restaurant kitchen manager. '
    'Extract all items mentioned. Return ONLY valid JSON: '
    '{"items":[{"ingredient_name":"string","quantity":number,"unit":"string or null"}],'
    '"unclear_segments":["segments you could not parse"]}. '
    'Common units: lb, oz, case, each, liter, gallon, bag, dozen. '
    'If unit not stated, set null. No markdown.'
)

def transcribe(audio_bytes: bytes, fmt: str='webm') -> str:
    buf = io.BytesIO(audio_bytes); buf.name = 'recording.'+fmt
    return whisper.audio.transcriptions.create(
        model='whisper-1', file=buf, language='en', response_format='text')

def parse_transcript(transcript: str) -> dict:
    resp = claude.messages.create(
        model='claude-sonnet-4-6', max_tokens=800,
        messages=[{'role':'user','content':PARSE_PROMPT+'\n\nTRANSCRIPT: '+transcript}])
    raw = resp.content[0].text.strip()
    if raw.startswith('```'): raw = '\n'.join(raw.split('\n')[1:-1])
    return json.loads(raw)

def stage_voice_count(db: Session, restaurant_id: str,
                      audio_bytes: bytes, fmt: str='webm') -> StagedIngestion:
    transcript = transcribe(audio_bytes, fmt)
    parsed     = parse_transcript(transcript)
    staged = StagedIngestion(
        restaurant_id     = restaurant_id,
        ingestion_type    = 'voice',
        import_type       = 'inventory_count',
        raw_input         = transcript,
        extracted_data    = json.dumps(parsed),
        confidence_scores = json.dumps({'overall': 0.85}),
    )
    db.add(staged); db.commit(); db.refresh(staged)
    return staged
```

**Watch out:** walk-in fans and compressors reduce Whisper accuracy. Prompt operators to pause near each item and speak clearly. Show the full transcript on the review screen and add a replay-audio button.

---

Continued in this same file below: email parsing (5B.5), manual entry form (5B.6), review UI (5B.7), commit service (5B.8), API router (5B.9).

See `step-05b-ingestion-part2.md` for the remaining sub-steps.

## Then (after completing part 2)

Update checkbox in `CLAUDE.md`, `git commit`, move to `step-06-alerts.md`.
