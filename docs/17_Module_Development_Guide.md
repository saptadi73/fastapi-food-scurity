# Food Safety Operating System (FSOS)

# 17_Module_Development_Guide.md

Version : 1.0

Status :
Draft

Document Type :
Development Guideline

Platform :
FastAPI

---

# 1. Purpose

Dokumen ini menjadi standar
pengembangan seluruh module
FSOS.

Semua programmer
harus mengikuti struktur ini.

Tidak diperbolehkan
membuat struktur sendiri.

---

# 2. Module Philosophy

Satu module

=

Satu Domain.

Contoh

Traceability

Holding

Fleet

Storage

Recall

Authentication

Semuanya berdiri sendiri.

---

# 3. Module Structure

modules/

traceability/

├── api/
│   ├── routes.py
│   ├── dependencies.py
│
├── application/
│   ├── services.py
│   ├── commands.py
│   ├── queries.py
│   ├── dto.py
│
├── domain/
│   ├── entities.py
│   ├── rules.py
│   ├── events.py
│   ├── interfaces.py
│
├── infrastructure/
│   ├── repository.py
│   ├── mapper.py
│   ├── persistence.py
│
├── schemas/
│   ├── request.py
│   ├── response.py
│
└── tests/

---

# 4. Responsibilities

API

↓

Request

↓

Application

↓

Domain

↓

Infrastructure

↓

Database

---

# 5. API Layer

API hanya

- menerima request
- validasi request
- memanggil service
- mengembalikan response

Tidak boleh

SQL

Business Rule

MQTT

---

# 6. Application Layer

Application bertugas

mengatur workflow.

Contoh

Receive Package

↓

Validate

↓

Domain

↓

Repository

↓

Publish Event

---

# 7. Domain Layer

Seluruh business rule.

Contoh

Holding

Rule

Recall

Rule

Temperature

Rule

Tidak boleh

FastAPI

SQLAlchemy

MQTT

---

# 8. Infrastructure Layer

Repository

MQTT

Redis

File Storage

External API

Google Maps

---

# 9. Schema

Request

Response

Validation

Semua menggunakan

Pydantic V2.

---

# 10. Repository

Repository hanya

CRUD

Query

Pagination

Filter

Tidak ada business rule.

---

# 11. Service

Service

mengatur

transaction.

---

# 12. Event

Setiap perubahan penting

menghasilkan Event.

PackageCreated

HoldingStarted

RecallCreated

AlarmRaised

---

# 13. Validation

Seluruh validasi

menggunakan

Pydantic.

Business Validation

berada di Domain.

---

# 14. Logging

INFO

WARNING

ERROR

DEBUG

Audit

---

# 15. Exception

BusinessException

ValidationException

NotFoundException

ConflictException

RuleException

---

# 16. Unit Test

Minimal

Repository Test

Service Test

Rule Test

API Test

---

# 17. Naming

Module

snake_case

File

snake_case

Class

PascalCase

Function

snake_case

---

# 18. API Checklist

☑ JWT

☑ Permission

☑ Validation

☑ Response Envelope

☑ Logging

☑ Swagger

☑ Unit Test

---

# 19. Development Workflow

Create Module

↓

Create Schema

↓

Create Entity

↓

Create Repository

↓

Create Service

↓

Create Route

↓

Create Test

↓

Update Swagger

---

# 20. Deliverables

Seluruh programmer

memiliki standar

yang sama.

---

# 21. Next Document

18_Deployment_Architecture.md