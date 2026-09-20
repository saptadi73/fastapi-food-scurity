"""MQTT broker consumer for FSOS gateway payloads."""

import asyncio
import json
import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

import aiomqtt
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config.settings import Settings
from app.modules.master.infrastructure.orm import (
    Device,
    DeviceBinding,
    Storage,
    StorageZone,
    Vehicle,
)
from app.modules.telemetry.infrastructure.orm import (
    FoodSensorBinding,
    GPSLog,
    MQTTMessageLog,
    TemperatureLog,
)

logger = logging.getLogger("fsos.mqtt")


class MQTTConsumer:
    def __init__(self, settings: Settings, session_factory: async_sessionmaker[AsyncSession]):
        self.settings = settings
        self.session_factory = session_factory
        self.stop_event = asyncio.Event()

    async def run(self) -> None:
        while not self.stop_event.is_set():
            try:
                await self._consume_connection()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("MQTT consumer disconnected; retrying")
                try:
                    await asyncio.wait_for(self.stop_event.wait(), timeout=5)
                except TimeoutError:
                    pass

    async def stop(self) -> None:
        self.stop_event.set()

    async def _consume_connection(self) -> None:
        password = self.settings.mqtt_password.get_secret_value() or None
        username = self.settings.mqtt_username or None
        async with aiomqtt.Client(
            hostname=self.settings.mqtt_host,
            port=self.settings.mqtt_port,
            username=username,
            password=password,
        ) as client:
            await client.subscribe("fsos/#", qos=1)
            logger.info("MQTT consumer subscribed", extra={"topic": "fsos/#"})
            async for message in client.messages:
                if self.stop_event.is_set():
                    return
                await self._handle_message(str(message.topic), bytes(message.payload), int(message.qos))

    async def _handle_message(self, topic: str, raw_payload: bytes, qos: int) -> None:
        received_at = datetime.now(UTC)
        message_uuid = uuid4()
        try:
            payload = json.loads(raw_payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            logger.warning("Ignoring non-JSON MQTT payload", extra={"topic": topic})
            return
        if not isinstance(payload, dict):
            return

        async with self.session_factory() as session:
            await session.execute(insert(MQTTMessageLog).values(
                message_uuid=message_uuid,
                tenant_id=self.settings.mqtt_tenant_id,
                topic=topic,
                qos=max(0, min(qos, 2)),
                payload=raw_payload,
                received_at=received_at,
                processed=False,
                created_by=None,
                updated_by=None,
            ))
            device = await self._resolve_device(session, topic, payload)
            if device is None:
                await session.commit()
                logger.warning("No MQTT device binding matched", extra={"topic": topic, "event": payload.get("event")})
                return
            handled = await self._write_telemetry(session, device, topic, payload, message_uuid, received_at)
            if handled:
                await session.execute(update(MQTTMessageLog).where(
                    MQTTMessageLog.message_uuid == message_uuid,
                    MQTTMessageLog.tenant_id == self.settings.mqtt_tenant_id,
                ).values(processed=True, updated_by=None))
            await session.commit()

    async def _resolve_device(self, session: AsyncSession, topic: str, payload: dict) -> dict | None:
        query = select(Device.__table__).where(
            Device.tenant_id == self.settings.mqtt_tenant_id,
            Device.mqtt_topic == topic,
            Device.deleted_at.is_(None),
            Device.status == "ACTIVE",
        )
        candidates = (await session.execute(query)).mappings().all()
        event = payload.get("event")
        sensor = payload.get("sensor")
        for device in candidates:
            if device["mqtt_event"] is not None and device["mqtt_event"] != event:
                continue
            if device["mqtt_sensor"] is not None and device["mqtt_sensor"] != sensor:
                continue
            return dict(device)
        return None

    async def _write_telemetry(
        self, session: AsyncSession, device: dict, topic: str, payload: dict,
        message_uuid: UUID, recorded_at: datetime,
    ) -> bool:
        if payload.get("valid") is False:
            return True
        device_type = str(device["device_type"]).upper()
        event = str(payload.get("event", "")).lower()
        if device_type == "GPS" or event == "gps" or topic.endswith("/gps"):
            return await self._write_gps(session, device, payload, message_uuid, recorded_at)
        temperature = payload.get("temperature_c")
        if temperature is None:
            return True
        try:
            value = Decimal(str(temperature))
        except (InvalidOperation, ValueError):
            return True
        binding = await session.scalar(select(FoodSensorBinding).where(
            FoodSensorBinding.tenant_id == self.settings.mqtt_tenant_id,
            FoodSensorBinding.device_uuid == device["device_uuid"],
            FoodSensorBinding.ended_at.is_(None),
            FoodSensorBinding.deleted_at.is_(None),
        ).order_by(FoodSensorBinding.phase.desc(), FoodSensorBinding.started_at.desc()))
        storage_id = await session.scalar(select(Storage.storage_id).join(
            StorageZone, StorageZone.storage_id == Storage.storage_id,
        ).where(
            Storage.tenant_id == self.settings.mqtt_tenant_id,
            StorageZone.tenant_id == self.settings.mqtt_tenant_id,
            StorageZone.zone_id == device["zone_id"],
            Storage.status == "ACTIVE",
            Storage.deleted_at.is_(None),
        ))
        await session.execute(insert(TemperatureLog).values(
            temperature_log_id=uuid4(), tenant_id=self.settings.mqtt_tenant_id,
            recorded_at=recorded_at, mqtt_message_id=message_uuid,
            device_uuid=device["device_uuid"], storage_uuid=storage_id,
            package_uuid=binding.package_id if binding and binding.phase == "HOLDING" else None,
            production_batch_uuid=binding.production_batch_id if binding else None,
            temperature=value, unit="C", created_by=None, updated_by=None,
        ))
        return True

    async def _write_gps(
        self, session: AsyncSession, device: dict, payload: dict,
        message_uuid: UUID, recorded_at: datetime,
    ) -> bool:
        try:
            latitude = Decimal(str(payload["latitude"]))
            longitude = Decimal(str(payload["longitude"]))
        except (KeyError, InvalidOperation, ValueError):
            return True
        vehicle = (await session.execute(select(Vehicle.vehicle_id).join(
            DeviceBinding, DeviceBinding.vehicle_id == Vehicle.vehicle_id,
        ).where(
            DeviceBinding.tenant_id == self.settings.mqtt_tenant_id,
            DeviceBinding.device_id == device["device_id"],
            DeviceBinding.deleted_at.is_(None),
            Vehicle.tenant_id == self.settings.mqtt_tenant_id,
            Vehicle.status == "ACTIVE",
            Vehicle.deleted_at.is_(None),
        ))).scalar_one_or_none()
        if vehicle is None:
            return True
        await session.execute(insert(GPSLog).values(
            gps_log_id=uuid4(), tenant_id=self.settings.mqtt_tenant_id,
            recorded_at=recorded_at, mqtt_message_id=message_uuid,
            vehicle_uuid=vehicle, latitude=latitude, longitude=longitude,
            speed=None, heading=None, altitude=None,
            hdop=payload.get("hdop"), satellite=payload.get("satellites"),
            created_by=None, updated_by=None,
        ))
        return True
