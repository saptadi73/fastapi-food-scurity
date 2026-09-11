# Food Safety Operating System (FSOS)

# 14_Holding_Time_Engine.md

Version : 1.0

Status :
Draft

Document Type :
Business Engine Design

Platform :
FastAPI

---

# 1. Purpose

Holding Time Engine merupakan pusat pengendalian
umur aman makanan (Safe Consumption Time).

Engine bertugas menghitung:

- Remaining Safe Time
- Warning
- Critical
- Expired
- Discard Recommendation

Holding Time tidak dihitung oleh Frontend.

Semua perhitungan dilakukan oleh Backend.

---

# 2. Objective

Menjamin bahwa makanan yang diterima sekolah
masih berada pada batas aman konsumsi.

Engine akan:

✔ menghitung Remaining Time

✔ mengirim Warning

✔ mengubah status Package

✔ mengirim Alarm

✔ mendukung Recall

---

# 3. Holding Time Flow

Cooking Finished

↓

Hot Holding

↓

Packaging

↓

Vehicle Loading

↓

Transportation

↓

School Receiving

↓

Serving

↓

Consumed

---

# 4. State Machine

Package mempunyai state.

CREATED

↓

COOKING

↓

HOT_HOLDING

↓

PACKAGED

↓

LOADED

↓

IN_TRANSIT

↓

RECEIVED

↓

SERVED

↓

CONSUMED

↓

ARCHIVED

Jika terjadi masalah

↓

DISCARDED

atau

RECALL

---

# 5. Holding Timer

Holding Timer dimulai

ketika

Cooking Finished.

Field

holding_started_at

holding_limit_minutes

warning_minutes

critical_minutes

expired_at

remaining_seconds

---

# 6. Holding Policy

Setiap kategori makanan
memiliki policy berbeda.

Contoh

Rice

180 menit

Chicken

120 menit

Vegetable

90 menit

Milk

60 menit

Policy disimpan pada database.

---

# 7. Remaining Safe Time

Remaining Time

=

Expired Time

-

Current Time

Nilai ini selalu diperbarui.

---

# 8. Status

SAFE

↓

WARNING

↓

CRITICAL

↓

EXPIRED

↓

DISCARDED

---

# 9. Warning

Jika Remaining Time

< 30 menit

↓

Warning

Jika

< 10 menit

↓

Critical

Jika

0

↓

Expired

---

# 10. Dynamic Adjustment

Remaining Time

tidak selalu linier.

Rule dapat mengurangi Remaining Time.

Contoh

Storage Temperature

> 5°C

selama

20 menit

↓

Holding Time

dikurangi

15 menit

---

# 11. Telemetry Integration

Engine membaca

Temperature

Humidity

GPS

ETA

Door Sensor

Alarm

---

# 12. Vehicle Delay

Jika ETA

lebih lama

dibanding

Remaining Time

↓

Create Warning

↓

Notify Kitchen

↓

Notify Driver

---

# 13. School Arrival

Saat QR Code diterima

Holding Engine

menghitung ulang

Remaining Time.

---

# 14. Dashboard

Dashboard menampilkan

Holding Countdown

Misalnya

Package

PKG00123

Remaining

01:12:35

Status

SAFE

---

# 15. Package Timeline

Cooking Finished

08:00

Packaging

08:15

Loaded

08:20

Arrived

08:52

Served

09:15

Consumed

09:30

---

# 16. Alarm

Holding Warning

Holding Critical

Holding Expired

Vehicle Delay

Storage Too Hot

---

# 17. Rule Engine

Holding Engine

berkonsultasi

dengan

Rule Engine.

Rule dapat berubah

tanpa mengubah source code.

---

# 18. Decision

Jika

Remaining Time

< ETA

↓

Unsafe Delivery

↓

Reject

↓

Recall Candidate

---

# 19. API

POST

/api/v1/holding/start

POST

/api/v1/holding/update

GET

/api/v1/holding/{package_uuid}

POST

/api/v1/holding/finish

---

# 20. Response

{
    "package_uuid":"...",
    "status":"WARNING",
    "remaining_minutes":28,
    "expired_at":"..."
}

---

# 21. Deliverables

Holding Engine mampu

✔ menghitung Remaining Time

✔ mengubah status

✔ memberikan warning

✔ mendukung dashboard

✔ mendukung recall

---

# 22. Next Document

15_Dashboard_Architecture.md