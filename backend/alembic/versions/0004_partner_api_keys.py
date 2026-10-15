"""partner API keys belong to named partners, not organizations; watch labels and check times (NA-05)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-15 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f('ix_api_keys_organization_id'), table_name='api_keys')
    op.drop_constraint(op.f('fk_api_keys_organization_id_organizations'), 'api_keys', type_='foreignkey')
    op.drop_column('api_keys', 'organization_id')
    op.alter_column('api_keys', 'name', new_column_name='partner_name', type_=sa.String(length=120))
    op.drop_constraint(op.f('fk_api_keys_created_by_id_users'), 'api_keys', type_='foreignkey')
    op.alter_column('api_keys', 'created_by_id', new_column_name='issued_by_id')
    op.create_foreign_key(
        op.f('fk_api_keys_issued_by_id_users'), 'api_keys', 'users', ['issued_by_id'], ['id'], ondelete='SET NULL'
    )
    op.add_column('partner_watchlists', sa.Column('label', sa.String(length=100), nullable=True))
    op.add_column('partner_watchlists', sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema. Keys cannot be given back an organization, so they are removed."""
    op.drop_column('partner_watchlists', 'last_checked_at')
    op.drop_column('partner_watchlists', 'label')
    op.execute("DELETE FROM api_keys")
    op.drop_constraint(op.f('fk_api_keys_issued_by_id_users'), 'api_keys', type_='foreignkey')
    op.alter_column('api_keys', 'issued_by_id', new_column_name='created_by_id')
    op.create_foreign_key(
        op.f('fk_api_keys_created_by_id_users'), 'api_keys', 'users', ['created_by_id'], ['id'], ondelete='SET NULL'
    )
    op.alter_column('api_keys', 'partner_name', new_column_name='name', type_=sa.String(length=100))
    op.add_column('api_keys', sa.Column('organization_id', sa.Uuid(), nullable=False))
    op.create_foreign_key(
        op.f('fk_api_keys_organization_id_organizations'), 'api_keys', 'organizations', ['organization_id'], ['id'],
        ondelete='CASCADE',
    )
    op.create_index(op.f('ix_api_keys_organization_id'), 'api_keys', ['organization_id'], unique=False)
