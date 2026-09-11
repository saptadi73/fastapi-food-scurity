# Food Safety Operating System (FSOS)

# 11_Security_Authentication.md

Version : 1.0

Document Type :
Security Architecture

Platform :
FastAPI

Status :
Draft

---

# 1. Purpose

Dokumen ini menjelaskan arsitektur keamanan
Food Safety Operating System.

Security tidak hanya untuk User,
tetapi juga untuk Device IoT,
ERP,
Frontend,
AI Service,
dan External API.

---

# 2. Security Principles

Platform menerapkan prinsip

Zero Trust

Setiap request

harus

terautentikasi

dan

terotorisasi.

---

# 3. Identity Model

FSOS memiliki empat Identity.

Human

↓

Device

↓

Application

↓

Service

---

# 4. Human Identity

Digunakan oleh

Administrator

Warehouse

Kitchen

QC

Driver

School

Auditor

---

# 5. Device Identity

Digunakan oleh

ESP32

Gateway

Temperature Node

Vehicle Node

Kitchen Node

Setiap Device mempunyai

UUID

API Key

Secret

Certificate (Future)

---

# 6. Application Identity

ERP MBG

Dashboard

Mobile

AI

Semua menggunakan

Client Credential.

---

# 7. Service Identity

MQTT Service

Notification

Rule Engine

Analytics

Background Worker

---

# 8. Authentication

Human

↓

JWT

Device

↓

API Key

Application

↓

OAuth2 Client Credential

Service

↓

Internal Secret

---

# 9. JWT

Access Token

15 menit

Refresh Token

7 hari

Rotasi Refresh Token

Blacklist

Logout

---

# 10. API Key

Device

menggunakan

Header

X-API-Key

atau

Authorization

---

# 11. RBAC

Role Based Access Control

Role

Administrator

Kitchen

Warehouse

QC

Driver

School

Viewer

---

# 12. Permission

Permission

Device.Read

Device.Write

Holding.Read

Holding.Update

Recall.Execute

Fleet.Read

Dashboard.Read

Rule.Manage

---

# 13. JWT Payload

sub

user_uuid

tenant

role

permission

exp

iat

jti

---

# 14. Device Authentication

ESP32

↓

Device UUID

↓

API Key

↓

MQTT

↓

FastAPI

↓

Device Registry

---

# 15. Refresh Token

Refresh Token

disimpan

di Database.

Dapat dicabut.

---

# 16. Password

bcrypt

Cost 12

---

# 17. Multi Tenant

Token

selalu

mengandung

Tenant UUID.

---

# 18. Rate Limit

Human

100 req/min

Device

30 req/min

Dashboard

Unlimited WebSocket

---

# 19. Audit

Semua Login

Logout

Permission

Rule Change

Disimpan.

---

# 20. Session

Session

tetap

disimpan

untuk Audit.

---

# 21. API Security

HTTPS

JWT

API Key

Rate Limit

CORS

---

# 22. MQTT Security

Username

Password

ACL

Topic Isolation

---

# 23. Future

TLS

mTLS

Certificate

Hardware Secure Element

---

# 24. Deliverables

FSOS memiliki
Identity Management
yang lengkap.

---

# 25. Next Document

12_Device_Registry.md