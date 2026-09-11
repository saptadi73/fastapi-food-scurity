# Food Safety Operating System (FSOS)

# 12_Digital_Twin_Registry.md

Version : 1.0

Status :
Draft

Document Type :
Digital Twin Architecture

Platform :
FastAPI

---

# 1. Purpose

Digital Twin Registry merupakan pusat identitas
seluruh objek digital pada FSOS.

Setiap objek fisik mempunyai
representasi digital.

FSOS tidak mengenal perangkat secara langsung.

FSOS mengenal Digital Twin.

---

# 2. Philosophy

Physical World

↓

Digital Twin

↓

Event

↓

Decision

↓

Dashboard

↓

Analytics

Semua keputusan dibuat
berdasarkan Digital Twin.

---

# 3. Managed Objects

Digital Twin dibuat untuk

Device

Kitchen

Storage

Vehicle

Package

Production Batch

Raw Material Batch

School

---

# 4. Digital Twin Identity

Seluruh Digital Twin memiliki

UUID

Code

Name

Status

Lifecycle

Owner

Location

Created Date

---

# 5. Device Twin

Field

device_uuid

device_code

device_name

device_type

serial_number

firmware_version

hardware_revision

mqtt_client_id

mqtt_topic

status

health

battery

wifi_signal

last_seen

---

# 6. Kitchen Twin

Kitchen UUID

Kitchen Code

Kitchen Name

Latitude

Longitude

Capacity

Status

Food Safety Score

---

# 7. Storage Twin

Storage UUID

Storage Type

Temperature Range

Humidity Range

Current Status

Alarm Status

Current Temperature

Current Humidity

---

# 8. Vehicle Twin

Vehicle UUID

GPS Device

Current Latitude

Current Longitude

Driver

Current Delivery

Status

ETA

Health

---

# 9. Package Twin

Package UUID

QR Code

Production Batch

Current Location

Vehicle

School

Holding Time

Remaining Time

Food Safety Status

---

# 10. Batch Twin

Batch UUID

Recipe

Operator

Kitchen

Start Time

Finish Time

Holding Start

Holding End

Status

---

# 11. Raw Material Twin

Batch UUID

Supplier

Receiving

Storage

Temperature History

Inspection

Current Status

---

# 12. Device Lifecycle

Manufactured

↓

Registered

↓

Provisioned

↓

Installed

↓

Activated

↓

Running

↓

Maintenance

↓

Retired

---

# 13. Package Lifecycle

Created

↓

Packed

↓

Stored

↓

Loaded

↓

Delivered

↓

Accepted

↓

Served

↓

Consumed

↓

Archived

---

# 14. Vehicle Lifecycle

Registered

↓

Assigned

↓

Ready

↓

Delivering

↓

Idle

↓

Maintenance

↓

Retired

---

# 15. Device Health

Healthy

Warning

Critical

Offline

Maintenance

---

# 16. Calibration

Calibration Date

Calibration Due

Calibration Status

Calibration Certificate

---

# 17. Firmware

Current Version

Target Version

OTA Available

OTA Status

---

# 18. Heartbeat

Every 30 Seconds

Update

Last Seen

Uptime

Memory

CPU

Signal

---

# 19. Ownership

Tenant

Kitchen

Operator

Department

Asset Number

---

# 20. Location

Latitude

Longitude

Geo Point

PostGIS

---

# 21. QR Code

Semua Digital Twin

mempunyai

QR Code.

Device

Vehicle

Package

Storage

Kitchen

Batch

---

# 22. Telemetry

Digital Twin

mengambil data dari

Temperature

Humidity

GPS

Battery

Signal

Holding

---

# 23. Event

Digital Twin

menghasilkan

DeviceRegistered

DeviceOnline

TemperatureChanged

HoldingStarted

HoldingExpired

PackageDelivered

RecallStarted

---

# 24. Dashboard

Dashboard

tidak membaca

Temperature Log.

Dashboard membaca

Digital Twin.

Sehingga

Current Status

langsung tersedia.

---

# 25. AI

AI membaca

Digital Twin

dan

Historical Event.

---

# 26. Deliverables

Seluruh objek penting
memiliki identitas digital.

---

# 27. Next Document

13_Traceability_Engine.md