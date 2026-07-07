"""step13_schema

Revision ID: 21d2a56b8659
Revises: c26262d39bbf
Create Date: 2026-07-06 21:32:06.397193

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '21d2a56b8659'
down_revision: Union[str, Sequence[str], None] = 'c26262d39bbf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('benchmark_stats',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('metric', sa.String(length=50), nullable=False),
    sa.Column('cohort', sa.String(length=50), nullable=False),
    sa.Column('stat_date', sa.Date(), nullable=False),
    sa.Column('p25', sa.Numeric(precision=10, scale=4), nullable=False),
    sa.Column('p50', sa.Numeric(precision=10, scale=4), nullable=False),
    sa.Column('p75', sa.Numeric(precision=10, scale=4), nullable=False),
    sa.Column('n', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('metric', 'cohort', 'stat_date', name='uq_benchmark_metric_cohort_date')
    )
    op.create_table('menu_price_events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('restaurant_id', sa.UUID(), nullable=False),
    sa.Column('menu_item_id', sa.UUID(), nullable=False),
    sa.Column('old_price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('new_price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['menu_item_id'], ['menu_items.id'], ),
    sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_menu_price_events_rid_item', 'menu_price_events', ['restaurant_id', 'menu_item_id'], unique=False)
    # Spurious drop_index/drop_constraint lines from TimescaleDB and existing-index artifacts stripped.


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_menu_price_events_rid_item', table_name='menu_price_events')
    op.drop_table('menu_price_events')
    op.drop_table('benchmark_stats')
