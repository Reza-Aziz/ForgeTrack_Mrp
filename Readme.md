
# ForgeTrack — IoT + Odoo Manufacturing Lab

## Structure
```
ForgeTrack/
├── addons/forgetrack_mrp/   # Odoo custom module (Odoo 19)
├── backend/                 # MQTT subscriber → Odoo bridge
│   ├── subscriber.py        # paho-mqtt listener
│   ├── odoo_client.py       # POST /json/2 → forgetrack.machine.reading
│   ├── requirements.txt
│   └── .env                 # ODOO_URL, ODOO_DB, ODOO_API_KEY, MQTT_*
└── compose.yaml             # Odoo 19 + Postgres 15 (Docker)
```

## Overview
ForgeTrack is a beginner custom Odoo module
for managing simple production orders.

## IoT pipeline
Sensor (ESP32 + HC-SR04) → Mosquitto MQTT (`factory/machine-01/telemetry`)
→ `backend/subscriber.py` → Odoo JSON API → `forgetrack.machine.reading`.

## Features
- Create and manage production orders
- Store production data using Odoo ORM
- Track Draft, Confirmed, and Done statuses
- Validate production quantity
- Control status transitions using Python methods

## Technology
- Odoo 19 Community
- Python
- XML
- PostgreSQL
- Docker Compose

## Learning Objectives
- Understand Odoo module architecture
- Define models and fields using the Odoo ORM
- Create list and form views
- Configure model access rights
- Implement basic business logic

## Limitations
This project is a learning prototype.
It does not implement complete MRP workflows,
Bill of Materials, or automatic inventory updates.

## Local Setup
1. Start Docker Desktop.
2. Run `docker compose up -d`.
3. Open http://localhost:8069.
4. Create or open the `forgetrack_db` database.
5. Update the Apps List.
6. Install ForgeTrack MRP.

## Run the MQTT bridge
```powershell
cd backend
python -m venv .venv            # sekali saja
.venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env     # lalu isi nilai aslinya
.venv\Scripts\python subscriber.py
```
