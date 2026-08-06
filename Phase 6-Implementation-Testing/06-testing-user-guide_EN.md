# 📘 End-to-End Testing Guide & Roadmap (English Version)
**Project:** AutoCAD Map 3D - PostgreSQL / PostGIS Connector  
**Phase:** Phase 6 — Implementation & Multi-Model Synchronization Testing  
**Audience:** Project Advisor / Academic Examiner  

---

## Guide Objective

This document provides a **complete A-to-Z testing roadmap** to deploy, run, and validate the automatic connector between **Autodesk Infrastructure Administrator / AutoCAD Map 3D** and **PostgreSQL / PostGIS**.

> **Important Note:** The main script `watch_and_sync.py` is the master automation service. It **automatically invokes** `convert_autodesk_to_postgis.py` in the background. Running the single command `watch_and_sync.py` is all that is required to test the entire pipeline end-to-end (DDL conversion, database provisioning, structure synchronization, physical deletions, and data record upserts).

---

## 1. Prerequisites & Environment Setup

### 1.1 Required Software
- **Python:** Version 3.9 or higher.
- **PostgreSQL / PostGIS:** PostgreSQL 13+ with the PostGIS extension installed.
- **Autodesk Infrastructure Administrator / AutoCAD Map 3D:** (or any Autodesk Industry Model `.sqlite` database file).

### 1.2 Python Dependencies Installation
Open a terminal (`cmd` or `PowerShell`) in the `Phase 6-Implementation-Testing` directory and run:

```powershell
pip install -r requirements-dev.txt
```

---

## 2. End-to-End Testing Roadmap (Simplified Roadmap)

```
[Step 1] Open/Create Industry Model in Autodesk Infrastructure Administrator
   │
   ▼
[Step 2] Launch Master Service (watch_and_sync.py)
   │ ├── Automatic detection of SQLite in %TEMP% / Embedded
   │ ├── Automatic execution of convert_autodesk_to_postgis.py
   │ ├── Automatic PostgreSQL Database creation & PostGIS extension enabling
   │ └── Application of Tables, Foreign Keys, GiST Indexes & Triggers
   ▼
[Step 3] Test Dynamic Schema Modifications (Add Classes & Attributes)
   │
   ▼
[Step 4] Test Physical Deletion (DROP TABLE CASCADE & DROP COLUMN)
   │
   ▼
[Step 5] Native FDO Connection & Visualization in AutoCAD Map 3D
```

---

## Step 1: Autodesk Industry Model Preparation

1. Open **Autodesk Infrastructure Administrator**.
2. Create or open an Industry Model SQLite database.
3. When opening the model, Autodesk generates an active temporary SQLite file located by default in the `%TEMP%` directory (Example: `C:\Users\PC\AppData\Local\Temp\Embedded`).

---

## Step 2: Launching End-to-End Synchronization (`watch_and_sync.py`)

This **single master command** handles DDL conversion, creates the target PostgreSQL database, provisions PostGIS, applies table schemas, handles additions/updates/deletions, and syncs spatial records.

### Run Command:
```powershell
python "C:\Path\To\Your_script_watch_and_sync_depending_on_ur_actual_path_to_the_script.py(Phase 6-Implementation-Testing\scripts\watch_and_sync.py)" --pg-user USER_NAME --pg-pass YOUR_PASSWORD --initial-sync
```

### CLI Command Options:
- `--initial-sync`: Triggers an immediate initial synchronization on startup.
- `--srid`: Sets PostGIS coordinate system EPSG code (default: `2154` - Lambert-93).
- `--dir`: (Optional) Specifies a custom directory to watch if SQLite files are outside `%TEMP%`.

### Expected Console Output:
1. Automatically detects active Autodesk Industry Model files.
2. Transparently calls `convert_autodesk_to_postgis.py`.
3. Automatically creates the target PostgreSQL database.
4. Enables the PostGIS extension (`CREATE EXTENSION IF NOT EXISTS postgis`).
5. Applies table schemas and initiates **Watchdog** real-time file observer mode.

---

## Step 3: Dynamic Schema Modification Tests

While `watch_and_sync.py` is running in the background console:

### Test A: Adding a new Class (Table Feature/Geo)
1. In **Autodesk Infrastructure Administrator**, add a new class (e.g., `VALVE` or `BUILDING`).
2. Save the Industry Model.
3. **Observation:** In the Python console, `watch_and_sync.py` immediately detects the change, compiles the DDL, and creates the new table in PostgreSQL along with its spatial indexes.

### Test B: Adding a new Attribute (Column)
1. In Infrastructure Administrator, add a new attribute to an existing class.
2. Save.
3. **Observation:** The service automatically executes `ALTER TABLE "table" ADD COLUMN "column_name" Type`.

> 💡 **Note on Class Renaming (SQL Table Name vs Display Caption):**  
> In Autodesk Infrastructure Administrator, editing a class title in the tree view updates the `CAPTION` property (the user-friendly display label) while **retaining the physical SQL table name** (`NAME`). The PostgreSQL connector uses the physical SQL table name to create and manage PostgreSQL tables (`CREATE TABLE "PHYSICAL_NAME"`), while logging the display caption in DDL comments.

---

## Step 4: Physical Deletion Sync Test

When an element is deleted in Autodesk Infrastructure Administrator (after confirmation in the UI):

1. In **Autodesk Infrastructure Administrator**, delete an attribute or an entire feature class.
2. Confirm the deletion prompt in Autodesk.
3. Save the model file.
4. **Observation in PostgreSQL:**
   - The table is immediately dropped in PostgreSQL via `DROP TABLE "table" CASCADE`.
   - The column is immediately dropped via `ALTER TABLE "table" DROP COLUMN IF EXISTS "column"`.
   - An audit report JSON file named `schema_diff_YYYYMMDD_HHMMSS.json` is automatically saved in the workspace.

---

## Step 5: Native FDO Connection in AutoCAD Map 3D

To consume and visualize synchronized data directly in AutoCAD Map 3D:

1. In AutoCAD Map 3D, open the **Task Pane** palette (`MAPWSPACE` -> On).
2. Click **Data** -> **Connect to Data** (FDO Connection).
3. Select **Add PostgreSQL / PostGIS Connection**.
4. Enter PostgreSQL connection details.
5. Click **Connect** and **Add to Map**.

---

## Workspace File Overview

| File | Purpose |
| :--- | :--- |
| `scripts/watch_and_sync.py` | **Master Script:** Real-time monitoring, DB provisioning, schema/data sync & physical deletion |
| `scripts/convert_autodesk_to_postgis.py` | DDL Conversion Engine (called automatically by `watch_and_sync.py`) |
| `requirements-dev.txt` | Python package dependency list |
| `06-testing-user-guide_EN.md` | English User & Testing Guide |
