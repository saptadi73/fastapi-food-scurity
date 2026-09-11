# Food Safety Operating System (FSOS)

# 09_Rule_Engine_Architecture.md

Version : 1.0

Status :
Draft

Document Type :
Rule Engine Design Specification

Platform :
FastAPI

---

# 1. Purpose

Dokumen ini menjelaskan Rule Engine
yang menjadi pusat seluruh keputusan
Food Safety Operating System (FSOS).

Rule Engine bertugas mengevaluasi
seluruh telemetry,
operasional,
holding time,
traceability,
dan complaint.

Rule Engine tidak menyimpan data.

Rule Engine hanya menghasilkan keputusan.

---

# 2. Why Rule Engine

Sebagian besar sistem hanya

Telemetry

↓

Database

↓

Dashboard

FSOS berbeda.

Telemetry

↓

Rule Engine

↓

Decision

↓

Database

↓

Dashboard

Dengan demikian

Dashboard tidak lagi menghitung.

Semua keputusan sudah dibuat.

---

# 3. Architecture

ESP32

↓

MQTT

↓

MQTT Service

↓

Telemetry Parser

↓

Event Bus

↓

Rule Engine

↓

Decision Engine

↓

Notification

↓

Repository

↓

PostgreSQL

---

# 4. Rule Categories

Rule dibagi menjadi

Food Safety

Holding Time

Temperature

Fleet

Traceability

Recall

Notification

Analytics

---

# 5. Food Safety Rules

Contoh

Storage Temperature

>

5°C

lebih dari

15 menit

↓

Critical Alarm

↓

Notify Operator

↓

Create Incident

---

# 6. Holding Time Rules

Cooking Finished

↓

Start Holding

↓

Remaining Time

↓

Warning

↓

Expired

↓

Discard

---

# 7. Temperature Rules

Storage

Min

Max

Warning

Critical

Recovery

---

# 8. Fleet Rules

Vehicle Offline

Vehicle Delay

ETA Exceeded

GPS Lost

Vehicle Arrived

---

# 9. Traceability Rules

Batch

↓

Package

↓

Vehicle

↓

School

↓

Complaint

↓

Recall

---

# 10. Recall Rules

Complaint

↓

Find Package

↓

Find Batch

↓

Find Vehicle

↓

Find School

↓

Recall

↓

Notification

---

# 11. Notification Rules

Alarm

↓

WhatsApp

↓

Telegram

↓

Dashboard

↓

Email

---

# 12. Analytics Rules

Food Safety Score

Holding KPI

Fleet KPI

Temperature KPI

Recall KPI

---

# 13. Rule Structure

Rule ID

Rule Name

Rule Category

Priority

Condition

Action

Enabled

Created By

Version

---

# 14. Rule Execution

Telemetry

↓

Find Rule

↓

Evaluate

↓

Execute

↓

Event

↓

Database

---

# 15. Rule Priority

Critical

High

Medium

Low

Info

---

# 16. Rule Condition

Example

Temperature > 5

AND

Duration > 15 Minutes

AND

Storage Type = Cold Storage

---

# 17. Rule Action

Alarm

Notification

Change Status

Create Incident

Create Recall

Discard Package

Create Audit

---

# 18. Rule Version

Setiap Rule

mempunyai Version.

Perubahan Rule

tidak menghapus

History.

---

# 19. Rule Log

Semua Rule

disimpan.

rule_log

rule_uuid

entity_uuid

executed_at

result

duration

---

# 20. Rule Engine Flow

Event

↓

Rule Match

↓

Condition

↓

Decision

↓

Action

↓

Notification

↓

Audit

---

# 21. Decision Engine

Decision Engine

menghasilkan

Safe

Warning

Critical

Unsafe

Discard

Recall

---

# 22. Rule Repository

Seluruh Rule

disimpan

di Database.

Tidak hardcode.

---

# 23. Rule Management

Administrator

dapat

Enable

Disable

Versioning

Simulation

---

# 24. Simulation

Rule

dapat

disimulasikan

sebelum aktif.

---

# 25. Future AI

AI

akan memberikan

Rule Recommendation.

---

# 26. Deliverables

FSOS memiliki

Decision Support

yang konsisten.

---

# 27. Next Document

10_Common_Framework.md