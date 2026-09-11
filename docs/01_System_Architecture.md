# Food Safety Operating System (FSOS)

# 01_System_Architecture.md

Version : 1.0

Status :
Draft

Author :
Research Project

---

# 1. Introduction

## 1.1 Background

Kasus keracunan makanan pada Program Makan Bergizi Gratis (MBG) menunjukkan bahwa pengawasan keamanan pangan tidak cukup hanya dilakukan melalui prosedur manual.

Diperlukan sebuah platform digital yang mampu melakukan monitoring keamanan pangan secara real-time, melakukan ketertelusuran (traceability), mengendalikan Holding Time, melakukan pelacakan armada distribusi, serta menyediakan mekanisme Food Recall apabila ditemukan potensi bahaya.

Platform tersebut diberi nama

Food Safety Operating System (FSOS).

FSOS merupakan platform independen yang terintegrasi dengan ERP Pengelolaan Dapur MBG.

---

# 2. Vision

Membangun platform keamanan pangan digital yang mampu melakukan monitoring, analisis, pengambilan keputusan, dan ketertelusuran pangan secara real-time.

---

# 3. Mission

Platform harus mampu

- menerima telemetry IoT
- memonitor suhu penyimpanan
- melakukan tracking armada
- mengendalikan Holding Time
- melakukan Traceability
- melakukan Food Recall
- mendukung HACCP
- menyediakan Dashboard Real-Time
- menyediakan AI Analytics

---

# 4. Position

ERP MBG

↓

mengelola

- Procurement
- Inventory
- Accounting
- Budget
- Production Planning

FSOS

↓

mengelola

- Food Safety
- Traceability
- Holding Time
- Fleet Tracking
- Recall
- HACCP
- AI

Kedua sistem saling berintegrasi menggunakan REST API.

---

# 5. System Scope

FSOS tidak menggantikan ERP.

FSOS hanya menangani keamanan pangan.

Ruang lingkup

✔ IoT Monitoring

✔ Temperature Monitoring

✔ Fleet Tracking

✔ Food Traceability

✔ Holding Time

✔ Dashboard

✔ Food Recall

✔ Notification

✔ AI Analytics

---

# 6. High Level Architecture

                    ERP MBG

                        │

                    REST API

                        │

+------------------------------------------------+

Food Safety Operating System

+------------------------------------------------+

IoT Service

MQTT

Traceability

Holding Time

Fleet Tracking

Food Recall

Dashboard

AI

+------------------------------------------------+

                        │

                 PostgreSQL

                        │

                  FastAPI

                        │

                Vue Dashboard

---

# 7. Technology Stack

Backend

FastAPI

Frontend

Vue 3

Database

PostgreSQL 18

GIS

PostGIS

IoT

ESP32

MQTT

Mosquitto

AI

OpenAI

Maps

Google Maps API

Authentication

JWT

Realtime

WebSocket

---

# 8. Architecture Pattern

Platform menggunakan

Clean Architecture.

Presentation

↓

Application

↓

Domain

↓

Infrastructure

Tidak menggunakan MVC.

---

# 9. Domain Driven Design

Domain utama

- Device
- Storage
- Traceability
- Holding
- Fleet
- Recall
- Dashboard
- Notification
- Analytics

Setiap Domain bersifat independen.

---

# 10. Event Driven Architecture

Semua telemetry IoT dianggap sebagai Event.

Contoh

temperature.updated

gps.updated

heartbeat.updated

holding.started

holding.expired

alarm.created

recall.created

Event akan diproses oleh Domain Engine.

---

# 11. Core Modules

Core

Configuration

Database

Security

Response

Exception

Logging

Event

MQTT

Utilities

---

# 12. Business Modules

Authentication

Device

Storage

Receiving

Production

Traceability

Holding Time

Fleet Tracking

Recall

Dashboard

Notification

Analytics

---

# 13. External Systems

ERP MBG

Google Maps API

MQTT Broker

OpenAI

WhatsApp Gateway

Email Gateway

---

# 14. Deployment

ESP32

↓

Mosquitto

↓

FastAPI

↓

PostgreSQL

↓

Vue

↓

Browser

---

# 15. Integration

ERP

↓

REST API

↓

FSOS

↓

IoT

↓

Dashboard

---

# 16. Design Principles

Modular

Scalable

Event Driven

Clean Architecture

DDD

Repository Pattern

Dependency Injection

RESTful API

JWT Authentication

OpenAPI Documentation

---

# 17. Coding Standard

Python

PEP8

Typing

Pydantic V2

SQLAlchemy 2

Async

UUID

---

# 18. JSON Response

Seluruh endpoint wajib menggunakan

Response Envelope.

Tidak boleh mengembalikan object secara langsung.

---

# 19. API Documentation

Seluruh endpoint wajib memiliki

Description

Payload

Parameter

Business Rule

Permission

Response

Error Code

Example

---

# 20. Next Document

02_Backend_Architecture.md

Menjelaskan

- Clean Architecture
- Folder Project
- Module Layout
- Dependency Injection
- Repository Pattern
- Service Pattern
- Event Engine