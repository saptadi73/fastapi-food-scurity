# Food Safety Operating System (FSOS)

# 15_Dashboard_Architecture.md

Version : 1.0

Status :
Draft

Document Type :
Dashboard Design Specification

Platform :
Vue 3
FastAPI
WebSocket

---

# 1. Purpose

Dashboard merupakan pusat monitoring
Food Safety Operating System.

Dashboard tidak melakukan
perhitungan.

Dashboard hanya menampilkan
hasil perhitungan Backend.

---

# 2. Dashboard Objectives

Dashboard harus mampu

✔ Monitoring IoT

✔ Monitoring Storage

✔ Monitoring Holding Time

✔ Monitoring Fleet

✔ Monitoring Production

✔ Monitoring Traceability

✔ Monitoring Recall

✔ Monitoring Food Safety Score

---

# 3. Dashboard Architecture

                ESP32

                  │

              MQTT Broker

                  │

              FastAPI

                  │

           Rule Engine

                  │

         Dashboard API

                  │

         REST + WebSocket

                  │

              Vue.js

---

# 4. Dashboard Modules

Dashboard terdiri dari

Home

Storage

Kitchen

Production

Holding Time

Fleet

School

Traceability

Recall

Analytics

Administration

---

# 5. Home Dashboard

Menampilkan

Total Kitchen

Total Vehicle

Storage Status

Package Today

Recall Today

Food Safety Score

Alarm Today

Device Online

---

# 6. Live Storage Dashboard

Per Storage

Current Temperature

Current Humidity

Temperature Trend

Alarm

Sensor Status

Door Status

---

# 7. Live Kitchen Dashboard

Current Production

Batch Running

Holding Status

Cooking Status

Operator

Kitchen Score

---

# 8. Holding Dashboard

Package

Remaining Time

Safe Consumption Score

Status

Countdown

Color Indicator

---

# 9. Fleet Dashboard

Vehicle

Driver

Current Position

Speed

ETA

Delay

Remaining Safe Time

---

# 10. Production Dashboard

Production Batch

Menu

Quantity

Packaging

Vehicle

Holding

---

# 11. Traceability Dashboard

Scan QR

↓

Timeline

↓

Movement

↓

Temperature

↓

GPS

↓

Operator

↓

History

---

# 12. Recall Dashboard

Complaint

↓

Package

↓

Production

↓

Vehicle

↓

School

↓

Recall Progress

---

# 13. Food Safety Dashboard

Food Safety Score

Kitchen Score

Vehicle Score

Supplier Score

School Score

---

# 14. Device Dashboard

Online

Offline

Health

Firmware

Battery

Signal

Calibration

---

# 15. Notification Dashboard

Critical Alarm

Warning

Recall

Holding

Storage

GPS

---

# 16. Dashboard Widgets

Temperature Gauge

Humidity Gauge

GPS Map

Holding Countdown

Timeline

Chart

Heat Map

KPI Card

Alarm List

---

# 17. WebSocket

Dashboard menggunakan

WebSocket

untuk

Temperature

GPS

Holding

Alarm

Device Status

Tidak melakukan polling.

---

# 18. Refresh Policy

Telemetry

Realtime

Master Data

30 detik

Analytics

5 menit

Report

Manual

---

# 19. Dashboard Color

SAFE

Hijau

WARNING

Kuning

CRITICAL

Merah

OFFLINE

Abu

---

# 20. KPI

Current Production

Package Today

Remaining Time

Average Holding

Storage Compliance

Fleet Compliance

Food Recall

Complaint

Food Safety Score

---

# 21. GIS

Google Maps

Vehicle

Kitchen

School

Storage

---

# 22. QR

Dashboard

dapat

Scan QR

↓

Digital Passport

↓

Timeline

↓

History

---

# 23. Deliverables

Dashboard mampu

✔ Live Monitoring

✔ Decision Support

✔ Traceability

✔ Recall

✔ Analytics

---

# 24. Next Document

16_API_Design.md