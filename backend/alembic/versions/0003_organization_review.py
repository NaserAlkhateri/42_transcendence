"""organizations: review timestamp and a required reason on rejection (NA-03)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-15 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('organizations', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('organizations', sa.Column('rejection_reason', sa.String(length=500), nullable=True))
    # Rows rejected before reasons existed get a neutral one so the constraint holds.
    op.execute("UPDATE organizations SET rejection_reason = 'Rejected before reasons were recorded.' WHERE status = 'rejected'")
    op.create_check_constraint(
        'rejection_has_reason', 'organizations', "(status = 'rejected') = (rejection_reason IS NOT NULL)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('rejection_has_reason', 'organizations', type_='check')
    op.drop_column('organizations', 'rejection_reason')
    op.drop_column('organizations', 'reviewed_at')
