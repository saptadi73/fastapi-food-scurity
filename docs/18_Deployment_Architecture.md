# Food Safety Operating System (FSOS)

# 18_Deployment_Architecture.md

Version : 1.0

Status :
Draft

Document Type :
Production Deployment Architecture

Platform :
Ubuntu 22.04 LTS

---

# 1. Purpose

Dokumen ini menjelaskan arsitektur deployment
Food Safety Operating System (FSOS).

Deployment dirancang agar

- mudah dipasang
- mudah dipelihara
- mudah dikembangkan
- siap produksi

---

# 2. Production Architecture

                   Internet
                        │
                    HTTPS 443
                        │
                     Nginx SSL
                        │
      ┌─────────────────┼────────────────┐
      │                 │                │
 REST API          WebSocket         Static Vue
      │
   Gunicorn
      │
   FastAPI
      │
──────────────────────────────────────────────
Business Layer
Rule Engine
Holding Engine
Traceability
Fleet
Recall
Dashboard
──────────────────────────────────────────────
      │
 PostgreSQL 18 + PostGIS
      │
 Redis
      │
 Mosquitto MQTT
      │
 ESP32 Device

---

# 3. Technology Stack

OS

Ubuntu 22.04 LTS

Backend

FastAPI

ASGI

Gunicorn + UvicornWorker

Frontend

Vue 3

Database

PostgreSQL 18

GIS

PostGIS

MQTT

Mosquitto

Cache

Redis

Reverse Proxy

Nginx

SSL

Let's Encrypt

---

# 4. Backend Deployment

Gunicorn

↓

4 Worker

↓

Async

↓

FastAPI

Tidak menggunakan

uvicorn

langsung.

---

# 5. Frontend

Vue

dibuild

↓

dist/

↓

Nginx

---

# 6. MQTT

Mosquitto

berjalan

sebagai service.

ESP32

↓

MQTT

↓

FastAPI MQTT Service

---

# 7. Redis

Digunakan untuk

Dashboard Cache

Session

Holding Cache

Rule Cache

Rate Limit

WebSocket

---

# 8. PostgreSQL

Database utama

PostgreSQL 18

Extension

UUID

PostGIS

pgcrypto

---

# 9. Folder Structure

/opt/fsos/

backend/

frontend/

logs/

backup/

scripts/

mqtt/

storage/

---

# 10. Environment

.env

DATABASE_URL

MQTT_HOST

MQTT_PORT

JWT_SECRET

REDIS_URL

GOOGLE_MAP_API_KEY

OPENAI_API_KEY

SMTP

WA_API

---

# 11. Logging

Application

MQTT

Audit

Security

Error

Nginx

---

# 12. Backup

Daily

Database

Weekly

File

Monthly

Archive

---

# 13. Monitoring

CPU

RAM

Disk

MQTT

Database

Redis

Gunicorn

Nginx

ESP32 Online

---

# 14. Security

HTTPS

JWT

API Key

Firewall

Fail2Ban

UFW

---

# 15. WebSocket

/ws/dashboard

/ws/storage

/ws/device

/ws/fleet

/ws/holding

/ws/alarm

---

# 16. Production Service

systemd

fsos-api.service

mosquitto.service

redis.service

postgresql.service

nginx.service

---

# 17. Nginx

api.domain.com

↓

FastAPI

dashboard.domain.com

↓

Vue

mqtt.domain.com

↓

WebSocket Proxy

---

# 18. SSL

Let's Encrypt

Auto Renewal

HSTS

TLS 1.3

---

# 19. Server Specification

Development

4 Core

8 GB RAM

100 GB SSD

Production

8 Core

16 GB RAM

250 GB SSD

National Scale

16 Core

32 GB RAM

1 TB SSD

---

# 20. Scaling

ESP32

↓

Mosquitto

↓

FastAPI

↓

Redis

↓

PostgreSQL

↓

Dashboard

Semua dapat diskalakan
secara independen.

---

# 21. Disaster Recovery

Backup

↓

Restore

↓

Health Check

↓

Restart Service

↓

Monitoring

---

# 22. Deliverables

Deployment siap untuk

✔ Development

✔ Staging

✔ Production

✔ Multi Kitchen

✔ Nasional

---

# 23. Phase Complete

Seluruh fase desain FSOS selesai.