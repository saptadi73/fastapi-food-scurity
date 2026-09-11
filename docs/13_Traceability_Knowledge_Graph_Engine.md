# Food Safety Operating System (FSOS)

# 13_Traceability_Knowledge_Graph_Engine.md

Version : 1.0

Status :
Draft

Document Type :
Knowledge Graph Architecture

Platform :
FastAPI

---

# 1. Purpose

Dokumen ini menjelaskan
Food Traceability Knowledge Graph Engine.

Engine ini bertugas melakukan

- Forward Traceability
- Backward Traceability
- Asset Relationship
- Timeline
- Food Recall
- Root Cause Analysis

Engine menjadi pusat ketertelusuran
seluruh rantai pangan.

---

# 2. Philosophy

FSOS tidak melakukan traceability
berdasarkan tabel.

FSOS melakukan traceability
berdasarkan Relationship.

Asset

↓

Relationship

↓

Knowledge Graph

↓

Traceability

↓

Decision

---

# 3. Graph Overview

Supplier

↓

Raw Material Batch

↓

Storage

↓

Production Batch

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

# 4. Graph Node

Seluruh Digital Twin

merupakan Graph Node.

Contoh

Supplier

Kitchen

Storage

Vehicle

Package

Production Batch

Raw Material Batch

School

Complaint

Recall

---

# 5. Relationship

Hubungan antar Node.

Relationship Type

SUPPLIED

STORED

USED

PRODUCED

PACKAGED

LOADED

DELIVERED

RECEIVED

CONSUMED

REPORTED

RECALLED

---

# 6. asset_relationship

relationship_uuid

parent_uuid

child_uuid

relationship_type

created_at

created_by

---

# 7. Graph Example

Supplier

↓

SUPPLIED

↓

Raw Material Batch

↓

USED

↓

Production Batch

↓

PRODUCED

↓

Package

↓

LOADED

↓

Vehicle

↓

DELIVERED

↓

School

---

# 8. Forward Traceability

Mulai dari

Raw Material Batch.

↓

Production

↓

Package

↓

Vehicle

↓

School

↓

Complaint

---

# 9. Backward Traceability

Mulai dari

Complaint.

↓

Package

↓

Production

↓

Raw Material Batch

↓

Supplier

---

# 10. Timeline

Setiap Asset

memiliki Timeline.

Created

Stored

Issued

Cooked

Packaged

Loaded

Delivered

Received

Served

Complaint

Recall

---

# 11. Relationship Event

Relationship juga Event.

Package

↓

Loaded

↓

Vehicle

merupakan Event.

---

# 12. Traceability Query

Package

↓

Production Batch

↓

Raw Material

↓

Supplier

Vehicle

↓

School

↓

Complaint

---

# 13. Root Cause Analysis

Complaint

↓

Package

↓

Holding

↓

Temperature

↓

Production

↓

Supplier

---

# 14. Recall

Recall

tidak melakukan query
ke banyak tabel.

Recall

melakukan

Graph Traversal.

---

# 15. Package Passport

Package

memiliki

UUID

QR Code

Holding

Vehicle

School

Timeline

Temperature

Complaint

Recall

---

# 16. Batch Passport

Batch

memiliki

Recipe

Operator

Kitchen

Timeline

Package

Holding

Recall

---

# 17. Supplier Passport

Supplier

memiliki

Raw Material

Batch

Complaint History

Recall History

Food Safety Score

---

# 18. Vehicle Passport

Vehicle

memiliki

Driver

GPS

Temperature

Delivery

Package

Complaint

---

# 19. School Passport

School

memiliki

Receiving

Package

Complaint

Food Safety Score

---

# 20. Graph Traversal

Engine mendukung

Parent

Child

Recursive

Graph Search

Impact Analysis

---

# 21. Impact Analysis

Jika

Raw Material Batch

bermasalah

↓

Cari

Production

↓

Cari

Package

↓

Cari

Vehicle

↓

Cari

School

↓

Recall

---

# 22. Graph Cache

Relationship

di-cache

untuk mempercepat

Traceability.

---

# 23. Dashboard

Dashboard

menampilkan

Graph

bukan tabel.

---

# 24. AI

AI

membaca

Knowledge Graph.

Bukan

query SQL.

---

# 25. Deliverables

FSOS mampu melakukan

✔ Forward Traceability

✔ Backward Traceability

✔ Timeline

✔ Recall

✔ Root Cause Analysis

✔ Impact Analysis

---

# 26. Next Document

14_Holding_Time_State_Machine.md