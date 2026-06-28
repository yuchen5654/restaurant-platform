import csv
import io
from sqlalchemy.orm import Session

from app.models.ingestion import CsvColumnMapping, StagedIngestion

FIELD_SCHEMAS = {
    'sales':           ['business_date', 'menu_item_name', 'quantity_sold', 'gross_revenue'],
    'inventory_count': ['ingredient_name', 'quantity', 'unit', 'counted_at'],
    'invoice':         ['vendor_name', 'ingredient_name', 'quantity_received', 'unit', 'unit_cost'],
    'labor':           ['employee_name', 'role', 'hours', 'pay_rate'],
}


def parse_csv(content: str):
    reader  = csv.DictReader(io.StringIO(content))
    headers = list(reader.fieldnames or [])
    rows    = [dict(r) for r in reader]
    return headers, rows


def apply_mapping(rows: list[dict], mapping: dict) -> list[dict]:
    """Rename CSV column keys to platform field names using the caller-supplied mapping."""
    return [{mapping[k]: v.strip() for k, v in row.items() if k in mapping} for row in rows]


def stage_csv_import(
    db: Session,
    restaurant_id: str,
    import_type: str,
    file_content: str,
    mapping: dict,
    save_mapping: bool = True,
    label: str = '',
) -> StagedIngestion:
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
        extracted_data    = mapped_rows,          # store native list — JSON column serialises it
        confidence_scores = {f: 1.0 for f in required},
    )
    db.add(staged)

    if save_mapping and label:
        existing = (
            db.query(CsvColumnMapping)
            .filter(
                CsvColumnMapping.restaurant_id == restaurant_id,
                CsvColumnMapping.import_type   == import_type,
                CsvColumnMapping.source_label  == label,
            )
            .first()
        )
        if existing:
            existing.mapping = mapping
        else:
            db.add(CsvColumnMapping(
                restaurant_id = restaurant_id,
                import_type   = import_type,
                source_label  = label,
                mapping       = mapping,
            ))

    db.commit()
    db.refresh(staged)
    return staged
