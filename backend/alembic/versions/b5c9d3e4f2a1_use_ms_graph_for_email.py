"""use_ms_graph_for_email

Revision ID: b5c9d3e4f2a1
Revises: a4b8c2d9e1f3
Create Date: 2026-04-30 09:17:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5c9d3e4f2a1'
down_revision: Union[str, None] = 'a4b8c2d9e1f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new MS Graph columns
    op.add_column('clients', sa.Column('ms_tenant_id', sa.String(length=100), nullable=True))
    op.add_column('clients', sa.Column('ms_client_id', sa.String(length=100), nullable=True))
    op.add_column('clients', sa.Column('ms_client_secret', sa.String(length=500), nullable=True))
    
    # Drop old column
    op.drop_column('clients', 'lead_email_password')


def downgrade() -> None:
    # Re-add old column
    op.add_column('clients', sa.Column('lead_email_password', sa.String(length=500), nullable=True))
    
    # Drop new MS Graph columns
    op.drop_column('clients', 'ms_client_secret')
    op.drop_column('clients', 'ms_client_id')
    op.drop_column('clients', 'ms_tenant_id')
