
# ForgeTrack — Odoo Manufacturing Module

## Overview
ForgeTrack is a beginner custom Odoo module
for managing simple production orders.

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
