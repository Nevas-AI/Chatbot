"""add_client_model_and_fk_columns

Revision ID: 021011ed36c1
Revises: 
Create Date: 2026-03-16 10:05:10.466481

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '021011ed36c1'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Default client UUID (deterministic so we can reference it)
DEFAULT_CLIENT_ID = uuid.UUID('00000000-0000-4000-a000-000000000001')


def upgrade() -> None:
    """Upgrade schema."""

    # 1. Create clients table
    op.create_table('clients',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('bot_name', sa.String(length=100), nullable=False),
        sa.Column('primary_color', sa.String(length=20), nullable=False),
        sa.Column('welcome_msg', sa.Text(), nullable=True),
        sa.Column('logo_url', sa.String(length=500), nullable=True),
        sa.Column('company_name', sa.String(length=200), nullable=False),
        sa.Column('support_email', sa.String(length=200), nullable=False),
        sa.Column('support_phone', sa.String(length=50), nullable=False),
        sa.Column('business_hours', sa.String(length=100), nullable=False),
        sa.Column('website_url', sa.String(length=500), nullable=True),
        sa.Column('collection_name', sa.String(length=200), nullable=False),
        sa.Column('escalation_keywords', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_clients_slug'), 'clients', ['slug'], unique=True)

    # 2. Insert a default client for existing data
    op.execute(
        sa.text(
            "INSERT INTO clients (id, name, slug, bot_name, primary_color, company_name, "
            "support_email, support_phone, business_hours, collection_name, is_active) "
            "VALUES (:id, :name, :slug, :bot_name, :primary_color, :company_name, "
            ":support_email, :support_phone, :business_hours, :collection_name, :is_active)"
        ).bindparams(
            id=str(DEFAULT_CLIENT_ID),
            name='Default',
            slug='default',
            bot_name='Neva',
            primary_color='#6366F1',
            company_name='Nevas Technologies',
            support_email='info@nevastech.com',
            support_phone='+91 0123456789',
            business_hours='Mon-Sat 9AM-6PM IST',
            collection_name='aria_knowledge',
            is_active=True,
        )
    )

    # 3. Add client_id columns as NULLABLE first
    op.add_column('chat_users', sa.Column('client_id', sa.UUID(), nullable=True))
    op.add_column('conversations', sa.Column('client_id', sa.UUID(), nullable=True))
    op.add_column('escalation_events', sa.Column('client_id', sa.UUID(), nullable=True))

    # 4. Backfill existing rows with the default client
    op.execute(sa.text(f"UPDATE chat_users SET client_id = '{DEFAULT_CLIENT_ID}' WHERE client_id IS NULL"))
    op.execute(sa.text(f"UPDATE conversations SET client_id = '{DEFAULT_CLIENT_ID}' WHERE client_id IS NULL"))
    op.execute(sa.text(f"UPDATE escalation_events SET client_id = '{DEFAULT_CLIENT_ID}' WHERE client_id IS NULL"))

    # 5. Now make columns NOT NULL
    op.alter_column('chat_users', 'client_id', nullable=False)
    op.alter_column('conversations', 'client_id', nullable=False)
    op.alter_column('escalation_events', 'client_id', nullable=False)

    # 6. Create indexes and foreign keys
    op.drop_index(op.f('ix_chat_users_identifier'), table_name='chat_users')
    op.create_index(op.f('ix_chat_users_identifier'), 'chat_users', ['identifier'], unique=False)
    op.create_index('idx_chat_users_client_identifier', 'chat_users', ['client_id', 'identifier'], unique=True)
    op.create_index(op.f('ix_chat_users_client_id'), 'chat_users', ['client_id'], unique=False)
    op.create_foreign_key('fk_chat_users_client_id', 'chat_users', 'clients', ['client_id'], ['id'], ondelete='CASCADE')

    op.create_index('idx_conversations_client_status', 'conversations', ['client_id', 'status'], unique=False)
    op.create_index(op.f('ix_conversations_client_id'), 'conversations', ['client_id'], unique=False)
    op.create_foreign_key('fk_conversations_client_id', 'conversations', 'clients', ['client_id'], ['id'], ondelete='CASCADE')

    op.create_index('idx_escalations_client_status', 'escalation_events', ['client_id', 'status'], unique=False)
    op.create_index(op.f('ix_escalation_events_client_id'), 'escalation_events', ['client_id'], unique=False)
    op.create_foreign_key('fk_escalation_events_client_id', 'escalation_events', 'clients', ['client_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_escalation_events_client_id', 'escalation_events', type_='foreignkey')
    op.drop_index(op.f('ix_escalation_events_client_id'), table_name='escalation_events')
    op.drop_index('idx_escalations_client_status', table_name='escalation_events')
    op.drop_column('escalation_events', 'client_id')

    op.drop_constraint('fk_conversations_client_id', 'conversations', type_='foreignkey')
    op.drop_index(op.f('ix_conversations_client_id'), table_name='conversations')
    op.drop_index('idx_conversations_client_status', table_name='conversations')
    op.drop_column('conversations', 'client_id')

    op.drop_constraint('fk_chat_users_client_id', 'chat_users', type_='foreignkey')
    op.drop_index(op.f('ix_chat_users_client_id'), table_name='chat_users')
    op.drop_index('idx_chat_users_client_identifier', table_name='chat_users')
    op.drop_index(op.f('ix_chat_users_identifier'), table_name='chat_users')
    op.create_index(op.f('ix_chat_users_identifier'), 'chat_users', ['identifier'], unique=True)
    op.drop_column('chat_users', 'client_id')

    op.drop_index(op.f('ix_clients_slug'), table_name='clients')
    op.drop_table('clients')
