# Food Safety Operating System (FSOS)

# 04_Database_Architecture.md

Version : 1.0

Status :
Draft

Document Type :
Database Architecture Specification

Platform :
PostgreSQL 18
PostGIS
UUID

---

# 1. Purpose

Dokumen ini menjelaskan arsitektur database
Food Safety Operating System.

Database dirancang untuk mendukung

- IoT
- Food Traceability
- Holding Time
- Fleet Tracking
- Food Recall
- Dashboard
- AI Analytics

Menggunakan PostgreSQL 18.

---

# 2. Design Principles

Database menggunakan prinsip

✔ UUID

✔ Normalisasi

✔ Audit Trail

✔ Event Driven

✔ Soft Delete

✔ Time Series Ready

✔ GIS Ready

✔ Multi Kitchen Ready

---

# 3. Database Layers

Database dibagi menjadi
empat kelompok utama.

Master Data

↓

Operational Data

↓

Telemetry Data

↓

Analytics Data

---

# 4. Master Data

Master Data bersifat relatif tetap.

Tabel

device

vehicle

driver

storage

supplier

food_item

raw_material

kitchen

school

tenant

user

role

permission

---

# 5. Operational Data

Operational Data

berisi transaksi.

receiving

receiving_item

storage_transaction

production_batch

production_item

packaging_batch

delivery

delivery_item

school_receiving

food_complaint

food_recall

---

# 6. Telemetry Data

Data berasal dari IoT.

temperature_log

humidity_log

gps_log

heartbeat_log

device_health

alarm_log

event_log

---

# 7. Analytics Data

holding_summary

dashboard_cache

daily_statistics

food_safety_score

ai_recommendation

prediction_cache

---

# 8. UUID

Semua tabel menggunakan

UUID

Contoh

device_id

UUID

production_batch_id

UUID

storage_id

UUID

Tidak menggunakan integer.

---

# 9. Audit Columns

Seluruh tabel mempunyai

created_at

updated_at

deleted_at

created_by

updated_by

deleted_by

version

---

# 10. Soft Delete

Data

tidak pernah

dihapus permanen.

Menggunakan

deleted_at.

---

# 11. Device Table

Menyimpan identitas perangkat.

device_uuid

device_name

device_type

firmware

hardware

status

last_online

location

gps

---

# 12. Temperature Log

temperature_log

id

device_uuid

storage_uuid

temperature

recorded_at

signal

battery

---

# 13. GPS Log

gps_log

id

vehicle_uuid

latitude

longitude

speed

heading

satellite

hdop

recorded_at

---

# 14. Event Log

Seluruh event
disimpan.

temperature.updated

gps.updated

holding.started

holding.expired

alarm.created

recall.created

---

# 15. Storage Transaction

Semua perpindahan bahan.

Receiving

↓

Storage

↓

Kitchen

↓

Production

↓

Packaging

↓

Vehicle

↓

School

Tidak boleh ada perpindahan
yang tidak tercatat.

---

# 16. Production Batch

Setiap proses memasak.

batch_code

menu

kitchen

started_at

finished_at

expired_at

holding_limit

status

---

# 17. Packaging Batch

Satu batch produksi
dapat menghasilkan
banyak kemasan.

package_code

production_batch

package_number

expired_at

remaining_time

---

# 18. Delivery

delivery

vehicle

driver

departure_time

arrival_time

status

gps

---

# 19. School Receiving

school

batch

received_at

temperature

status

receiver

---

# 20. Complaint

complaint

school

package

description

reported_at

status

---

# 21. Recall

recall

batch

reason

started_at

completed_at

status

---

# 22. Food Traceability

Traceability dapat dilakukan
ke depan maupun ke belakang.

Raw Material

↓

Production

↓

Packaging

↓

Vehicle

↓

School

↓

Complaint

↓

Recall

---

# 23. Holding Time

Holding Time
tidak dihitung
dari dashboard.

Tetapi disimpan.

started_at

expired_at

remaining_time

status

warning_level

---

# 24. Fleet Tracking

GPS

disimpan
terpisah.

Tidak disimpan
di tabel delivery.

---

# 25. Time Series

temperature_log

gps_log

heartbeat_log

akan menjadi
time series table.

---

# 26. GIS

Semua

Kitchen

School

Storage

Vehicle

menggunakan

PostGIS.

---

# 27. Index

Index wajib

UUID

created_at

recorded_at

device_uuid

batch_code

package_code

---

# 28. Partition

temperature_log

gps_log

heartbeat_log

dipartisi

per bulan.

---

# 29. Database Rules

Tidak boleh
menyimpan
business rule.

Database
hanya menyimpan fakta.

---

# 30. Deliverables

Database siap mendukung

✔ IoT

✔ Dashboard

✔ Traceability

✔ Holding Time

✔ Recall

✔ AI

---

# 31. Next Document

05_Common_Framework.md