# Food Safety Operating System (FSOS)

# 05_Domain_Model.md

Version : 1.0

Status :
Draft

Document Type :
Domain Driven Design (DDD)

Platform :
FastAPI

---

# 1. Purpose

Dokumen ini menjelaskan Domain Model Food Safety Operating System.

Domain Model menjadi dasar seluruh implementasi backend.

Seluruh Entity

Database

REST API

Dashboard

AI

dibangun berdasarkan Domain ini.

---

# 2. Why Domain Model

Sebagian besar aplikasi FastAPI dibuat berdasarkan tabel database.

FSOS tidak.

FSOS dibangun berdasarkan Business Domain.

Domain

↓

Business Rule

↓

Database

↓

API

↓

Frontend

Bukan sebaliknya.

---

# 3. Bounded Context

FSOS dibagi menjadi beberapa Domain.

Authentication

↓

Master Data

↓

Device

↓

Telemetry

↓

Storage

↓

Receiving

↓

Production

↓

Holding Time

↓

Packaging

↓

Fleet Tracking

↓

School Receiving

↓

Complaint

↓

Recall

↓

Dashboard

↓

Notification

↓

Analytics

---

# 4. Authentication Domain

Bertanggung jawab terhadap

Login

JWT

Role

Permission

Refresh Token

Audit Login

---

# 5. Master Data Domain

Master

Kitchen

Storage

Supplier

Vehicle

Driver

School

Food Item

Raw Material

Menu

Tenant

User

Role

---

# 6. Device Domain

Mengelola

ESP32

Device

Firmware

Calibration

Heartbeat

Health

Configuration

Digital Twin

---

# 7. Telemetry Domain

Mengelola

Temperature

Humidity

GPS

Heartbeat

Battery

Signal

Alarm

Semua berasal dari IoT.

---

# 8. Storage Domain

Mengelola

Storage

Cold Storage

Dry Storage

Freezer

Storage Transaction

FIFO

FEFO

---

# 9. Receiving Domain

Mengelola

Penerimaan bahan makanan.

Receiving

Receiving Item

Inspection

QR Code

Batch

Supplier

Temperature

Photo

---

# 10. Production Domain

Mengelola

Kitchen Production.

Production Batch

Production Item

Recipe

Raw Material Usage

Started

Finished

Operator

---

# 11. Holding Time Domain

Mengelola

Holding Time.

Cooking Time

Packaging Time

Dispatch Time

Arrival Time

Remaining Time

Expired

Warning

Discard

---

# 12. Packaging Domain

Mengelola

Package

Package QR

Package Label

Package UUID

Package Status

---

# 13. Fleet Domain

Mengelola

Vehicle

GPS

Driver

Route

ETA

Live Tracking

Delivery

---

# 14. School Receiving Domain

Mengelola

School

Receiver

Receiving Temperature

Photo

Accepted

Rejected

---

# 15. Complaint Domain

Mengelola

Complaint

Food Incident

Food Poisoning

Investigation

CAPA

---

# 16. Recall Domain

Mengelola

Recall

Affected Batch

Affected Package

Affected School

Affected Vehicle

Recall Progress

---

# 17. Dashboard Domain

Mengelola

KPI

Statistics

Temperature

Holding Time

Fleet

Recall

Food Safety Score

---

# 18. Notification Domain

Mengelola

Email

WhatsApp

Telegram

Push Notification

Alarm

---

# 19. Analytics Domain

Mengelola

AI Recommendation

Prediction

Trend

Pattern

Risk Score

Decision Support

---

# 20. Aggregate Root

Setiap Domain mempunyai Aggregate.

Receiving

Production Batch

Package

Delivery

Complaint

Recall

Device

---

# 21. Entity

Contoh Entity

Device

Raw Material

Package

Vehicle

Production Batch

Storage

School

Complaint

---

# 22. Value Object

Coordinate

Temperature

Humidity

Duration

Holding Time

Geo Point

QRCode

---

# 23. Domain Event

temperature.updated

humidity.updated

gps.updated

device.connected

device.disconnected

holding.started

holding.warning

holding.expired

package.created

package.delivered

complaint.created

recall.created

---

# 24. Workflow

Receiving

↓

Storage

↓

Issue Material

↓

Production

↓

Holding

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

# 25. Domain Dependency

Master Data

↓

Receiving

↓

Production

↓

Packaging

↓

Fleet

↓

School

↓

Complaint

↓

Recall

Analytics

bergantung

pada

semua Domain.

---

# 26. Rule Engine

Setiap Domain

memiliki Rule.

Contoh

Holding

↓

Rule

Fleet

↓

Rule

Recall

↓

Rule

Storage

↓

Rule

Tidak ada Rule

di Route.

---

# 27. Deliverables

Setelah dokumen selesai.

Seluruh Business Process

telah dipetakan.

Database

menjadi mudah.

API

menjadi mudah.

Frontend

menjadi mudah.

---

# 28. Next Document

06_ERD_Master_Data.md

Membahas

ERD

Master Data

beserta relasinya.