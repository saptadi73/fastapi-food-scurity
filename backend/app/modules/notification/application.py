from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import insert, select, update

from app.core.database.scope import VersionConflictError
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.notification.infrastructure.orm import NotificationOutbox
from app.modules.receiving.application.service import ReceivingService


class NotificationConflictError(Exception):
    pass


async def enqueue_notification(session, scope, *, event_type: str, entity_type: str, entity_uuid: UUID,
                               subject: str, message: str, channel: str = 'DASHBOARD',
                               recipient: str | None = None) -> UUID:
    notification_id = uuid4()
    now = datetime.now(UTC)
    await session.execute(insert(NotificationOutbox).values(
        notification_id=notification_id,
        tenant_id=scope.tenant_id,
        entity_type=entity_type,
        entity_uuid=entity_uuid,
        event_type=event_type,
        channel=channel,
        recipient=recipient,
        subject=subject,
        message=message,
        status='PENDING',
        scheduled_at=now,
        sent_at=None,
        failure_reason=None,
        created_by=scope.actor_id,
        updated_by=scope.actor_id,
    ))
    return notification_id


class NotificationService(ReceivingService):
    async def list(self, *, offset=0, limit=20, status=None, channel=None, entity_type=None, entity_uuid=None):
        await require_permission(self.db, self.scope, 'Notification.Read')
        query = select(NotificationOutbox.__table__).where(*self.visible(NotificationOutbox))
        if status is not None:
            query = query.where(NotificationOutbox.status == status)
        if channel is not None:
            query = query.where(NotificationOutbox.channel == channel)
        if entity_type is not None:
            query = query.where(NotificationOutbox.entity_type == entity_type)
        if entity_uuid is not None:
            query = query.where(NotificationOutbox.entity_uuid == entity_uuid)
        rows = (await self.db.execute(query.order_by(
            NotificationOutbox.created_at.desc(),
            NotificationOutbox.notification_id.desc(),
        ).offset(offset).limit(limit + 1))).mappings().all()
        return {'items': [dict(row) for row in rows[:limit]], 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if len(rows) > limit else None}

    async def mark_sent(self, identifier, payload):
        await require_permission(self.db, self.scope, 'Notification.Dispatch')
        current = await self.row(NotificationOutbox, 'notification_id', identifier, lock=True)
        if current['version'] != payload.expected_version:
            raise VersionConflictError()
        if current['status'] == 'SENT':
            raise NotificationConflictError('Notification already sent')
        if current['status'] == 'CANCELLED':
            raise NotificationConflictError('Cancelled notification cannot be sent')
        sent_at = payload.sent_at or datetime.now(UTC)
        if sent_at < current['scheduled_at']:
            raise NotificationConflictError('sent_at must not be before scheduled_at')
        await self.db.execute(update(NotificationOutbox).where(
            *self.visible(NotificationOutbox),
            NotificationOutbox.notification_id == identifier,
        ).values(
            status='SENT',
            sent_at=sent_at,
            failure_reason=None,
            updated_at=datetime.now(UTC),
            updated_by=self.scope.actor_id,
            version=NotificationOutbox.version + 1,
        ))
        return await self.row(NotificationOutbox, 'notification_id', identifier)

    async def mark_failed(self, identifier, payload):
        await require_permission(self.db, self.scope, 'Notification.Dispatch')
        current = await self.row(NotificationOutbox, 'notification_id', identifier, lock=True)
        if current['version'] != payload.expected_version:
            raise VersionConflictError()
        if current['status'] == 'SENT':
            raise NotificationConflictError('Sent notification cannot be failed')
        if current['status'] == 'CANCELLED':
            raise NotificationConflictError('Cancelled notification cannot be failed')
        await self.db.execute(update(NotificationOutbox).where(
            *self.visible(NotificationOutbox),
            NotificationOutbox.notification_id == identifier,
        ).values(
            status='FAILED',
            failure_reason=payload.failure_reason,
            updated_at=datetime.now(UTC),
            updated_by=self.scope.actor_id,
            version=NotificationOutbox.version + 1,
        ))
        return await self.row(NotificationOutbox, 'notification_id', identifier)
