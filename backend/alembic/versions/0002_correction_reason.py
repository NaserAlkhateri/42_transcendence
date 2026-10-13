"""corrections: a reason on every correction, and at most one correction per record

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-13 23:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('service_records', sa.Column('correction_reason', sa.Enum('odometer', 'service_date', 'work_done', 'category', 'other', name='correction_reason', native_enum=False, create_constraint=True, length=32), nullable=True))
    # Existing corrections predate the reason: mark them "other". History is append-only, so the trigger is
    # lifted for this one backfill inside the migration's transaction and restored before it commits.
    op.execute("ALTER TABLE service_records DISABLE TRIGGER service_records_append_only")
    op.execute("UPDATE service_records SET correction_reason = 'other' WHERE corrects_record_id IS NOT NULL")
    op.execute("ALTER TABLE service_records ENABLE TRIGGER service_records_append_only")
    op.create_check_constraint(
        'correction_has_reason', 'service_records', '(corrects_record_id IS NULL) = (correction_reason IS NULL)'
    )
    op.drop_index(op.f('ix_service_records_corrects_record_id'), table_name='service_records')
    op.create_index(op.f('ix_service_records_corrects_record_id'), 'service_records', ['corrects_record_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_service_records_corrects_record_id'), table_name='service_records')
    op.create_index(op.f('ix_service_records_corrects_record_id'), 'service_records', ['corrects_record_id'], unique=False)
    op.drop_constraint('correction_has_reason', 'service_records', type_='check')
    op.execute("ALTER TABLE service_records DISABLE TRIGGER service_records_append_only")
    op.drop_column('service_records', 'correction_reason')
    op.execute("ALTER TABLE service_records ENABLE TRIGGER service_records_append_only")
