# Food Safety Operating System (FSOS)

# 06_ERD_Master_Data.md

Version : 1.0

Status :
Draft

Document Type :
Master Data Database Design

Database :
PostgreSQL 18 + UUID

---

# 1. Purpose

Dokumen ini menjelaskan desain Master Data
Food Safety Operating System.

Master Data merupakan pondasi seluruh transaksi.

Semua transaksi harus mereferensikan Master Data.

---

# 2. Design Principles

Master Data

✔ menggunakan UUID

✔ Soft Delete

✔ Audit Trail

✔ Versioning

✔ QR Ready

✔ GIS Ready

---

# 3. Master Data Overview

Master Data terdiri dari

Tenant

Kitchen

Storage

Storage Zone

Device

Vehicle

Driver

School

Supplier

Raw Material

Food Item

Recipe

Packaging Type

User

Role

Permission

Alarm Rule

Holding Rule

---

# 4. Tenant

Satu tenant

dapat memiliki

banyak

Kitchen.

Field

tenant_id

tenant_code

tenant_name

status

---

# 5. Kitchen

Kitchen merupakan

SPPG.

Field

kitchen_id

tenant_id

kitchen_code

kitchen_name

latitude

longitude

address

capacity

status

---

# 6. Storage

Storage dimiliki

Kitchen.

Storage Type

Cold Storage

Freezer

Dry Storage

Field

storage_id

kitchen_id

storage_code

storage_name

storage_type

temperature_min

temperature_max

status

---

# 7. Storage Zone

Satu Storage

dapat memiliki

beberapa Zone.

Misalnya

Rack A

Rack B

Rack C

Field

zone_id

storage_id

zone_code

zone_name

---

# 8. Device

Setiap ESP32

merupakan Device.

Field

device_id

device_uuid

device_name

device_type

firmware

hardware

mqtt_topic

status

last_online

---

# 9. Vehicle

Field

vehicle_id

vehicle_code

plate_number

vehicle_type

capacity

gps_device

status

---

# 10. Driver

Field

driver_id

driver_code

driver_name

phone

status

---

# 11. School

Field

school_id

school_code

school_name

latitude

longitude

address

student_count

status

---

# 12. Supplier

Field

supplier_id

supplier_code

supplier_name

phone

email

status

---

# 13. Raw Material

Master bahan.

Field

raw_material_id

material_code

material_name

category

uom

storage_type

recommended_temperature_min

recommended_temperature_max

maximum_storage_hours

status

---

# 14. Food Item

Master menu.

Field

food_item_id

food_code

food_name

category

uom

holding_limit_minutes

status

---

# 15. Recipe

Recipe

menghubungkan

Food Item

dengan

Raw Material.

recipe_id

food_item_id

raw_material_id

quantity

uom

---

# 16. Packaging Type

Kemasan.

Field

package_type_id

code

name

material

volume

---

# 17. Alarm Rule

Master Rule.

temperature_high

temperature_low

holding_warning

holding_expired

gps_offline

---

# 18. Holding Rule

Field

holding_rule_id

food_category

maximum_minutes

warning_minutes

discard_minutes

---

# 19. User

Field

user_id

username

fullname

email

status

---

# 20. Role

Administrator

Kitchen Operator

Warehouse

Quality Control

Driver

School

Viewer

---

# 21. Permission

Permission berbasis

RBAC.

---

# 22. Relationship

Tenant

↓

Kitchen

↓

Storage

↓

Zone

↓

Device

---

Supplier

↓

Raw Material

↓

Recipe

↓

Food Item

---

Vehicle

↓

Driver

---

Kitchen

↓

School

---

# 23. GIS

Kitchen

Storage

School

Vehicle

menggunakan

PostGIS Point.

---

# 24. QR Code Ready

Seluruh Master

memiliki

QR Identifier.

Contoh

Kitchen

↓

QR

Storage

↓

QR

Vehicle

↓

QR

Device

↓

QR

---

# 25. Audit Trail

created_at

updated_at

deleted_at

created_by

updated_by

version

---

# 26. Deliverables

Master Data

siap

digunakan

oleh

seluruh transaksi.

---

# 27. Next Document

07_ERD_Operational_Data.md

Membahas

Receiving

Storage Transaction

Production

Packaging

Delivery

School Receiving

Complaint

Recall