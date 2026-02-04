"""Add pickup and pickup_address tables

Revision ID: 001_pickup_tables
Revises: 
Create Date: 2026-02-03 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_pickup_tables'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create pickup_address table
    op.create_table('pickup_address',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('phone', sa.String(length=50), nullable=False),
    sa.Column('address_line1', sa.String(length=200), nullable=False),
    sa.Column('city_locality', sa.String(length=100), nullable=False),
    sa.Column('state_province', sa.String(length=100), nullable=False),
    sa.Column('postal_code', sa.String(length=20), nullable=False),
    sa.Column('country_code', sa.String(length=2), nullable=False),
    sa.Column('email', sa.String(length=100), nullable=True),
    sa.Column('company_name', sa.String(length=100), nullable=True),
    sa.Column('address_line2', sa.String(length=200), nullable=True),
    sa.Column('address_line3', sa.String(length=200), nullable=True),
    sa.Column('address_residential_indicator', sa.String(length=10), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    
    # Create pickup table
    op.create_table('pickup',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('pickup_id', sa.String(length=50), nullable=False),
    sa.Column('pickup_address_id', sa.Integer(), nullable=False),
    sa.Column('label_ids', postgresql.ARRAY(sa.String()), nullable=False),
    sa.Column('contact_details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('pickup_window', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('pickup_notes', sa.Text(), nullable=True),
    sa.Column('carrier_id', sa.String(length=50), nullable=True),
    sa.Column('confirmation_number', sa.String(length=50), nullable=True),
    sa.Column('warehouse_id', sa.String(length=50), nullable=True),
    sa.Column('notification_job_id', sa.String(length=100), nullable=True),
    sa.Column('notification_sent', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['pickup_address_id'], ['pickup_address.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pickup_is_deleted'), 'pickup', ['is_deleted'], unique=False)
    op.create_index(op.f('ix_pickup_pickup_address_id'), 'pickup', ['pickup_address_id'], unique=False)
    op.create_index(op.f('ix_pickup_pickup_id'), 'pickup', ['pickup_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_pickup_pickup_id'), table_name='pickup')
    op.drop_index(op.f('ix_pickup_pickup_address_id'), table_name='pickup')
    op.drop_index(op.f('ix_pickup_is_deleted'), table_name='pickup')
    op.drop_table('pickup')
    op.drop_table('pickup_address')
