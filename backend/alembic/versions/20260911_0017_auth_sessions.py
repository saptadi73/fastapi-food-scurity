"""Persist authentication sessions and hashed rotating refresh tokens."""
import sqlalchemy as sa

from alembic import op

revision = '20260911_0017'
down_revision = '20260911_0016'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('auth_session',
        sa.Column('session_id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint('session_id'),
        sa.ForeignKeyConstraint(['tenant_id', 'user_id'], ['app_user.tenant_id', 'app_user.user_id'], name='fk_auth_session_user', ondelete='RESTRICT'),
        sa.UniqueConstraint('tenant_id', 'session_id', name='uq_auth_session_tenant'),
        sa.CheckConstraint('expires_at > created_at', name='ck_auth_session_expiry'),
    )
    op.create_index('ix_auth_session_user', 'auth_session', ['tenant_id', 'user_id'])
    op.create_table('refresh_token',
        sa.Column('token_id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('session_id', sa.Uuid(), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint('token_id'),
        sa.ForeignKeyConstraint(['tenant_id', 'session_id'], ['auth_session.tenant_id', 'auth_session.session_id'], name='fk_refresh_session', ondelete='RESTRICT'),
        sa.UniqueConstraint('token_hash', name='uq_refresh_hash'),
        sa.CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name='ck_refresh_hash'),
    )
    op.create_index('ix_refresh_session', 'refresh_token', ['tenant_id', 'session_id'])


def downgrade():
    op.drop_table('refresh_token')
    op.drop_table('auth_session')
