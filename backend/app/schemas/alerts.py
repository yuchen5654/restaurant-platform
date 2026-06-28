from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AlertOut(BaseModel):
    id:            UUID
    restaurant_id: UUID
    alert_type:    str
    severity:      str
    message:       str
    extra_data:    Optional[Any] = None
    is_read:       bool
    created_at:    datetime

    model_config = ConfigDict(from_attributes=True)
