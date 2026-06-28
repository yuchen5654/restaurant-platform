from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class StagedIngestionOut(BaseModel):
    id:                UUID
    restaurant_id:     UUID
    ingestion_type:    str
    import_type:       str
    status:            str
    raw_input:         Optional[str]     = None
    extracted_data:    Optional[Any]     = None
    confidence_scores: Optional[Any]     = None
    created_at:        datetime
    confirmed_at:      Optional[datetime] = None
    image_s3_key:      Optional[str]     = None

    model_config = ConfigDict(from_attributes=True)


class CsvMappingOut(BaseModel):
    id:           UUID
    import_type:  str
    source_label: str
    mapping:      Any
    created_at:   datetime

    model_config = ConfigDict(from_attributes=True)
