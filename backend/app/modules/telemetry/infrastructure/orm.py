from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.mixins import AuditMixin
from app.core.database.session import Base


class MQTTMessageLog(AuditMixin, Base):
    __tablename__ = "mqtt_message_log"
    __table_args__ = (
        UniqueConstraint("tenant_id", "message_uuid", name="uq_mqtt_message_tenant_uuid"),
        CheckConstraint("qos BETWEEN 0 AND 2", name="ck_mqtt_message_qos"),
        CheckConstraint("length(trim(topic)) > 0", name="ck_mqtt_message_topic"),
        CheckConstraint("deleted_at IS NULL AND deleted_by IS NULL", name="ck_mqtt_message_not_deleted"),
        CheckConstraint("version >= 1", name="ck_mqtt_message_version"),
        Index("ix_mqtt_message_tenant_received", "tenant_id", "received_at"),
    )
    message_uuid: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"))
    topic: Mapped[str] = mapped_column(String(65535))
    qos: Mapped[int]
    payload: Mapped[bytes] = mapped_column(LargeBinary)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed: Mapped[bool] = mapped_column(default=False, server_default="false")


class FoodSensorBinding(AuditMixin, Base):
    __tablename__ = "food_sensor_binding"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "device_uuid"], ["device.tenant_id", "device.device_uuid"],
                             name="fk_food_sensor_binding_device", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "production_batch_id"],
                             ["production_batch.tenant_id", "production_batch.production_batch_id"],
                             name="fk_food_sensor_binding_production", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "package_id"], ["package.tenant_id", "package.package_id"],
                             name="fk_food_sensor_binding_package", ondelete="RESTRICT"),
        CheckConstraint("phase IN ('PRODUCTION', 'HOLDING')", name="ck_food_sensor_binding_phase"),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="ck_food_sensor_binding_time"),
        CheckConstraint("version >= 1", name="ck_food_sensor_binding_version"),
        Index("ix_food_sensor_binding_tenant_package", "tenant_id", "package_id", "started_at"),
        Index("ix_food_sensor_binding_tenant_production", "tenant_id", "production_batch_id", "started_at"),
    )
    binding_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    device_uuid: Mapped[UUID]
    production_batch_id: Mapped[UUID]
    package_id: Mapped[UUID | None]
    phase: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1, server_default="1")


class SensorAudit(AuditMixin):
    tenant_id: Mapped[UUID]
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    mqtt_message_id: Mapped[UUID | None]


def sensor_constraints(table, device=True):
    constraints = [
        ForeignKeyConstraint(["tenant_id", "mqtt_message_id"],
                             ["mqtt_message_log.tenant_id", "mqtt_message_log.message_uuid"],
                             name=f"fk_{table}_mqtt", ondelete="RESTRICT"),
        CheckConstraint("deleted_at IS NULL AND deleted_by IS NULL", name=f"ck_{table}_not_deleted"),
        CheckConstraint("version >= 1", name=f"ck_{table}_version"),
        Index(f"ix_{table}_recorded", "recorded_at"),
        Index(f"ix_{table}_mqtt", "tenant_id", "mqtt_message_id"),
    ]
    if device:
        constraints.extend([
            ForeignKeyConstraint(["tenant_id", "device_uuid"], ["device.tenant_id", "device.device_uuid"],
                                 name=f"fk_{table}_device", ondelete="RESTRICT"),
            Index(f"ix_{table}_device_time", "tenant_id", "device_uuid", "recorded_at"),
        ])
    return constraints


class TemperatureLog(SensorAudit, Base):
    __tablename__ = "temperature_log"
    __table_args__ = (
        *sensor_constraints("temperature"),
        ForeignKeyConstraint(["tenant_id", "storage_uuid"], ["storage.tenant_id", "storage.storage_id"],
                             name="fk_temperature_storage", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "package_uuid"], ["package.tenant_id", "package.package_id"],
                             name="fk_temperature_package", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "production_batch_uuid"],
                             ["production_batch.tenant_id", "production_batch.production_batch_id"],
                             name="fk_temperature_production", ondelete="RESTRICT"),
        CheckConstraint("temperature <> 'NaN'::numeric", name="ck_temperature_finite"),
        CheckConstraint("unit IN ('C', 'F', 'K')", name="ck_temperature_unit"),
        Index("ix_temperature_storage_time", "tenant_id", "storage_uuid", "recorded_at"),
        Index("ix_temperature_package_time", "tenant_id", "package_uuid", "recorded_at"),
        Index("ix_temperature_production_time", "tenant_id", "production_batch_uuid", "recorded_at"),
        {"postgresql_partition_by": "RANGE (recorded_at)"},
    )
    temperature_log_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    device_uuid: Mapped[UUID]
    storage_uuid: Mapped[UUID | None]
    package_uuid: Mapped[UUID | None]
    production_batch_uuid: Mapped[UUID | None]
    temperature: Mapped[Decimal] = mapped_column(Numeric(8, 3))
    unit: Mapped[str] = mapped_column(String(1))


class HumidityLog(SensorAudit, Base):
    __tablename__ = "humidity_log"
    __table_args__ = (
        *sensor_constraints("humidity"),
        CheckConstraint("humidity BETWEEN 0 AND 100", name="ck_humidity_range"),
        {"postgresql_partition_by": "RANGE (recorded_at)"},
    )
    humidity_log_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    device_uuid: Mapped[UUID]
    humidity: Mapped[Decimal] = mapped_column(Numeric(6, 3))


class GPSLog(SensorAudit, Base):
    __tablename__ = "gps_log"
    __table_args__ = (
        *sensor_constraints("gps", device=False),
        ForeignKeyConstraint(["tenant_id", "vehicle_uuid"], ["vehicle.tenant_id", "vehicle.vehicle_id"],
                             name="fk_gps_vehicle", ondelete="RESTRICT"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_gps_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_gps_longitude"),
        CheckConstraint("speed >= 0 AND speed <> 'NaN'::numeric", name="ck_gps_speed"),
        CheckConstraint("heading >= 0 AND heading < 360", name="ck_gps_heading"),
        CheckConstraint("hdop >= 0 AND hdop <> 'NaN'::numeric", name="ck_gps_hdop"),
        CheckConstraint("altitude <> 'NaN'::numeric", name="ck_gps_altitude"),
        CheckConstraint("satellite >= 0", name="ck_gps_satellite"),
        Index("ix_gps_vehicle_time", "tenant_id", "vehicle_uuid", "recorded_at"),
        Index("ix_gps_location", "location", postgresql_using="gist"),
        {"postgresql_partition_by": "RANGE (recorded_at)"},
    )
    gps_log_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    vehicle_uuid: Mapped[UUID]
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    speed: Mapped[Decimal | None] = mapped_column(Numeric(9, 3))
    heading: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    altitude: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    hdop: Mapped[Decimal | None] = mapped_column(Numeric(9, 3))
    satellite: Mapped[int | None]
    location: Mapped[WKBElement] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False),
        Computed("ST_SetSRID(ST_MakePoint(longitude::double precision, latitude::double precision),4326)", persisted=True),
    )


class HeartbeatLog(SensorAudit, Base):
    __tablename__ = "heartbeat_log"
    __table_args__ = (
        *sensor_constraints("heartbeat"),
        CheckConstraint("uptime >= 0", name="ck_heartbeat_uptime"),
        CheckConstraint("heap >= 0", name="ck_heartbeat_heap"),
        CheckConstraint("battery BETWEEN 0 AND 100", name="ck_heartbeat_battery"),
        {"postgresql_partition_by": "RANGE (recorded_at)"},
    )
    heartbeat_log_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    device_uuid: Mapped[UUID]
    uptime: Mapped[int] = mapped_column(BigInteger)
    heap: Mapped[int | None] = mapped_column(BigInteger)
    firmware: Mapped[str | None] = mapped_column(String(100))
    hardware: Mapped[str | None] = mapped_column(String(100))
    wifi_signal: Mapped[int | None]
    battery: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))


class TelemetryAudit(AuditMixin):
    tenant_id: Mapped[UUID]
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mqtt_message_id: Mapped[UUID | None]


class DeviceHealthLog(TelemetryAudit, Base):
    __tablename__ = "device_health_log"
    __table_args__ = (
        *sensor_constraints("device_health"),
        CheckConstraint("length(trim(health)) > 0", name="ck_device_health_status"),
    )
    device_health_log_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    device_uuid: Mapped[UUID]
    health: Mapped[str] = mapped_column(String(50))
    sensor: Mapped[str | None] = mapped_column(String(50))
    wifi: Mapped[str | None] = mapped_column(String(50))
    mqtt: Mapped[str | None] = mapped_column(String(50))
    gps: Mapped[str | None] = mapped_column(String(50))
    battery: Mapped[str | None] = mapped_column(String(50))


class AlarmLog(TelemetryAudit, Base):
    __tablename__ = "alarm_log"
    __table_args__ = (
        *sensor_constraints("alarm"),
        UniqueConstraint("tenant_id", "alarm_id", name="uq_alarm_tenant_id"),
        CheckConstraint("length(trim(alarm_code)) > 0", name="ck_alarm_code"),
        CheckConstraint("length(trim(severity)) > 0", name="ck_alarm_severity"),
    )
    alarm_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    device_uuid: Mapped[UUID]
    alarm_code: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(String(2000))
    acknowledged: Mapped[bool] = mapped_column(default=False, server_default="false")


class HoldingLog(TelemetryAudit, Base):
    __tablename__ = "holding_log"
    __table_args__ = (
        *sensor_constraints("holding", device=False),
        ForeignKeyConstraint(["tenant_id", "package_uuid"], ["package.tenant_id", "package.package_id"],
                             name="fk_holding_package", ondelete="RESTRICT"),
        CheckConstraint("elapsed_minutes >= 0", name="ck_holding_elapsed"),
        CheckConstraint("length(trim(status)) > 0", name="ck_holding_status"),
        CheckConstraint("length(trim(warning_level)) > 0", name="ck_holding_warning"),
        Index("ix_holding_package_time", "tenant_id", "package_uuid", "recorded_at"),
    )
    holding_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    package_uuid: Mapped[UUID]
    status: Mapped[str] = mapped_column(String(50))
    elapsed_minutes: Mapped[int]
    remaining_minutes: Mapped[int]
    warning_level: Mapped[str] = mapped_column(String(50))


class SignalLog(TelemetryAudit, Base):
    __tablename__ = "signal_log"
    __table_args__ = (
        *sensor_constraints("signal"),
        CheckConstraint("quality BETWEEN 0 AND 100", name="ck_signal_quality"),
        CheckConstraint("wifi_signal IS NOT NULL OR rssi IS NOT NULL OR quality IS NOT NULL", name="ck_signal_measurement"),
    )
    signal_log_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    device_uuid: Mapped[UUID]
    wifi_signal: Mapped[int | None]
    rssi: Mapped[int | None]
    quality: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))


class BatteryLog(TelemetryAudit, Base):
    __tablename__ = "battery_log"
    __table_args__ = (
        *sensor_constraints("battery"),
        CheckConstraint("battery BETWEEN 0 AND 100", name="ck_battery_level"),
        CheckConstraint("percentage BETWEEN 0 AND 100", name="ck_battery_percentage"),
        CheckConstraint("voltage >= 0 AND voltage <> 'NaN'::numeric", name="ck_battery_voltage"),
        CheckConstraint("battery IS NOT NULL OR voltage IS NOT NULL OR percentage IS NOT NULL OR charging IS NOT NULL",
                        name="ck_battery_measurement"),
    )
    battery_log_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    device_uuid: Mapped[UUID]
    battery: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    voltage: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    charging: Mapped[bool | None]


class DeviceSession(TelemetryAudit, Base):
    __tablename__ = "device_session"
    __table_args__ = (
        *sensor_constraints("device_session"),
        UniqueConstraint("tenant_id", "session_id", name="uq_device_session_tenant_id"),
        CheckConstraint("disconnected_at >= connected_at", name="ck_device_session_time"),
        Index("ix_device_session_connected", "tenant_id", "device_uuid", "connected_at"),
    )
    session_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    device_uuid: Mapped[UUID]
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(INET)
    firmware: Mapped[str | None] = mapped_column(String(100))


class AlarmAcknowledgment(TelemetryAudit, Base):
    __tablename__ = "alarm_acknowledgment"
    __table_args__ = (
        *sensor_constraints("alarm_ack", device=False),
        UniqueConstraint("tenant_id", "alarm_id", name="uq_alarm_ack_once"),
        ForeignKeyConstraint(["tenant_id", "alarm_id"], ["alarm_log.tenant_id", "alarm_log.alarm_id"],
                             name="fk_alarm_ack_alarm", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "acknowledged_by"], ["app_user.tenant_id", "app_user.user_id"],
                             name="fk_alarm_ack_actor", ondelete="RESTRICT"),
    )
    acknowledgment_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    alarm_id: Mapped[UUID]
    acknowledged_by: Mapped[UUID]
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DeviceSessionEnd(TelemetryAudit, Base):
    __tablename__ = "device_session_end"
    __table_args__ = (
        *sensor_constraints("session_end", device=False),
        UniqueConstraint("tenant_id", "session_id", name="uq_session_end_once"),
        ForeignKeyConstraint(["tenant_id", "session_id"], ["device_session.tenant_id", "device_session.session_id"],
                             name="fk_session_end_session", ondelete="RESTRICT"),
    )
    session_end_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID]
    disconnected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
