from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.scope import ActorScope
from app.core.events.orm import EventLog
from app.modules.authentication.infrastructure.orm import Role, User, UserLocationAssignment, UserRole
from app.modules.authentication.infrastructure.passwords import hash_password_async
from app.modules.authentication.schemas.users import UserCreate, UserUpdate
from app.modules.master.infrastructure.orm import Kitchen, School


class UserConflictError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class UserAdministrationService:
    def __init__(self, db: AsyncSession, scope: ActorScope):
        self.db, self.scope = db, scope

    @property
    def audit(self):
        return {'tenant_id': self.scope.tenant_id, 'created_by': self.scope.actor_id,
                'updated_by': self.scope.actor_id}

    async def roles(self):
        rows = (await self.db.execute(select(Role.role_id, Role.role_code, Role.role_name).where(
            Role.tenant_id == self.scope.tenant_id, Role.deleted_at.is_(None)
        ).order_by(Role.role_name, Role.role_id))).mappings().all()
        return [dict(row) for row in rows]

    async def detail(self, user_id):
        user = (await self.db.execute(select(User.__table__).where(
            User.tenant_id == self.scope.tenant_id, User.user_id == user_id, User.deleted_at.is_(None)
        ))).mappings().one_or_none()
        if user is None:
            raise UserNotFoundError('User not found in tenant')
        roles = (await self.db.execute(select(Role.role_id, Role.role_code, Role.role_name).select_from(UserRole).join(
            Role, (Role.tenant_id == UserRole.tenant_id) & (Role.role_id == UserRole.role_id)
        ).where(UserRole.tenant_id == self.scope.tenant_id, UserRole.user_id == user_id,
                UserRole.deleted_at.is_(None), Role.deleted_at.is_(None)).order_by(Role.role_name))).mappings().all()
        assignments = (await self.db.execute(select(
            UserLocationAssignment.assignment_id, UserLocationAssignment.location_type,
            UserLocationAssignment.kitchen_id, UserLocationAssignment.school_id,
        ).where(UserLocationAssignment.tenant_id == self.scope.tenant_id,
                UserLocationAssignment.user_id == user_id,
                UserLocationAssignment.deleted_at.is_(None)).order_by(UserLocationAssignment.created_at)
        )).mappings().all()
        return {key: user[key] for key in ('user_id', 'username', 'fullname', 'email', 'job_title', 'status',
                                            'version', 'created_at')} | {
            'roles': [dict(row) for row in roles], 'location_assignments': [dict(row) for row in assignments]}

    async def list(self, offset: int, limit: int, status: str | None):
        where = [User.tenant_id == self.scope.tenant_id, User.deleted_at.is_(None)]
        if status:
            where.append(User.status == status)
        total = await self.db.scalar(select(func.count()).select_from(User).where(*where)) or 0
        ids = (await self.db.scalars(select(User.user_id).where(*where).order_by(
            User.created_at.desc(), User.user_id.desc()).offset(offset).limit(limit))).all()
        items = [await self.detail(identifier) for identifier in ids]
        return {'items': items, 'total': total, 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if offset + limit < total else None}

    async def create(self, payload: UserCreate):
        duplicate = await self.db.scalar(select(User.user_id).where(
            User.tenant_id == self.scope.tenant_id,
            (func.lower(User.username) == payload.username.strip().lower()) |
            (func.lower(User.email) == payload.email.lower()), User.deleted_at.is_(None)).limit(1))
        if duplicate:
            raise UserConflictError('Username or email already exists in tenant')
        roles = set((await self.db.scalars(select(Role.role_id).where(
            Role.tenant_id == self.scope.tenant_id, Role.role_id.in_(payload.role_ids),
            Role.deleted_at.is_(None)).with_for_update(read=True))).all())
        if roles != set(payload.role_ids):
            raise UserConflictError('Every role must exist in tenant')
        for assignment in payload.location_assignments:
            model, column, identifier = ((Kitchen, Kitchen.kitchen_id, assignment.kitchen_id)
                                         if assignment.location_type == 'KITCHEN'
                                         else (School, School.school_id, assignment.school_id))
            exists = await self.db.scalar(select(column).where(
                model.tenant_id == self.scope.tenant_id, column == identifier,
                model.status == 'ACTIVE', model.deleted_at.is_(None)).with_for_update(read=True))
            if exists is None:
                raise UserConflictError('Every assigned location must be active in tenant')
        user_id = uuid4()
        await self.db.execute(insert(User).values(user_id=user_id, username=payload.username.strip(),
            fullname=payload.fullname.strip(), email=payload.email.lower(),
            job_title=payload.job_title.strip() if payload.job_title else None,
            password_hash=await hash_password_async(payload.password.get_secret_value()), status='ACTIVE', **self.audit))
        for role_id in payload.role_ids:
            await self.db.execute(insert(UserRole).values(user_role_id=uuid4(), user_id=user_id,
                                                          role_id=role_id, **self.audit))
        for assignment in payload.location_assignments:
            await self.db.execute(insert(UserLocationAssignment).values(
                assignment_id=uuid4(), user_id=user_id, location_type=assignment.location_type,
                kitchen_id=assignment.kitchen_id, school_id=assignment.school_id, **self.audit))
        detail = await self.detail(user_id)
        await self.db.execute(insert(EventLog).values(event_uuid=uuid4(), event_type='user.registered',
            entity_type='USER', entity_uuid=user_id,
            payload={'schema_version': 1, 'actor_id': str(self.scope.actor_id), 'user_id': str(user_id),
                     'role_ids': [str(value) for value in payload.role_ids],
                     'location_assignment_ids': [str(item['assignment_id']) for item in detail['location_assignments']]},
            **self.audit))
        return detail

    async def update(self, user_id, payload: UserUpdate):
        target = (await self.db.execute(select(User.__table__).where(
            User.tenant_id == self.scope.tenant_id, User.user_id == user_id,
            User.deleted_at.is_(None)).with_for_update())).mappings().one_or_none()
        if target is None:
            raise UserNotFoundError('User not found in tenant')
        if target['version'] != payload.expected_version:
            raise UserConflictError('Stale user version')
        if user_id == self.scope.actor_id and payload.status != 'ACTIVE':
            raise UserConflictError('Current user cannot deactivate or lock itself')
        duplicate = await self.db.scalar(select(User.user_id).where(
            User.tenant_id == self.scope.tenant_id, User.user_id != user_id,
            func.lower(User.email) == payload.email.lower(), User.deleted_at.is_(None)).limit(1))
        if duplicate:
            raise UserConflictError('Email already exists in tenant')
        roles = set((await self.db.scalars(select(Role.role_id).where(
            Role.tenant_id == self.scope.tenant_id, Role.role_id.in_(payload.role_ids),
            Role.deleted_at.is_(None)).with_for_update(read=True))).all())
        if roles != set(payload.role_ids):
            raise UserConflictError('Every role must exist in tenant')
        for assignment in payload.location_assignments:
            model, column, identifier = ((Kitchen, Kitchen.kitchen_id, assignment.kitchen_id)
                                         if assignment.location_type == 'KITCHEN'
                                         else (School, School.school_id, assignment.school_id))
            exists = await self.db.scalar(select(column).where(
                model.tenant_id == self.scope.tenant_id, column == identifier,
                model.status == 'ACTIVE', model.deleted_at.is_(None)).with_for_update(read=True))
            if exists is None:
                raise UserConflictError('Every assigned location must be active in tenant')
        values = {'fullname': payload.fullname.strip(), 'email': payload.email.lower(),
                  'job_title': payload.job_title.strip() if payload.job_title else None,
                  'status': payload.status, 'updated_by': self.scope.actor_id,
                  'version': payload.expected_version + 1}
        if payload.password is not None:
            values['password_hash'] = await hash_password_async(payload.password.get_secret_value())
        result = await self.db.execute(update(User).where(
            User.tenant_id == self.scope.tenant_id, User.user_id == user_id,
            User.version == payload.expected_version, User.deleted_at.is_(None)).values(**values))
        if result.rowcount != 1:
            raise UserConflictError('Stale user version')
        now = datetime.now(timezone.utc)
        role_rows = (await self.db.execute(select(UserRole.__table__).where(
            UserRole.tenant_id == self.scope.tenant_id, UserRole.user_id == user_id).with_for_update())).mappings().all()
        role_by_id = {row['role_id']: row for row in role_rows}
        for role_id, row in role_by_id.items():
            active = role_id in roles
            await self.db.execute(update(UserRole).where(UserRole.user_role_id == row['user_role_id']).values(
                deleted_at=None if active else now, deleted_by=None if active else self.scope.actor_id,
                updated_by=self.scope.actor_id, version=row['version'] + 1))
        for role_id in roles - set(role_by_id):
            await self.db.execute(insert(UserRole).values(user_role_id=uuid4(), user_id=user_id,
                                                          role_id=role_id, **self.audit))
        assignment_rows = (await self.db.execute(select(UserLocationAssignment.__table__).where(
            UserLocationAssignment.tenant_id == self.scope.tenant_id,
            UserLocationAssignment.user_id == user_id).with_for_update())).mappings().all()
        assignment_by_target = {(row['location_type'], row['kitchen_id'] or row['school_id']): row
                                for row in assignment_rows}
        requested = {(item.location_type, item.kitchen_id or item.school_id): item
                     for item in payload.location_assignments}
        for target_key, row in assignment_by_target.items():
            active = target_key in requested
            await self.db.execute(update(UserLocationAssignment).where(
                UserLocationAssignment.assignment_id == row['assignment_id']).values(
                deleted_at=None if active else now, deleted_by=None if active else self.scope.actor_id,
                updated_by=self.scope.actor_id, version=row['version'] + 1))
        for target_key, item in requested.items():
            if target_key not in assignment_by_target:
                await self.db.execute(insert(UserLocationAssignment).values(
                    assignment_id=uuid4(), user_id=user_id, location_type=item.location_type,
                    kitchen_id=item.kitchen_id, school_id=item.school_id, **self.audit))
        detail = await self.detail(user_id)
        await self.db.execute(insert(EventLog).values(event_uuid=uuid4(), event_type='user.updated',
            entity_type='USER', entity_uuid=user_id,
            payload={'schema_version': 1, 'actor_id': str(self.scope.actor_id), 'user_id': str(user_id),
                     'status': payload.status, 'version': detail['version'],
                     'role_ids': [str(value) for value in payload.role_ids],
                     'location_assignment_ids': [str(item['assignment_id']) for item in detail['location_assignments']],
                     'password_changed': payload.password is not None}, **self.audit))
        return detail
