from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.mixins import AuditMixin
from app.core.database.session import Base


class User(AuditMixin, Base):
    __tablename__ = "app_user"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_user_tenant_id"),
        CheckConstraint("length(trim(username)) > 0", name="ck_user_username"),
        CheckConstraint("length(trim(email)) > 0", name="ck_user_email"),
        CheckConstraint("version >= 1", name="ck_user_version"),
        Index("ix_user_created_at", "created_at"),
    )
    user_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"))
    username: Mapped[str] = mapped_column(String(100))
    fullname: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254))
    # Belum memiliki password saat provisioning; hashing dilakukan service autentikasi.
    password_hash: Mapped[str | None] = mapped_column(String(255), deferred=True)
    status: Mapped[str] = mapped_column(String(30), default="INACTIVE", server_default="INACTIVE")


Index("uq_user_tenant_username", User.tenant_id, func.lower(func.btrim(User.username)), unique=True)
Index("uq_user_tenant_email", User.tenant_id, func.lower(func.btrim(User.email)), unique=True)


class Role(AuditMixin, Base):
    __tablename__ = "role"
    __table_args__ = (
        UniqueConstraint("tenant_id", "role_id", name="uq_role_tenant_id"),
        UniqueConstraint("tenant_id", "role_code", name="uq_role_tenant_code"),
        CheckConstraint("length(trim(role_code)) > 0", name="ck_role_code"),
        CheckConstraint("version >= 1", name="ck_role_version"),
        Index("ix_role_created_at", "created_at"),
    )
    role_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"))
    role_code: Mapped[str] = mapped_column(String(50))
    role_name: Mapped[str] = mapped_column(String(100))


class Permission(AuditMixin, Base):
    __tablename__ = "permission"
    __table_args__ = (
        UniqueConstraint("tenant_id", "permission_id", name="uq_permission_tenant_id"),
        UniqueConstraint("tenant_id", "permission_code", name="uq_permission_tenant_code"),
        CheckConstraint("length(trim(permission_code)) > 0", name="ck_permission_code"),
        CheckConstraint("version >= 1", name="ck_permission_version"),
        Index("ix_permission_created_at", "created_at"),
    )
    permission_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"))
    permission_code: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500))


class UserRole(AuditMixin, Base):
    __tablename__ = "user_role"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "user_id"], ["app_user.tenant_id", "app_user.user_id"],
                             name="fk_user_role_user", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "role_id"], ["role.tenant_id", "role.role_id"],
                             name="fk_user_role_role", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "user_id", "role_id", name="uq_user_role_pair"),
        CheckConstraint("version >= 1", name="ck_user_role_version"),
        Index("ix_user_role_tenant_role", "tenant_id", "role_id"),
        Index("ix_user_role_created_at", "created_at"),
    )
    user_role_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    user_id: Mapped[UUID]
    role_id: Mapped[UUID]


class RolePermission(AuditMixin, Base):
    __tablename__ = "role_permission"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "role_id"], ["role.tenant_id", "role.role_id"],
                             name="fk_role_permission_role", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "permission_id"], ["permission.tenant_id", "permission.permission_id"],
                             name="fk_role_permission_permission", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "role_id", "permission_id", name="uq_role_permission_pair"),
        CheckConstraint("version >= 1", name="ck_role_permission_version"),
        Index("ix_role_permission_tenant_permission", "tenant_id", "permission_id"),
        Index("ix_role_permission_created_at", "created_at"),
    )
    role_permission_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    role_id: Mapped[UUID]
    permission_id: Mapped[UUID]
