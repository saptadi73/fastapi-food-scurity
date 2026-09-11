# Food Safety Operating System (FSOS)

# 10_Common_Framework.md

Version : 1.0

Status :
Draft

Document Type :
Backend Framework Design

Platform :
FastAPI

---

# 1. Purpose

Dokumen ini menjelaskan Framework Internal
yang akan digunakan oleh seluruh module FSOS.

Framework ini bertujuan agar seluruh module:

- konsisten
- reusable
- mudah dipelihara
- mudah diuji

---

# 2. Framework Overview

Seluruh module menggunakan framework yang sama.

Authentication

↓

Response

↓

Validation

↓

Logging

↓

Repository

↓

Database

↓

Exception

↓

Event

---

# 3. Folder Structure

core/

config/

database/

dependency/

events/

exceptions/

logging/

middleware/

responses/

security/

settings/

validators/

---

common/

base/

constants/

dto/

helpers/

interfaces/

pagination/

utils/

---

# 4. BaseEntity

Seluruh Entity

harus mewarisi

BaseEntity.

BaseEntity memiliki

id

created_at

updated_at

deleted_at

created_by

updated_by

deleted_by

version

---

# 5. BaseRepository

Repository standar.

Method

create()

update()

delete()

find_by_id()

find_all()

exists()

count()

paginate()

---

# 6. BaseService

Seluruh service

mewarisi

BaseService.

Method

validate()

save()

update()

delete()

publish_event()

---

# 7. BaseResponse

Seluruh endpoint

menggunakan format berikut.

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

Tidak boleh ada response lain.

---

# 8. Error Response

{
 "success": false,
 "code": 400,
 "message": "Validation Error",
 "errors": [
   {
      "field":"temperature",
      "message":"Temperature is required."
   }
 ]
}

---

# 9. Pagination

Format baku.

{
 "page":1,
 "per_page":20,
 "total":120,
 "pages":6
}

---

# 10. Sorting

sort=name

sort=-created_at

---

# 11. Filtering

?status=ACTIVE

?device=Kitchen01

?batch=B240901

Semua module menggunakan format sama.

---

# 12. UUID

Semua endpoint

menggunakan UUID.

Tidak menggunakan integer.

---

# 13. Validation

Semua Request

menggunakan

Pydantic.

Tidak boleh validasi manual.

---

# 14. Logger

Logger dibagi menjadi

Application Log

Audit Log

MQTT Log

Security Log

Rule Engine Log

---

# 15. Exception

Global Exception

ValidationException

BusinessException

RuleException

MQTTException

DatabaseException

AuthenticationException

---

# 16. Middleware

Request ID

Logging

JWT

Performance

Rate Limit

---

# 17. Dependency Injection

Repository

Service

Configuration

Current User

JWT

---

# 18. Event Bus

publish()

subscribe()

dispatch()

Semua module

berkomunikasi

menggunakan Event.

---

# 19. Event Type

Device Event

Telemetry Event

Traceability Event

Holding Event

Fleet Event

Recall Event

Dashboard Event

Notification Event

---

# 20. Cache

Redis digunakan untuk

Dashboard

Rule Engine

Holding Time

AI

---

# 21. Configuration

Semua berasal dari

.env

DATABASE_URL

MQTT_HOST

JWT_SECRET

GOOGLE_MAP_API_KEY

OPENAI_API_KEY

---

# 22. Security

JWT

Refresh Token

API Key

RBAC

CORS

Rate Limit

---

# 23. Documentation

Swagger

OpenAPI

Markdown

Semua otomatis.

---

# 24. Deliverables

Framework siap digunakan

oleh seluruh module.

---

# 25. Next Document

11_Security_JWT.md