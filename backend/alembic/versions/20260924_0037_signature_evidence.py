"""immutable school receiving and complaint signature evidence"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20260924_0037'
down_revision = '20260924_0036'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('signature_evidence',
        sa.Column('signature_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_type', sa.String(30), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('purpose', sa.String(100), nullable=False),
        sa.Column('signed_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('signed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('signer_snapshot', postgresql.JSONB(), nullable=False),
        sa.Column('file_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('storage_reference', sa.String(1024), nullable=False),
        sa.Column('content_type', sa.String(30), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('sha256_hex', sa.String(64), nullable=False),
        sa.Column('status', sa.String(20), server_default='CAPTURED', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id','signed_by'], ['app_user.tenant_id','app_user.user_id'], name='fk_signature_tenant_user', ondelete='RESTRICT'),
        sa.UniqueConstraint('tenant_id','signature_id', name='uq_signature_tenant_id'),
        sa.UniqueConstraint('tenant_id','entity_type','entity_id','purpose', name='uq_signature_target_purpose'),
        sa.CheckConstraint("entity_type IN ('SCHOOL_RECEIVING','COMPLAINT')", name='ck_signature_entity_type'),
        sa.CheckConstraint("content_type IN ('image/png','image/webp')", name='ck_signature_content_type'),
        sa.CheckConstraint('length(sha256_hex) = 64', name='ck_signature_sha256'),
        sa.CheckConstraint('length(trim(purpose)) > 0', name='ck_signature_purpose'),
        sa.CheckConstraint("jsonb_typeof(signer_snapshot) = 'object'", name='ck_signature_snapshot'),
        sa.CheckConstraint("status = 'CAPTURED'", name='ck_signature_status'),
        sa.CheckConstraint('size_bytes > 0', name='ck_signature_size'),
        sa.CheckConstraint('version >= 1', name='ck_signature_version'))
    op.create_index('ix_signature_target', 'signature_evidence', ['tenant_id','entity_type','entity_id'])
    op.create_index('ix_signature_signed_at', 'signature_evidence', ['signed_at'])
    op.execute("""
      CREATE FUNCTION public.fsos_reject_signature_mutation() RETURNS trigger
      LANGUAGE plpgsql AS $$ BEGIN
        RAISE EXCEPTION 'signature evidence is immutable' USING ERRCODE='55000';
      END $$
    """)
    op.execute("""CREATE TRIGGER signature_evidence_immutable BEFORE UPDATE OR DELETE
      ON public.signature_evidence FOR EACH ROW EXECUTE FUNCTION public.fsos_reject_signature_mutation()""")
    op.execute("""
      INSERT INTO permission (permission_id, tenant_id, permission_code, description, created_at, updated_at, version)
      SELECT gen_random_uuid(), t.tenant_id, p.code, p.description, now(), now(), 1
      FROM tenant t CROSS JOIN (VALUES
        ('SchoolReceiving.Sign','Capture receiving signature evidence'),
        ('Complaint.Sign','Capture complaint signature evidence'),
        ('Signature.Verify','Read and verify signature evidence')) p(code, description)
      WHERE t.deleted_at IS NULL ON CONFLICT (tenant_id, permission_code) DO NOTHING
    """)
    op.execute("""
      INSERT INTO role_permission (role_permission_id, tenant_id, role_id, permission_id, created_at, updated_at, version)
      SELECT gen_random_uuid(), r.tenant_id, r.role_id, p.permission_id, now(), now(), 1
      FROM role r JOIN permission p ON p.tenant_id=r.tenant_id
      WHERE r.deleted_at IS NULL AND p.deleted_at IS NULL
        AND r.role_code IN ('FRONTEND_ADMIN','TENANT_ADMIN','DEV_MAINTENANCE')
        AND p.permission_code IN ('SchoolReceiving.Sign','Complaint.Sign','Signature.Verify')
      ON CONFLICT (tenant_id, role_id, permission_id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute('DROP TRIGGER signature_evidence_immutable ON public.signature_evidence')
    op.execute('DROP FUNCTION public.fsos_reject_signature_mutation()')
    op.drop_index('ix_signature_signed_at', table_name='signature_evidence')
    op.drop_index('ix_signature_target', table_name='signature_evidence')
    op.drop_table('signature_evidence')
