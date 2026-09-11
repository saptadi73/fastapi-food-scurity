# Food Safety Operating System (FSOS)

# 03_Project_Structure.md

Version : 1.0

Status :
Draft

Document Type :
Software Architecture

---

# 1. Purpose

Dokumen ini menjelaskan struktur repository dan struktur project
Food Safety Operating System (FSOS).

Seluruh project dirancang agar:

- Modular
- Scalable
- Mudah dipelihara
- Mudah dideploy
- Mendukung pengembangan multi developer

---

# 2. Repository Structure

foodsafety-platform/

├── backend/
├── frontend/
├── mobile/
├── firmware/
├── docs/
├── deployment/
├── database/
├── docker/
├── scripts/
├── tools/
├── tests/
└── README.md

Setiap folder mempunyai tanggung jawab masing-masing.

---

# 3. Backend Structure

backend/

app/

config/

docs/

tests/

requirements/

alembic/

scripts/

.env

README.md

main.py

---

# 4. App Structure

app/

core/

common/

modules/

shared/

resources/

---

# 5. Core

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

Core hanya berisi framework internal.

Tidak boleh ada business rule.

---

# 6. Shared

shared/

dto/

interfaces/

base/

constants/

helpers/

validators/

utils/

Shared digunakan seluruh module.

---

# 7. Modules

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

master/

iap module berdiri sendiri.

---

# 8. Module Structure

Contoh

modules/

traceability/

api/

application/

domain/

infrastructure/

schemas/

tests/

---

# 9. API

api/

routes.py

dependencies.py

Router hanya menerima request.

Tidak boleh ada query database.

---

# 10. Application

application/

services.py

commands.py

queries.py

dto.py

Application mengatur workflow.

---

# 11. Domain

domain/

entities.py

rules.py

events.py

interfaces.py

services.py

Seluruh business rule berada di sini.

---

# 12. Infrastructure

infrastructure/

repository.py

orm.py

mapper.py

mqtt.py

storage.py

Semua akses eksternal berada di layer ini.

---

# 13. Schemas

schemas/

request.py

response.py

filter.py

validator.py

Menggunakan Pydantic V2.

---

# 14. Tests

tests/

unit/

integration/

fixtures/

mock/

Setiap module memiliki test sendiri.

---

# 15. Naming Convention

Folder

snake_case

File

snake_case

Class

PascalCase

Function

snake_case

Variable

snake_case

Constant

UPPER_CASE

---

# 16. Configuration

Semua konfigurasi berasal dari

.env

Contoh

DATABASE_URL

MQTT_HOST

MQTT_PORT

JWT_SECRET

GOOGLE_MAP_API_KEY

OPENAI_API_KEY

Tidak boleh ada hardcode.

---

# 17. API Prefix

/api/v1/

Contoh

/api/v1/device

/api/v1/storage

/api/v1/holding

/api/v1/fleet

/api/v1/traceability

---

# 18. UUID

Seluruh entity menggunakan UUID.

Tidak menggunakan integer autoincrement.

---

# 19. Alembic

Seluruh perubahan database menggunakan Alembic Migration.

Tidak boleh mengubah database manual.

---

# 20. Logging

logs/

application.log

mqtt.log

security.log

audit.log

error.log

---

# 21. Documentation

docs/

architecture/

api/

database/

deployment/

workflow/

Seluruh dokumentasi menggunakan Markdown.

---

# 22. Docker

docker/

backend/

postgres/

redis/

mosquitto/

nginx/

Mendukung deployment container.

---

# 23. Scripts

scripts/

backup/

restore/

migration/

seed/

maintenance/

---

# 24. Git Rules

main

production

develop

feature/*

bugfix/*

hotfix/*

---

# 25. Deliverables

Setelah dokumen ini selesai:

✔ Struktur project telah baku

✔ Mudah dipelihara

✔ Mudah ditambah module

✔ Mendukung tim developer

---

# 26. Next Document

04_Database_Architecture.md

Berisi:

- PostgreSQL
- UUID
- Relasi
- Event Log
- Telemetry
- Traceability
- Holding Time
- Fleet Tracking
- Food Recall