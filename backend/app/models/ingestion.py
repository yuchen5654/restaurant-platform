from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database import Base


class CsvColumnMapping(Base):
    """Saved column mapping per import type per restaurant — future imports are one-click."""
    __tablename__ = 'csv_column_mappings'

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    import_type   = Column(String(50))    # sales | inventory_count | invoice | labor
    source_label  = Column(String(100))   # e.g. 'Toast Export', 'DoorDash Payout'
    mapping       = Column(JSON)           # {'csv_col_name': 'platform_field_name', ...}
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())


class StagedIngestion(Base):
    """Holding record for any ingestion method awaiting operator confirmation.
    All paths (CSV, OCR, voice, email) write here first."""
    __tablename__ = 'staged_ingestions'

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id     = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    ingestion_type    = Column(String(50))    # csv | ocr_invoice | ocr_count | voice | email
    import_type       = Column(String(50))    # sales | inventory_count | invoice | labor
    raw_input         = Column(Text)          # transcript, truncated CSV, or image ref
    extracted_data    = Column(JSON)          # structured extraction result (Python dict/list)
    confidence_scores = Column(JSON)          # per-field confidence 0.0–1.0
    status            = Column(String(20), default='pending')  # pending|confirmed|rejected
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    confirmed_at      = Column(DateTime(timezone=True))
    confirmed_by      = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    image_s3_key      = Column(String(300))   # S3 key for uploaded photo (added in Step 10)
