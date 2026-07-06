"""add_insights_tables

Revision ID: c4a1f2b3d5e6
Revises: 0a3dc7dbfe8f
Create Date: 2026-07-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c4a1f2b3d5e6'
down_revision: Union[str, None] = '0a3dc7dbfe8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'restaurant_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('restaurants.id'), nullable=False, unique=True),
        sa.Column('monthly_fixed_costs', sa.Numeric(12, 2), nullable=True),
        sa.Column('target_food_cost_pct', sa.Numeric(5, 2), server_default='30.0'),
        sa.Column('menu_eng_popularity_factor', sa.Numeric(4, 2), server_default='0.70'),
        sa.Column('par_min_cover_days', sa.Integer(), server_default='4'),
        sa.Column('par_max_cover_days', sa.Integer(), server_default='21'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_restaurant_settings_restaurant_id',
                    'restaurant_settings', ['restaurant_id'], unique=True)

    op.create_table(
        'depletion_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('restaurant_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('restaurants.id'), nullable=False),
        sa.Column('ingredient_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('ingredients.id'), nullable=False),
        sa.Column('menu_item_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('menu_items.id'), nullable=False),
        sa.Column('quantity', sa.Numeric(10, 4), nullable=False),
        sa.Column('depleted_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_depletion_events_restaurant_ingredient',
                    'depletion_events', ['restaurant_id', 'ingredient_id'])
    op.create_index('ix_depletion_events_depleted_at',
                    'depletion_events', ['depleted_at'])


def downgrade() -> None:
    op.drop_table('depletion_events')
    op.drop_table('restaurant_settings')
