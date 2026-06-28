# Step 3 — Recipe Engine & Inventory Auto-Depletion

**Estimated time:** 8–12 hours
**Phase:** 1 (Foundation)
**Depends on:** Step 2.

---

## Goal

The connective tissue of the platform. When a sale is recorded, ingredients are automatically decremented from stock and food cost is calculated. When an invoice is received, ingredient costs update everywhere instantly. Everything downstream (dashboards, alerts, forecasting) depends on this.

## 3.1 Invoice processing — `app/services/inventory_service.py`

```python
from sqlalchemy.orm import Session
from app.models.inventory import Ingredient, VendorInvoice, InvoiceLineItem, WasteLog
from decimal import Decimal
from datetime import datetime, timezone

def process_invoice(db: Session, restaurant_id: str, invoice_data) -> VendorInvoice:
    """Records invoice, updates ingredient cost and stock — single transaction."""
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
        ingredient = db.get(Ingredient, line.ingredient_id)
        if not ingredient or ingredient.restaurant_id != restaurant_id:
            raise ValueError(f'Ingredient {line.ingredient_id} not found')
        extended = Decimal(str(line.quantity_received)) * Decimal(str(line.unit_cost))
        db.add(InvoiceLineItem(
            invoice_id        = invoice.id,
            ingredient_id     = line.ingredient_id,
            quantity_received = line.quantity_received,
            unit_cost         = line.unit_cost,
            extended_cost     = extended,
        ))
        # KEY: update cost and stock on the ingredient itself
        ingredient.current_cost_per_unit = line.unit_cost
        ingredient.current_stock = (ingredient.current_stock or 0) + line.quantity_received

    db.commit()
    db.refresh(invoice)
    return invoice

def log_waste(db: Session, restaurant_id: str, ingredient_id: str,
              quantity: float, reason: str, notes: str = None) -> WasteLog:
    ingredient = db.get(Ingredient, ingredient_id)
    if not ingredient or ingredient.restaurant_id != restaurant_id:
        raise ValueError('Ingredient not found')
    waste = WasteLog(
        restaurant_id = restaurant_id, ingredient_id = ingredient_id,
        logged_at     = datetime.now(timezone.utc), quantity = quantity,
        reason        = reason, cost_at_time = ingredient.current_cost_per_unit,
        notes         = notes,
    )
    db.add(waste)
    ingredient.current_stock = max(0, (ingredient.current_stock or 0) - quantity)
    db.commit()
    return waste
```

## 3.2 Depletion engine — `app/services/depletion_service.py`

```python
from sqlalchemy.orm import Session
from app.models.recipe import MenuItem
from app.models.inventory import Ingredient
from app.models.sales import SalesByItem
from decimal import Decimal
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def deplete_from_sale(db: Session, restaurant_id: str, menu_item_id: str,
                      quantity_sold: int, business_date: datetime,
                      gross_revenue: float) -> SalesByItem:
    menu_item = db.get(MenuItem, menu_item_id)
    if not menu_item or menu_item.restaurant_id != restaurant_id:
        raise ValueError(f'Menu item {menu_item_id} not found')

    total_food_cost = Decimal('0')
    for recipe_line in menu_item.recipe_lines:
        ingredient = recipe_line.ingredient
        if not ingredient:
            logger.warning(f'RecipeLine {recipe_line.id} has no ingredient — skipping')
            continue
        qty_consumed = Decimal(str(recipe_line.quantity)) * quantity_sold
        prev_stock   = ingredient.current_stock or Decimal('0')
        ingredient.current_stock = max(Decimal('0'), prev_stock - qty_consumed)
        if prev_stock < qty_consumed:
            # Negative stock = data quality issue, not a code bug. Surface it.
            logger.warning(
                f'Stock for {ingredient.name} would go negative. '
                f'Check inventory count accuracy for restaurant {restaurant_id}.'
            )
        if ingredient.current_cost_per_unit:
            total_food_cost += qty_consumed * ingredient.current_cost_per_unit

    record = SalesByItem(
        restaurant_id = restaurant_id, menu_item_id = menu_item_id,
        business_date = business_date, quantity_sold = quantity_sold,
        gross_revenue = Decimal(str(gross_revenue)), food_cost = total_food_cost,
    )
    db.add(record)
    # NOTE: caller commits — allows batching
    return record

def deplete_batch(db: Session, restaurant_id: str,
                  sales: list[dict], business_date: datetime) -> list[SalesByItem]:
    """Process multiple item sales in one transaction (end-of-day POS import)."""
    records = [
        deplete_from_sale(db, restaurant_id, s['menu_item_id'],
                          s['quantity'], business_date, s['revenue'])
        for s in sales
    ]
    db.commit()
    return records
```

## 3.3 Food cost service — `app/services/food_cost_service.py`

```python
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from app.models.sales import SalesByItem
from datetime import datetime

def get_food_cost_summary(db, restaurant_id, date_from, date_to):
    r = db.execute(select(
        func.sum(SalesByItem.gross_revenue).label('revenue'),
        func.sum(SalesByItem.food_cost).label('food_cost'),
    ).where(
        SalesByItem.restaurant_id == restaurant_id,
        SalesByItem.business_date >= date_from,
        SalesByItem.business_date <= date_to,
        SalesByItem.menu_item_id.is_not(None),
    )).one()
    rev = float(r.revenue or 0); fc = float(r.food_cost or 0)
    return {
        'date_from': date_from.isoformat(), 'date_to': date_to.isoformat(),
        'total_revenue': rev, 'total_food_cost': fc,
        'food_cost_pct': round(fc/rev*100, 2) if rev > 0 else None,
    }

def get_item_profitability(db, restaurant_id, date_from, date_to, limit=20):
    rows = db.execute(select(
        SalesByItem.menu_item_id,
        func.sum(SalesByItem.quantity_sold).label('qty'),
        func.sum(SalesByItem.gross_revenue).label('rev'),
        func.sum(SalesByItem.food_cost).label('fc'),
        (func.sum(SalesByItem.gross_revenue) -
         func.sum(SalesByItem.food_cost)).label('profit'),
    ).where(
        SalesByItem.restaurant_id == restaurant_id,
        SalesByItem.business_date >= date_from,
        SalesByItem.business_date <= date_to,
        SalesByItem.menu_item_id.is_not(None),
    ).group_by(SalesByItem.menu_item_id
    ).order_by(
        (func.sum(SalesByItem.gross_revenue) -
         func.sum(SalesByItem.food_cost)).desc()
    ).limit(limit)).all()
    return [{'menu_item_id': str(r.menu_item_id), 'quantity_sold': r.qty,
             'revenue': float(r.rev or 0), 'food_cost': float(r.fc or 0),
             'gross_profit': float(r.profit or 0),
             'food_cost_pct': round(float(r.fc or 0)/float(r.rev)*100,2) if r.rev else None}
            for r in rows]
```

---

## Watch out

**Negative stock is a signal, not a bug.** It means an inventory count was wrong, an invoice wasn't recorded, or waste wasn't logged. Log these warnings visibly — they are among the most actionable things you can surface to an operator. Do not silently suppress them.

## Done when

You can manually insert a menu item with recipe lines, call `deplete_from_sale`, and verify: (1) ingredient `current_stock` decreased, (2) a `SalesByItem` row was created with the correct `food_cost`, (3) `get_food_cost_summary` returns a sensible percentage.

## Then

Update checkbox in `CLAUDE.md`, `git commit`, move to `step-04-api.md`.
