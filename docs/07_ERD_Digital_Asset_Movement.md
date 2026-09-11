# Food Safety Operating System (FSOS)

# 07_ERD_Digital_Asset_Movement.md

Version : 1.0

Document Type :
Digital Asset Movement Database Design

Database :
PostgreSQL 18

Status :
Draft

---

# 1. Purpose

Dokumen ini menjelaskan seluruh transaksi
Food Safety Operating System.

Seluruh transaksi dipandang sebagai

Digital Asset Movement.

Yang berpindah bukan hanya barang.

Tetapi identitas digitalnya.

---

# 2. Design Philosophy

Master Data

tidak pernah berubah.

Yang berubah adalah

Digital Asset.

Misalnya

Raw Material

↓

Raw Material Batch

↓

Production Batch

↓

Package

↓

Vehicle

↓

School

↓

Consumption

---

# 3. Digital Asset Hierarchy

Master Raw Material

↓

Raw Material Batch

↓

Production Batch

↓

Package

↓

Delivery

↓

School

↓

Complaint

↓

Recall

---

# 4. Raw Material Batch

Setiap penerimaan bahan

menghasilkan

Batch.

Field

raw_material_batch_id

batch_code

supplier_id

receiving_id

expired_date

status

qr_code

---

# 5. Receiving

Receiving

hanya

header.

receiving_id

supplier_id

received_at

operator

status

---

# 6. Receiving Item

receiving_item

berisi

Raw Material Batch.

receiving_item_id

receiving_id

raw_material_batch_id

quantity

temperature

accepted

---

# 7. Asset Movement

Inilah tabel

terpenting.

asset_movement

movement_id

asset_type

asset_uuid

movement_type

from_location

to_location

operator

movement_time

remarks

---

# 8. Movement Type

Receiving

Storage

Issue

Production

Packaging

Vehicle Loading

Delivery

School Receiving

Consumed

Complaint

Recall

Discard

---

# 9. Production Batch

Production Batch

dibentuk

dari

Raw Material Batch.

production_batch_id

batch_code

kitchen

menu

started_at

finished_at

holding_started_at

holding_expired_at

status

---

# 10. Production Item

Menghubungkan

Production Batch

dengan

Raw Material Batch.

production_item_id

production_batch_id

raw_material_batch_id

quantity

---

# 11. Package

Setiap Production Batch

menghasilkan

Package.

package_id

package_code

production_batch_id

package_number

remaining_minutes

expired_at

status

---

# 12. Package Movement

Package

bergerak.

Package

↓

Vehicle

↓

School

↓

Consumption

Semuanya dicatat.

---

# 13. Delivery

delivery_id

vehicle

driver

departure_time

arrival_time

status

---

# 14. Delivery Item

delivery_item

menghubungkan

Delivery

dengan

Package.

delivery_item_id

delivery_id

package_id

---

# 15. School Receiving

school_receiving

school

package

received_time

temperature

accepted

photo

---

# 16. Consumption

package

↓

Consumed

↓

Time

↓

Remaining

↓

Safe

---

# 17. Complaint

Complaint

selalu

mengacu

Package.

complaint_id

package_id

school_id

description

reported_at

---

# 18. Recall

Recall

mengacu

Production Batch.

recall_id

production_batch_id

reason

started_at

completed_at

---

# 19. Traceability

Forward

Raw Material

↓

Production

↓

Package

↓

Vehicle

↓

School

↓

Complaint

Backward

Complaint

↓

Package

↓

Production

↓

Raw Material

---

# 20. QR Code

QR

tidak dibuat

untuk

Master.

Tetapi

Digital Asset.

Raw Material Batch

Production Batch

Package

Vehicle

Device

---

# 21. Digital Passport

Setiap Asset

mempunyai

Digital Passport.

Misalnya

Package

↓

UUID

QR

History

Temperature

Movement

Holding

Complaint

Recall

---

# 22. Remaining Time

Remaining Time

tidak dihitung

setiap query.

Tetapi

diupdate

setiap Event.

---

# 23. Holding Time

Holding Time

mengikuti

Package.

Bukan

Production.

Karena

setiap Package

bisa

berbeda

status.

---

# 24. Asset Status

Created

Stored

Issued

Cooking

Packaging

Loaded

Delivered

Received

Consumed

Complaint

Recall

Discard

---

# 25. Audit

Seluruh Movement

tidak pernah

dihapus.

---

# 26. Deliverables

FSOS

mampu

melakukan

Forward Traceability

Backward Traceability

Movement Tracking

Food Recall

Remaining Time

Holding Time

---

# 27. Next Document

08_ERD_Telemetry.md

Membahas

Temperature

Humidity

GPS

Heartbeat

Device Health

Alarm

Event Log