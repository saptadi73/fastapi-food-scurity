import json
from datetime import datetime

from sqlalchemy import func, select

from app.core.database.scope import ActorScope
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.telemetry.infrastructure.orm import MQTTMessageLog


class MQTTEventService:
    def __init__(self, session, scope: ActorScope):
        self.session = session
        self.scope = scope

    @staticmethod
    def payload_view(payload: bytes) -> tuple[object | None, str | None]:
        try:
            text = payload.decode('utf-8')
        except UnicodeDecodeError:
            return None, None
        try:
            return json.loads(text), None
        except json.JSONDecodeError:
            return None, text[:4096]

    async def list_events(self, *, topic: str | None = None, processed: bool | None = None,
                          since: datetime | None = None, until: datetime | None = None,
                          offset: int = 0, limit: int = 20):
        await require_permission(self.session, self.scope, 'Device.Read')
        query = select(MQTTMessageLog.__table__).where(
            MQTTMessageLog.tenant_id == self.scope.tenant_id,
            MQTTMessageLog.deleted_at.is_(None),
        )
        if topic is not None:
            query = query.where(MQTTMessageLog.topic == topic)
        if processed is not None:
            query = query.where(MQTTMessageLog.processed == processed)
        if since is not None:
            query = query.where(MQTTMessageLog.received_at >= since)
        if until is not None:
            query = query.where(MQTTMessageLog.received_at < until)
        rows = (await self.session.execute(
            query.order_by(MQTTMessageLog.received_at.desc(), MQTTMessageLog.message_uuid.desc())
            .offset(offset).limit(limit + 1)
        )).mappings().all()
        items = []
        for row in rows[:limit]:
            payload_json, payload_text = self.payload_view(row['payload'])
            items.append({
                'message_uuid': row['message_uuid'],
                'tenant_id': row['tenant_id'],
                'topic': row['topic'],
                'qos': row['qos'],
                'received_at': row['received_at'],
                'processed': row['processed'],
                'payload_json': payload_json,
                'payload_text': payload_text,
            })
        return {'items': items, 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if len(rows) > limit else None}

    async def list_topics(self, *, topic_prefix: str | None = None,
                          offset: int = 0, limit: int = 20):
        await require_permission(self.session, self.scope, 'Device.Read')
        query = select(
            MQTTMessageLog.topic,
            func.count(MQTTMessageLog.message_uuid).label('event_count'),
            func.max(MQTTMessageLog.received_at).label('latest_received_at'),
        ).where(
            MQTTMessageLog.tenant_id == self.scope.tenant_id,
            MQTTMessageLog.deleted_at.is_(None),
        ).group_by(MQTTMessageLog.topic)
        if topic_prefix is not None:
            query = query.where(MQTTMessageLog.topic.startswith(topic_prefix))
        rows = (await self.session.execute(
            query.order_by(func.max(MQTTMessageLog.received_at).desc(), MQTTMessageLog.topic.asc())
            .offset(offset).limit(limit + 1)
        )).mappings().all()
        return {'items': [dict(row) for row in rows[:limit]], 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if len(rows) > limit else None}
