# Food Safety Operating System (FSOS)

# 02_Backend_Architecture.md

Version : 1.0

Status :
Draft

Document Type :
Software Design Specification (SDS)

Platform :
FastAPI + PostgreSQL + MQTT

---

# 1. Purpose

Dokumen ini menjelaskan arsitektur backend Food Safety Operating System (FSOS).

Backend dirancang agar:

- Modular
- Mudah dipelihara
- Mudah dikembangkan
- Mendukung Event Driven Architecture
- Mendukung Domain Driven Design (DDD)
- Mendukung Clean Architecture

Backend bukan sekadar REST API, tetapi menjadi pusat pengambilan keputusan keamanan pangan.

---

# 2. Design Principles

Backend menggunakan prinsip berikut:

- Clean Architecture
- Domain Driven Design
- Repository Pattern
- Dependency Injection
- Service Layer
- Event Driven
- UUID First
- Async Programming
- API First

---

# 3. High Level Architecture

                    Vue Dashboard
                           │
                     REST / WebSocket
                           │
                     Presentation Layer
                           │
                  FastAPI Controller (API)
                           │
                   Application Services
                           │
                     Domain Layer
                           │
                 Infrastructure Layer
                           │
        PostgreSQL • MQTT • Redis • Storage

---

# 4. Clean Architecture

FSOS menggunakan empat layer utama.

Presentation

↓

Application

↓

Domain

↓

Infrastructure

Ketergantungan hanya boleh mengarah ke bawah.

Infrastructure tidak boleh mengetahui FastAPI.

Domain tidak boleh mengetahui SQLAlchemy.

Application tidak boleh mengetahui PostgreSQL.

---

# 5. Layer Responsibilities

## Presentation

Bertugas

- REST API
- WebSocket
- Request Validation
- JWT Validation
- Response JSON

Tidak boleh terdapat Business Rule.

---

## Application

Bertugas

- Orchestration
- Use Case
- Transaction
- Calling Domain
- Event Publishing

---

## Domain

Berisi

- Entity
- Value Object
- Domain Service
- Business Rule
- Policy

Tidak boleh menggunakan SQLAlchemy.

Tidak boleh menggunakan FastAPI.

---

## Infrastructure

Bertugas

- Database
- MQTT
- File Storage
- Email
- WhatsApp
- Redis

---

# 6. Folder Structure

app/

core/

common/

modules/

tests/

docs/

---

# 7. Core Folder

core/

config/

database/

security/

middleware/

logging/

responses/

exceptions/

events/

dependency/

settings/

Core bersifat reusable.

---

# 8. Common Folder

common/

constants/

enums/

helpers/

validators/

utils/

base/

BaseEntity

BaseRepository

BaseResponse

BaseException

---

# 9. Modules

modules/

authentication/

device/

storage/

receiving/

traceability/

production/

holding/

fleet/

recall/

dashboard/

notification/

analytics/

audit/

---

# 10. Module Structure

Contoh

modules/traceability/

api/

application/

domain/

infrastructure/

schemas/

tests/

---

# 11. API Layer

api/

routes.py

dependencies.py

Router hanya menerima request.

Router tidak boleh melakukan query database.

---

# 12. Application Layer

application/

services.py

commands.py

queries.py

dto.py

Application Layer

mengatur

alur pekerjaan.

---

# 13. Domain Layer

domain/

entities.py

services.py

rules.py

events.py

interfaces.py

Domain

berisi seluruh business rule.

---

# 14. Infrastructure Layer

infrastructure/

repository.py

orm.py

mapper.py

mqtt.py

storage.py

Tidak boleh ada Business Rule.

---

# 15. Repository Pattern

Application

↓

Repository Interface

↓

Repository Implementation

↓

SQLAlchemy

---

# 16. Event Flow

MQTT

↓

MQTT Service

↓

Event Bus

↓

Application Service

↓

Domain

↓

Repository

↓

Database

---

# 17. Dependency Injection

FastAPI Dependency Injection

digunakan pada

Repository

Service

Security

Configuration

---

# 18. UUID

Semua Entity menggunakan UUID.

Tidak menggunakan Integer Auto Increment.

---

# 19. Asynchronous

Seluruh komunikasi

Database

MQTT

WebSocket

menggunakan async.

---

# 20. SQLAlchemy

Menggunakan

SQLAlchemy 2.x

Async Session

Repository Pattern

---

# 21. Pydantic

Menggunakan

Pydantic V2

Request

Response

Validation

---

# 22. Configuration

Semua konfigurasi

berasal dari

.env

Tidak boleh

hardcode.

---

# 23. Logging

Menggunakan

Python Logging

JSON Logging

Rotating File

Audit Log

---

# 24. Exception

Global Exception Handler

Business Exception

Validation Exception

Database Exception

MQTT Exception

---

# 25. JSON Response

Seluruh endpoint menggunakan format

{
    "success": true,
    "code": 200,
    "message": "Success",
    "data": {},
    "errors": [],
    "meta": {
        "request_id": "",
        "timestamp": "",
        "execution_time": ""
    }
}

---

# 26. API Versioning

/api/v1/

Seluruh endpoint menggunakan version.

---

# 27. Documentation

Swagger

OpenAPI

Markdown API

Frontend Guide

---

# 28. Testing

Unit Test

Integration Test

API Test

Repository Test

Service Test

---

# 29. Deliverables

Setelah dokumen ini selesai

Developer dapat memahami

- struktur backend
- cara membuat module
- cara membuat endpoint
- cara membuat service
- cara membuat repository

tanpa melihat source code.

---

# 30. Next Document

03_Project_Structure.md

Membahas

- Struktur project FastAPI
- Folder
- Naming Convention
- Module Generator
- Environment
- Coding Standard