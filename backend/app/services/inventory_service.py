from decimal import Decimal
from datetime import datetime, timezone
import logging
import uuid as _uuid

from sqlalchemy.orm import Session

from app.models.inventory import Ingredient, VendorInvoice, InvoiceLineItem, WasteLog

logger = logging.getLogger(__name__)


def _to_uuid(val) -> _uuid.UUID:
    return val if isinstance(val, _uuid.UUID) else _uuid.UUID(str(val))


def process_invoice(db: Session, restaurant_id: str, invoice_data) -> VendorInvoice:
    """Record invoice, update ingredient cost and stock — single transaction."""
    invoice = VendorInvoice(
        restaurant_id  = restaurant_id,
        vendor_id      = invoice_data.vendor_id,
        invoice_number = invoice_data.invoice_number,
        received_at    = invoice_data.received_at or datetime.now(timezone.utc),
        total_amount   = invoice_data.total_amount,
    )
    db.add(invoice)
    db.flush()

    for line in invoice_data.line_items:
        ingredient = db.get(Ingredient, _to_uuid(line.ingredient_id))
        if not ingredient or ingredient.restaurant_id != _to_uuid(restaurant_id):
            raise ValueError(f'Ingredient {line.ingredient_id} not found')
        extended = Decimal(str(line.quantity_received)) * Decimal(str(line.unit_cost))
        db.add(InvoiceLineItem(
            invoice_id        = invoice.id,
            ingredient_id     = line.ingredient_id,
            quantity_received = line.quantity_received,
            unit_cost         = line.unit_cost,
            extended_cost     = extended,
        ))
        ingredient.current_cost_per_unit = line.unit_cost
        ingredient.current_stock = (ingredient.current_stock or 0) + line.quantity_received

    db.commit()
    db.refresh(invoice)
    return invoice


def log_waste(db: Session, restaurant_id: str, ingredient_id: str,
              quantity: float, reason: str, notes: str = None) -> WasteLog:
    ingredient = db.get(Ingredient, _to_uuid(ingredient_id))
    if not ingredient or ingredient.restaurant_id != _to_uuid(restaurant_id):
        raise ValueError('Ingredient not found')

    current = ingredient.current_stock or Decimal('0')
    if Decimal(str(quantity)) > current:
        logger.warning(
            f'Waste entry for {ingredient.name} ({quantity} {ingredient.unit}) exceeds '
            f'current stock ({current}). Check inventory count accuracy for '
            f'restaurant {restaurant_id}.'
        )

    waste = WasteLog(
        restaurant_id = restaurant_id,
        ingredient_id = ingredient_id,
        logged_at     = datetime.now(timezone.utc),
        quantity      = quantity,
        reason        = reason,
        cost_at_time  = ingredient.current_cost_per_unit,
        notes         = notes,
    )
    db.add(waste)
    ingredient.current_stock = max(Decimal('0'), current - Decimal(str(quantity)))
    db.commit()
    return waste
