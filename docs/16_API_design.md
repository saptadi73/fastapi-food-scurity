# Food Safety Operating System (FSOS)

# 16_API_Design.md

Version : 1.0

Status :
Draft

Document Type :
API Design Guideline

Platform :
FastAPI
OpenAPI 3.x

---

# 1. Purpose

Dokumen ini menjelaskan standar desain REST API
yang digunakan oleh seluruh module
Food Safety Operating System (FSOS).

Seluruh endpoint harus mengikuti
dokumen ini.

Tidak boleh membuat endpoint
di luar standar.

---

# 2. REST Principles

API menggunakan prinsip REST.

GET

Mengambil data.

POST

Membuat data.

PUT

Mengubah seluruh data.

PATCH

Mengubah sebagian data.

DELETE

Soft Delete.

---

# 3. API Version

Seluruh endpoint menggunakan

/api/v1/

Contoh

/api/v1/device

/api/v1/storage

/api/v1/holding

/api/v1/traceability

---

# 4. Resource Naming

Gunakan

Noun

Tidak menggunakan Verb.

Benar

/device

/packages

/holding

Salah

/getDevice

/savePackage

/updateHolding

---

# 5. UUID

Seluruh endpoint menggunakan UUID.

Contoh

GET

/api/v1/package/{package_uuid}

---

# 6. Standard Response

Seluruh endpoint menggunakan format berikut.

{
    "success": true,
    "code": 200,
    "message": "Success",
    "data": {},
    "errors": [],
    "meta": {
        "request_id": "",
        "correlation_id": "",
        "timestamp": "",
        "execution_time_ms": 15
    }
}

---

# 7. Error Response

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

# 8. Pagination

GET

?page=1

&per_page=20

Response

page

per_page

total

total_pages

---

# 9. Filtering

GET

?status=ACTIVE

?storage=UUID

?kitchen=UUID

---

# 10. Sorting

GET

?sort=name

?sort=-created_at

---

# 11. Searching

GET

?q=Chicken

?q=Package001

?q=Vehicle001

---

# 12. Date Filter

?start_date=

?end_date=

Menggunakan ISO8601.

---

# 13. Authentication

Authorization

Bearer Token

Device

menggunakan

API Key.

---

# 14. API Categories

Authentication

Device

Telemetry

Storage

Receiving

Production

Holding

Package

Fleet

School

Complaint

Recall

Dashboard

Analytics

---

# 15. Device API

POST

/device/register

GET

/device

GET

/device/{uuid}

PATCH

/device/{uuid}

---

# 16. Telemetry API

POST

/telemetry

GET

/telemetry

GET

/telemetry/live

---

# 17. Traceability API

GET

/traceability/package/{uuid}

GET

/traceability/batch/{uuid}

GET

/traceability/raw-material/{uuid}

---

# 18. Holding API

POST

/holding/start

POST

/holding/update

GET

/holding/package/{uuid}

POST

/holding/finish

---

# 19. Fleet API

GET

/fleet/live

GET

/fleet/history

GET

/fleet/{vehicle_uuid}

---

# 20. Dashboard API

GET

/dashboard/home

GET

/dashboard/storage

GET

/dashboard/fleet

GET

/dashboard/holding

GET

/dashboard/analytics

---

# 21. Recall API

POST

/recall/start

POST

/recall/close

GET

/recall

GET

/recall/{uuid}

---

# 22. QR API

POST

/qr/generate

GET

/qr/{uuid}

POST

/qr/verify

---

# 23. WebSocket

/ws/dashboard

/ws/device

/ws/fleet

/ws/storage

/ws/holding

/ws/alarm

---

# 24. HTTP Status

200

Success

201

Created

204

No Content

400

Validation Error

401

Unauthorized

403

Forbidden

404

Not Found

409

Conflict

422

Business Rule

500

Internal Error

---

# 25. API Documentation

Swagger

Redoc

Markdown

OpenAPI JSON

---

# 26. Deliverables

Seluruh API

menggunakan standar yang sama.

---

# 27. Next Document

17_Deployment_Architecture.md