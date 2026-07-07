import uuid as _uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, Index
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class MenuPriceEvent(Base):
    __tablename__ = 'menu_price_events'
    __table_args__ = (
        Index('ix_menu_price_events_rid_item', 'restaurant_id', 'menu_item_id'),
    )

    id            = Column(UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey('restaurants.id'), nullable=False)
    menu_item_id  = Column(UUID(as_uuid=True), ForeignKey('menu_items.id'), nullable=False)
    old_price     = Column(Numeric(10, 2), nullable=False)
    new_price     = Column(Numeric(10, 2), nullable=False)
    changed_at    = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
