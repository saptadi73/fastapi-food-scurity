# Food Safety Operating System (FSOS)

# 08_ERD_Telemetry.md

Version : 1.0

Status :
Draft

Database :
PostgreSQL 18
PostGIS

Document Type :
Telemetry Database Design

---

# 1. Purpose

Dokumen ini menjelaskan desain database
untuk seluruh telemetry IoT.

Telemetry merupakan Digital Evidence.

Data telemetry

tidak boleh

diubah.

Tidak boleh

dihapus.

Seluruh telemetry menjadi
bukti digital.

---

# 2. Telemetry Architecture

ESP32

↓

MQTT

↓

MQTT Service

↓

Event Engine

↓

Telemetry Database

↓

Dashboard

↓

Analytics

---

# 3. Design Principles

Telemetry

✔ Immutable

✔ Time Series

✔ Event Driven

✔ UUID

✔ Audit

✔ High Performance

✔ Partition

---

# 4. Telemetry Modules

Temperature

Humidity

GPS

Heartbeat

Device Health

Alarm

Holding

Signal

Battery

---

# 5. temperature_log

temperature_log

temperature_log_id

device_uuid

storage_uuid

temperature

unit

recorded_at

mqtt_message_id

created_at

---

# 6. humidity_log

humidity_log

humidity_log_id

device_uuid

humidity

recorded_at

mqtt_message_id

---

# 7. gps_log

gps_log

gps_log_id

vehicle_uuid

latitude

longitude

speed

heading

altitude

hdop

satellite

recorded_at

---

# 8. heartbeat_log

heartbeat_log

heartbeat_log_id

device_uuid

uptime

heap

firmware

hardware

wifi_signal

battery

recorded_at

---

# 9. device_health_log

device_health_log

device_uuid

health

sensor

wifi

mqtt

gps

battery

recorded_at

---

# 10. alarm_log

alarm_log

alarm_id

device_uuid

alarm_code

severity

description

acknowledged

created_at

---

# 11. holding_log

holding_log

holding_id

package_uuid

status

elapsed_minutes

remaining_minutes

warning_level

recorded_at

---

# 12. signal_log

wifi_signal

rssi

quality

recorded_at

---

# 13. battery_log

battery

voltage

percentage

charging

recorded_at

---

# 14. event_log

event_log

event_uuid

event_type

entity_type

entity_uuid

payload

created_at

---

# 15. MQTT Message Log

mqtt_message_log

message_uuid

topic

qos

payload

received_at

processed

---

# 16. Device Session

device_session

device_uuid

connected_at

disconnected_at

ip_address

firmware

---

# 17. Time Series

Seluruh tabel

temperature

humidity

gps

heartbeat

dipartisi

per bulan.

---

# 18. GIS

GPS

menggunakan

PostGIS Point.

---

# 19. Digital Evidence

Telemetry

tidak boleh

UPDATE.

Tidak boleh

DELETE.

Append Only.

---

# 20. Event

temperature.updated

gps.updated

holding.updated

heartbeat.updated

alarm.created

device.connected

device.disconnected

---

# 21. Telemetry Flow

ESP32

↓

MQTT

↓

Parser

↓

Validator

↓

Telemetry DB

↓

Event

↓

Rule Engine

↓

Dashboard

---

# 22. Telemetry Retention

Temperature

1 tahun

GPS

1 tahun

Heartbeat

6 bulan

Alarm

5 tahun

Recall

Permanen

---

# 23. Index

device_uuid

recorded_at

storage_uuid

vehicle_uuid

package_uuid

---

# 24. Deliverables

Database mampu

✔ Live Dashboard

✔ AI Analytics

✔ Holding Time

✔ Fleet Tracking

✔ Digital Evidence

---

# 25. Next Document

09_Common_Framework.md