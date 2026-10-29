"""Initial schema with incidents, emergency units, dispatch assignments, and audit ledger.

Revision ID: 001_initial_tables
Revises: 
Create Date: 2026-10-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '001_initial_tables'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Incidents Table
    op.create_table(
        'incidents',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('incident_number', sa.String(length=50), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False, server_default='UNKNOWN'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='REPORTED'),
        sa.Column('severity', sa.String(length=50), nullable=False, server_default='LEVEL_3_MODERATE'),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('address', sa.String(length=255), nullable=True),
        sa.Column('requires_human_review', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('assessment_data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_incidents_incident_number', 'incidents', ['incident_number'], unique=True)

    # 2. Emergency Units Table
    op.create_table(
        'emergency_units',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('callsign', sa.String(length=50), nullable=False, unique=True),
        sa.Column('unit_type', sa.String(length=50), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='AVAILABLE'),
        sa.Column('station', sa.String(length=100), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_emergency_units_callsign', 'emergency_units', ['callsign'], unique=True)

    # 3. Dispatch Assignments Table
    op.create_table(
        'dispatch_assignments',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('incident_id', sa.String(length=36), sa.ForeignKey('incidents.id'), nullable=False),
        sa.Column('unit_id', sa.String(length=36), sa.ForeignKey('emergency_units.id'), nullable=False),
        sa.Column('dispatcher_id', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='DISPATCHED'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('on_scene_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cleared_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_dispatch_assignments_incident_id', 'dispatch_assignments', ['incident_id'])
    op.create_index('ix_dispatch_assignments_unit_id', 'dispatch_assignments', ['unit_id'])

    # 4. Immutable Audit Ledger Table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('incident_id', sa.String(length=36), nullable=False),
        sa.Column('actor', sa.String(length=50), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('details', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_audit_logs_incident_id', 'audit_logs', ['incident_id'])

def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('dispatch_assignments')
    op.drop_table('emergency_units')
    op.drop_table('incidents')
