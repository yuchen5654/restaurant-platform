"""Commit a staged ingestion to live tables after operator review.

All paths land in staged_ingestions first. When the operator confirms, this
service fuzzy-matches extracted names against the catalog and calls the same
process_invoice / deplete_batch functions used by manual entry — one path
through the system.
"""
import difflib
import logging
import uuid as _uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy.orm import Session

from app.models.ingestion import StagedIngestion
from app.models.inventory import Ingredient, InventoryCount, Vendor
from app.models.recipe import MenuItem

logger = logging.getLogger(__name__)


def _to_uuid(val) -> _uuid.UUID:
    return val if isinstance(val, _uuid.UUID) else _uuid.UUID(str(val))


# ---------------------------------------------------------------------------
# Fuzzy matching helpers
# ---------------------------------------------------------------------------

def fuzzy_match_ingredient(db: Session, restaurant_id, name: str) -> Ingredient | None:
    rid         = _to_uuid(restaurant_id)
    ingredients = db.query(Ingredient).filter(Ingredient.restaurant_id == rid).all()
    matches     = difflib.get_close_matches(name, [i.name for i in ingredients], n=1, cutoff=0.7)
    return next((i for i in ingredients if i.name == matches[0]), None) if matches else None


def fuzzy_match_menu_item(db: Session, restaurant_id, name: str) -> MenuItem | None:
    rid   = _to_uuid(restaurant_id)
    items = db.query(MenuItem).filter(MenuItem.restaurant_id == rid).all()
    matches = difflib.get_close_matches(name, [i.name for i in items], n=1, cutoff=0.7)
    return next((i for i in items if i.name == matches[0]), None) if matches else None


def _find_or_create_ingredient(db: Session, rid: _uuid.UUID, name: str, unit: str) -> Ingredient:
    """Fuzzy-match first; auto-create with zero cost if no match (conventions §ingestion)."""
    ing = fuzzy_match_ingredient(db, rid, name)
    if not ing:
        ing = Ingredient(
            restaurant_id         = rid,
            name                  = name,
            unit                  = unit or 'ea',
            current_cost_per_unit = Decimal('0'),
        )
        db.add(ing)
        db.flush()
        logger.info('Auto-created ingredient: %s', name)
    return ing


# ---------------------------------------------------------------------------
# Per-import-type commit helpers
# ---------------------------------------------------------------------------

def _commit_invoice(db: Session, restaurant_id: str, data: dict) -> dict:
    from app.services.inventory_service import process_invoice

    rid         = _to_uuid(restaurant_id)
    vendor_name = data.get('vendor_name') or 'Unknown Vendor'

    vendor = db.query(Vendor).filter(
        Vendor.restaurant_id == rid, Vendor.name == vendor_name,
    ).first()
    if not vendor:
        vendor = Vendor(restaurant_id=rid, name=vendor_name)
        db.add(vendor)
        db.flush()

    received_at = datetime.now(timezone.utc)
    date_str    = data.get('received_date')
    if date_str:
        try:
            received_at = datetime.fromisoformat(date_str)
        except ValueError:
            pass

    line_items = []
    skipped    = []
    for raw in data.get('line_items', []):
        ing_name = raw.get('ingredient_name', '')
        unit     = raw.get('unit') or 'ea'
        ing      = _find_or_create_ingredient(db, rid, ing_name, unit)
        qty      = Decimal(str(raw.get('quantity', 0)))
        cost     = Decimal(str(raw.get('unit_cost', 0)))
        if qty <= 0:
            skipped.append(ing_name)
            continue
        line_items.append(SimpleNamespace(
            ingredient_id     = str(ing.id),
            quantity_received = qty,
            unit_cost         = cost,
        ))

    if not line_items:
        logger.warning('Invoice commit: no valid line items — nothing written')
        return {'lines_committed': 0, 'lines_skipped': skipped}

    invoice_obj = SimpleNamespace(
        vendor_id      = str(vendor.id),
        invoice_number = data.get('invoice_number'),
        received_at    = received_at,
        total_amount   = data.get('total_amount'),
        line_items     = line_items,
    )
    invoice = process_invoice(db, restaurant_id, invoice_obj)
    return {'invoice_id': str(invoice.id), 'lines_committed': len(line_items), 'lines_skipped': skipped}


def _commit_count(db: Session, restaurant_id: str, data: dict) -> dict:
    rid       = _to_uuid(restaurant_id)
    count_at  = datetime.now(timezone.utc)
    date_str  = data.get('count_date')
    if date_str:
        try:
            count_at = datetime.fromisoformat(date_str)
        except ValueError:
            pass

    committed = []
    skipped   = []
    for item in data.get('items', []):
        ing_name = item.get('ingredient_name', '')
        qty      = item.get('quantity')
        unit     = item.get('unit') or 'ea'
        if qty is None:
            skipped.append(ing_name)
            continue
        ing = _find_or_create_ingredient(db, rid, ing_name, unit)
        db.add(InventoryCount(
            restaurant_id = rid,
            ingredient_id = ing.id,
            counted_at    = count_at,
            quantity      = Decimal(str(qty)),
        ))
        # Physical count is authoritative — update running stock.
        ing.current_stock = Decimal(str(qty))
        committed.append(ing_name)

    db.commit()
    return {'counts_committed': len(committed), 'counts_skipped': skipped}


def _commit_sales(db: Session, restaurant_id: str, data) -> dict:
    from app.services.depletion_service import deplete_from_sale

    rows      = data if isinstance(data, list) else []
    committed = 0
    skipped   = []

    for row in rows:
        item_name = row.get('menu_item_name', '')
        qty       = int(row.get('quantity_sold', 0) or 0)
        revenue   = float(row.get('gross_revenue', 0) or 0)
        date_str  = row.get('business_date', '')
        try:
            business_date = datetime.fromisoformat(str(date_str))
        except (ValueError, TypeError):
            business_date = datetime.now(timezone.utc)

        menu_item = fuzzy_match_menu_item(db, restaurant_id, item_name)
        if not menu_item:
            logger.warning('Sales commit: no menu item match for "%s" — skipping', item_name)
            skipped.append(item_name)
            continue

        deplete_from_sale(db, restaurant_id, str(menu_item.id), qty, business_date, revenue)
        committed += 1

    db.commit()
    return {'sales_committed': committed, 'sales_skipped': skipped}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_COMMIT_FNS = {
    'invoice':         _commit_invoice,
    'inventory_count': _commit_count,
    'sales':           _commit_sales,
}


def commit_staged_ingestion(
    db: Session,
    restaurant_id: str,
    staged_id: str,
    confirmed_by: str,
) -> dict:
    rid    = _to_uuid(restaurant_id)
    staged = db.get(StagedIngestion, _to_uuid(staged_id))
    if not staged or staged.restaurant_id != rid:
        raise ValueError(f'Staged ingestion {staged_id} not found')
    if staged.status != 'pending':
        raise ValueError(f'Staged ingestion is already {staged.status}')

    commit_fn = _COMMIT_FNS.get(staged.import_type)
    if not commit_fn:
        raise ValueError(f'No commit handler for import_type: {staged.import_type}')

    # Set confirmed fields before the sub-service commits — the sub-service's
    # db.commit() will persist the status change atomically with the live data.
    staged.status       = 'confirmed'
    staged.confirmed_at = datetime.now(timezone.utc)
    staged.confirmed_by = _to_uuid(confirmed_by)

    result = commit_fn(db, restaurant_id, staged.extracted_data)

    # _commit_count and _commit_sales commit internally; _commit_invoice delegates
    # to process_invoice which commits. Ensure staged status is persisted if the
    # sub-function committed before we set the fields (safety flush).
    if db.is_active:
        try:
            db.commit()
        except Exception:
            pass  # already committed by the sub-function

    return result


def reject_staged_ingestion(db: Session, restaurant_id: str, staged_id: str) -> None:
    rid    = _to_uuid(restaurant_id)
    staged = db.get(StagedIngestion, _to_uuid(staged_id))
    if not staged or staged.restaurant_id != rid:
        raise ValueError(f'Staged ingestion {staged_id} not found')
    if staged.status != 'pending':
        raise ValueError(f'Staged ingestion is already {staged.status}')
    staged.status = 'rejected'
    db.commit()
