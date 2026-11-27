"""Store private organization document metadata and removal history."""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("object_key", sa.String(512), nullable=False, unique=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("purged_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("size_bytes > 0", name=op.f("ck_organization_documents_size_positive")),
    )
    op.create_index(op.f("ix_organization_documents_organization_id"), "organization_documents", ["organization_id"])


def downgrade() -> None:
    op.drop_table("organization_documents")
