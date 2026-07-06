"""step12_schema

Revision ID: c26262d39bbf
Revises: c4a1f2b3d5e6
Create Date: 2026-07-06 17:58:11.881425

Stripped before applying:
  - drop_index on depletion_events indexes (hand-written in Step 11, not in Alembic metadata)
  - drop_constraint on restaurant_settings_restaurant_id_key (same reason)
  - drop_index on sales_by_item / sales_summaries hypertable partition indexes (TimescaleDB artifact)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c26262d39bbf'
down_revision: Union[str, Sequence[str], None] = 'c4a1f2b3d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('channel_fees',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('restaurant_id', sa.UUID(), nullable=False),
        sa.Column('channel', sa.String(length=30), nullable=False),
        sa.Column('commission_rate', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('labor_entries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('restaurant_id', sa.UUID(), nullable=False),
        sa.Column('business_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('hours', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('labor_cost', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('sale_adjustments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('restaurant_id', sa.UUID(), nullable=False),
        sa.Column('business_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('adjustment_type', sa.String(length=30), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('employee_str', sa.String(length=200), nullable=True),
        sa.Column('daypart', sa.String(length=30), nullable=True),
        sa.Column('source', sa.String(length=30), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('weather_days',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('restaurant_id', sa.UUID(), nullable=False),
        sa.Column('business_date', sa.Date(), nullable=False),
        sa.Column('precip_mm', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('tmax', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('tmin', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('restaurant_id', 'business_date', name='uq_weather_restaurant_date'),
    )
    # Column additions — no drop_index lines stripped above
    op.add_column('recipe_lines',         sa.Column('channel', sa.String(length=30), nullable=True))
    op.add_column('restaurant_settings',  sa.Column('seat_count', sa.Integer(), nullable=True))
    op.add_column('restaurant_settings',  sa.Column('lat', sa.Numeric(precision=9, scale=6), nullable=True))
    op.add_column('restaurant_settings',  sa.Column('lon', sa.Numeric(precision=9, scale=6), nullable=True))
    op.add_column('restaurant_settings',  sa.Column('restaurant_type', sa.String(length=30), nullable=True))
    op.add_column('sales_by_item',        sa.Column('source', sa.String(length=30), nullable=True))
    op.add_column('sales_by_item',        sa.Column('channel', sa.String(length=30), nullable=True))
    op.add_column('sales_summaries',      sa.Column('channel', sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column('sales_summaries',    'channel')
    op.drop_column('sales_by_item',      'channel')
    op.drop_column('sales_by_item',      'source')
    op.drop_column('restaurant_settings','restaurant_type')
    op.drop_column('restaurant_settings','lon')
    op.drop_column('restaurant_settings','lat')
    op.drop_column('restaurant_settings','seat_count')
    op.drop_column('recipe_lines',       'channel')
    op.drop_table('weather_days')
    op.drop_table('sale_adjustments')
    op.drop_table('labor_entries')
    op.drop_table('channel_fees')
