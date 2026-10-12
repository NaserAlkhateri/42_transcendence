"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-12 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('organizations',
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('kind', sa.Enum('dealership', 'workshop', name='organization_kind', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('registration_number', sa.String(length=64), nullable=False),
    sa.Column('emirate', sa.String(length=64), nullable=True),
    sa.Column('status', sa.Enum('pending', 'approved', 'rejected', name='organization_status', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_organizations')),
    sa.UniqueConstraint('registration_number', name=op.f('uq_organizations_registration_number'))
    )
    op.create_index(op.f('ix_organizations_status'), 'organizations', ['status'], unique=False)
    op.create_table('users',
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=120), nullable=False),
    sa.Column('role', sa.Enum('consumer', 'platform_admin', name='user_role', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('status', sa.Enum('active', 'disabled', name='user_status', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('must_change_password', sa.Boolean(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('email = lower(email)', name=op.f('ck_users_email_lowercase')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('vehicles',
    sa.Column('vin', sa.String(length=17), nullable=False),
    sa.Column('make', sa.String(length=64), nullable=True),
    sa.Column('model', sa.String(length=64), nullable=True),
    sa.Column('model_year', sa.Integer(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("vin ~ '^[A-HJ-NPR-Z0-9]{17}$'", name=op.f('ck_vehicles_vin_format')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_vehicles')),
    sa.UniqueConstraint('vin', name=op.f('uq_vehicles_vin'))
    )
    op.create_table('api_keys',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('created_by_id', sa.Uuid(), nullable=True),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('key_prefix', sa.String(length=16), nullable=False),
    sa.Column('key_hash', sa.String(length=255), nullable=False),
    sa.Column('scopes', postgresql.ARRAY(sa.String(length=32)), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name=op.f('fk_api_keys_created_by_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_api_keys_organization_id_organizations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_api_keys')),
    sa.UniqueConstraint('key_prefix', name=op.f('uq_api_keys_key_prefix'))
    )
    op.create_index(op.f('ix_api_keys_organization_id'), 'api_keys', ['organization_id'], unique=False)
    op.create_table('audit_events',
    sa.Column('actor_id', sa.Uuid(), nullable=True),
    sa.Column('actor_label', sa.String(length=320), nullable=False),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('target_type', sa.String(length=64), nullable=False),
    sa.Column('target_id', sa.String(length=64), nullable=False),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_audit_events_actor_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_events'))
    )
    op.create_index(op.f('ix_audit_events_actor_id'), 'audit_events', ['actor_id'], unique=False)
    op.create_index('ix_audit_events_created_at', 'audit_events', ['created_at'], unique=False)
    op.create_index('ix_audit_events_target', 'audit_events', ['target_type', 'target_id'], unique=False)
    op.create_table('notifications',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('event_type', sa.String(length=64), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notifications_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications'))
    )
    op.create_index('ix_notifications_user_created', 'notifications', ['user_id', 'created_at'], unique=False)
    op.create_table('organization_members',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('role', sa.Enum('entity_admin', 'entity_staff', name='member_role', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('status', sa.Enum('active', 'inactive', name='member_status', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_organization_members_organization_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_organization_members_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_organization_members')),
    sa.UniqueConstraint('organization_id', 'user_id', name=op.f('uq_organization_members_organization_id_user_id'))
    )
    op.create_index(op.f('ix_organization_members_user_id'), 'organization_members', ['user_id'], unique=False)
    op.create_table('service_records',
    sa.Column('vehicle_id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=True),
    sa.Column('staff_id', sa.Uuid(), nullable=True),
    sa.Column('organization_name', sa.String(length=200), nullable=False),
    sa.Column('staff_name', sa.String(length=120), nullable=False),
    sa.Column('category', sa.Enum('maintenance', 'repair', name='record_category', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('work_codes', postgresql.ARRAY(sa.String(length=32)), nullable=False),
    sa.Column('odometer_km', sa.Integer(), nullable=False),
    sa.Column('service_date', sa.Date(), nullable=False),
    sa.Column('is_mileage_flagged', sa.Boolean(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('corrects_record_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('corrects_record_id IS NULL OR corrects_record_id <> id', name=op.f('ck_service_records_no_self_correction')),
    sa.CheckConstraint('odometer_km >= 0', name=op.f('ck_service_records_odometer_non_negative')),
    sa.ForeignKeyConstraint(['corrects_record_id'], ['service_records.id'], name=op.f('fk_service_records_corrects_record_id_service_records'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_service_records_organization_id_organizations'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['staff_id'], ['users.id'], name=op.f('fk_service_records_staff_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], name=op.f('fk_service_records_vehicle_id_vehicles'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_service_records'))
    )
    op.create_index(op.f('ix_service_records_corrects_record_id'), 'service_records', ['corrects_record_id'], unique=False)
    op.create_index(op.f('ix_service_records_is_mileage_flagged'), 'service_records', ['is_mileage_flagged'], unique=False)
    op.create_index(op.f('ix_service_records_organization_id'), 'service_records', ['organization_id'], unique=False)
    op.create_index(op.f('ix_service_records_staff_id'), 'service_records', ['staff_id'], unique=False)
    op.create_index('ix_service_records_vehicle_timeline', 'service_records', ['vehicle_id', 'service_date', 'created_at'], unique=False)
    op.create_table('sessions',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=128), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sessions')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_sessions_token_hash'))
    )
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'], unique=False)
    op.create_table('watchlists',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('vehicle_id', sa.Uuid(), nullable=False),
    sa.Column('notifications_enabled', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_watchlists_user_id_users'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], name=op.f('fk_watchlists_vehicle_id_vehicles'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_watchlists')),
    sa.UniqueConstraint('user_id', 'vehicle_id', name=op.f('uq_watchlists_user_id_vehicle_id'))
    )
    op.create_index(op.f('ix_watchlists_vehicle_id'), 'watchlists', ['vehicle_id'], unique=False)
    op.create_table('attachments',
    sa.Column('service_record_id', sa.Uuid(), nullable=False),
    sa.Column('uploaded_by_id', sa.Uuid(), nullable=True),
    sa.Column('object_key', sa.String(length=512), nullable=False),
    sa.Column('file_name', sa.String(length=255), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('access_scope', sa.Enum('organization', 'platform', name='attachment_scope', native_enum=False, create_constraint=True, length=32), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('size_bytes > 0', name=op.f('ck_attachments_size_positive')),
    sa.ForeignKeyConstraint(['service_record_id'], ['service_records.id'], name=op.f('fk_attachments_service_record_id_service_records'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['uploaded_by_id'], ['users.id'], name=op.f('fk_attachments_uploaded_by_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_attachments')),
    sa.UniqueConstraint('object_key', name=op.f('uq_attachments_object_key'))
    )
    op.create_index(op.f('ix_attachments_service_record_id'), 'attachments', ['service_record_id'], unique=False)
    op.create_table('partner_watchlists',
    sa.Column('api_key_id', sa.Uuid(), nullable=False),
    sa.Column('vehicle_id', sa.Uuid(), nullable=False),
    sa.Column('preferences', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], name=op.f('fk_partner_watchlists_api_key_id_api_keys'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], name=op.f('fk_partner_watchlists_vehicle_id_vehicles'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_partner_watchlists')),
    sa.UniqueConstraint('api_key_id', 'vehicle_id', name=op.f('uq_partner_watchlists_api_key_id_vehicle_id'))
    )
    op.create_index(op.f('ix_partner_watchlists_vehicle_id'), 'partner_watchlists', ['vehicle_id'], unique=False)

    # Service history is append-only (doc/ARCHITECTURE.md, critical domain logic 5).
    op.execute(
        """
        CREATE FUNCTION service_records_append_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'service_records is append-only: DELETE is not allowed'
                    USING ERRCODE = 'restrict_violation';
            END IF;
            -- The only allowed UPDATE is the FK "ON DELETE SET NULL" when an organization or user is deleted.
            IF (to_jsonb(NEW) - 'organization_id' - 'staff_id') IS DISTINCT FROM (to_jsonb(OLD) - 'organization_id' - 'staff_id')
               OR (NEW.organization_id IS DISTINCT FROM OLD.organization_id AND NEW.organization_id IS NOT NULL)
               OR (NEW.staff_id IS DISTINCT FROM OLD.staff_id AND NEW.staff_id IS NOT NULL) THEN
                RAISE EXCEPTION 'service_records is append-only: only organization_id/staff_id may be cleared by a deletion'
                    USING ERRCODE = 'restrict_violation';
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER service_records_append_only
        BEFORE UPDATE OR DELETE ON service_records
        FOR EACH ROW EXECUTE FUNCTION service_records_append_only();
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS service_records_append_only ON service_records")
    op.execute("DROP FUNCTION IF EXISTS service_records_append_only()")
    op.drop_index(op.f('ix_partner_watchlists_vehicle_id'), table_name='partner_watchlists')
    op.drop_table('partner_watchlists')
    op.drop_index(op.f('ix_attachments_service_record_id'), table_name='attachments')
    op.drop_table('attachments')
    op.drop_index(op.f('ix_watchlists_vehicle_id'), table_name='watchlists')
    op.drop_table('watchlists')
    op.drop_index(op.f('ix_sessions_user_id'), table_name='sessions')
    op.drop_table('sessions')
    op.drop_index(op.f('ix_service_records_corrects_record_id'), table_name='service_records')
    op.drop_index(op.f('ix_service_records_is_mileage_flagged'), table_name='service_records')
    op.drop_index(op.f('ix_service_records_organization_id'), table_name='service_records')
    op.drop_index(op.f('ix_service_records_staff_id'), table_name='service_records')
    op.drop_index('ix_service_records_vehicle_timeline', table_name='service_records')
    op.drop_table('service_records')
    op.drop_index(op.f('ix_organization_members_user_id'), table_name='organization_members')
    op.drop_table('organization_members')
    op.drop_index('ix_notifications_user_created', table_name='notifications')
    op.drop_table('notifications')
    op.drop_index(op.f('ix_audit_events_actor_id'), table_name='audit_events')
    op.drop_index('ix_audit_events_created_at', table_name='audit_events')
    op.drop_index('ix_audit_events_target', table_name='audit_events')
    op.drop_table('audit_events')
    op.drop_index(op.f('ix_api_keys_organization_id'), table_name='api_keys')
    op.drop_table('api_keys')
    op.drop_table('vehicles')
    op.drop_table('users')
    op.drop_index(op.f('ix_organizations_status'), table_name='organizations')
    op.drop_table('organizations')
