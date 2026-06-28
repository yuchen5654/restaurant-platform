import json
import uuid as _uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ingestion import CsvColumnMapping, StagedIngestion
from app.routers.auth import get_current_restaurant_id, get_current_user
from app.schemas.ingestion import CsvMappingOut, StagedIngestionOut
from app.services.csv_ingestion_service import stage_csv_import
from app.services.email_ingestion_service import (
    extract_email_id,
    find_restaurant_by_email_id,
    stage_email_ingestion,
)
from app.services.ingestion_commit_service import (
    commit_staged_ingestion,
    reject_staged_ingestion,
)
from app.services.ocr_ingestion_service import stage_image_upload
from app.services.voice_ingestion_service import stage_voice_count

router = APIRouter(prefix='/ingestion', tags=['ingestion'])


def _to_uuid(val) -> _uuid.UUID:
    return val if isinstance(val, _uuid.UUID) else _uuid.UUID(str(val))


# ---------------------------------------------------------------------------
# Ingestion endpoints (authenticated)
# ---------------------------------------------------------------------------

@router.post('/csv', status_code=201, response_model=StagedIngestionOut)
def upload_csv(
    file:         UploadFile = File(...),
    import_type:  str        = Form(...),
    mapping:      str        = Form(...),   # JSON: {'csv_col': 'platform_field', ...}
    label:        str        = Form(''),
    save_mapping: bool       = Form(True),
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    mapping_dict = json.loads(mapping)
    content      = file.file.read().decode('utf-8')
    try:
        staged = stage_csv_import(db, rid, import_type, content, mapping_dict, save_mapping, label)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return staged


@router.post('/ocr', status_code=201, response_model=StagedIngestionOut)
def upload_image(
    file:         UploadFile = File(...),
    extract_type: str        = Form('invoice'),  # invoice | count
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    image_bytes = file.file.read()
    staged = stage_image_upload(db, rid, image_bytes, extract_type)
    return staged


@router.post('/voice', status_code=201, response_model=StagedIngestionOut)
def upload_voice(
    file: UploadFile = File(...),
    fmt:  str        = Form('webm'),
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    audio_bytes = file.file.read()
    staged = stage_voice_count(db, rid, audio_bytes, fmt)
    return staged


# ---------------------------------------------------------------------------
# SendGrid inbound-parse webhook — no user auth (called by SendGrid)
# ---------------------------------------------------------------------------

@router.post('/email-webhook')
async def email_webhook(request: Request, db: Session = Depends(get_db)):
    """Receives SendGrid inbound-parse POSTs; routes by invoice_email_id in To header."""
    form      = await request.form()
    to_addr   = form.get('to', '')
    from_addr = form.get('from', '')
    subject   = form.get('subject', '')
    body      = str(form.get('text') or form.get('html') or '')

    email_id   = extract_email_id(str(to_addr))
    if not email_id:
        return {'ok': False, 'reason': 'no email_id in to address'}

    restaurant = find_restaurant_by_email_id(db, email_id)
    if not restaurant:
        return {'ok': False, 'reason': 'restaurant not found'}

    try:
        staged = stage_email_ingestion(
            db, str(restaurant.id), str(from_addr), str(subject), body,
        )
        return {'ok': True, 'staged_id': str(staged.id)}
    except Exception as exc:
        return {'ok': False, 'reason': str(exc)}


# ---------------------------------------------------------------------------
# Review queue
# ---------------------------------------------------------------------------

@router.get('/staged', response_model=list[StagedIngestionOut])
def list_staged(
    status: str  = 'pending',
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    return (
        db.query(StagedIngestion)
        .filter(StagedIngestion.restaurant_id == rid, StagedIngestion.status == status)
        .order_by(StagedIngestion.created_at.desc())
        .all()
    )


@router.get('/staged/{staged_id}', response_model=StagedIngestionOut)
def get_staged(
    staged_id: str,
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    s = db.get(StagedIngestion, _to_uuid(staged_id))
    if not s or s.restaurant_id != _to_uuid(rid):
        raise HTTPException(404)
    return s


@router.post('/staged/{staged_id}/confirm')
def confirm_staged(
    staged_id: str,
    db:   Session = Depends(get_db),
    rid:  str     = Depends(get_current_restaurant_id),
    user          = Depends(get_current_user),
):
    try:
        result = commit_staged_ingestion(db, rid, staged_id, str(user.id))
        return {'ok': True, **result}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post('/staged/{staged_id}/reject')
def reject_staged(
    staged_id: str,
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    try:
        reject_staged_ingestion(db, rid, staged_id)
        return {'ok': True}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


# ---------------------------------------------------------------------------
# CSV mapping library
# ---------------------------------------------------------------------------

@router.get('/csv-mappings', response_model=list[CsvMappingOut])
def list_csv_mappings(
    import_type: str | None = None,
    db:  Session = Depends(get_db),
    rid: str     = Depends(get_current_restaurant_id),
):
    q = db.query(CsvColumnMapping).filter(CsvColumnMapping.restaurant_id == rid)
    if import_type:
        q = q.filter(CsvColumnMapping.import_type == import_type)
    return q.order_by(CsvColumnMapping.source_label).all()
