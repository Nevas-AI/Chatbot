"""add_booking_url_to_clients

Revision ID: a4b8c2d9e1f3
Revises: 021011ed36c1
Create Date: 2026-04-28 11:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4b8c2d9e1f3'
down_revision: Union[str, Sequence[str], None] = '021011ed36c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add booking_url column to clients table for Microsoft Bookings integration."""
    op.add_column('clients', sa.Column('booking_url', sa.String(length=1000), nullable=True))


def downgrade() -> None:
    """Remove booking_url column from clients table."""
    op.drop_column('clients', 'booking_url')
