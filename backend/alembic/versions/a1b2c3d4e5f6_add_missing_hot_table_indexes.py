"""add_missing_hot_table_indexes

Revision ID: a1b2c3d4e5f6
Revises: 21d2a56b8659
Create Date: 2026-07-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '21d2a56b8659'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'ix_sale_adjustments_rid_date',
        'sale_adjustments',
        ['restaurant_id', 'business_date'],
        unique=False,
    )
    op.create_index(
        'ix_labor_entries_rid_date',
        'labor_entries',
        ['restaurant_id', 'business_date'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_labor_entries_rid_date',    table_name='labor_entries')
    op.drop_index('ix_sale_adjustments_rid_date', table_name='sale_adjustments')
