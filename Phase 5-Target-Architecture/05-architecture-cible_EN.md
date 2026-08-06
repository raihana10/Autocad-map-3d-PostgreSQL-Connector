# Phase 5 — Target Architecture & Alternative Solution

> **Phase 5 of the Project** — Definition, implementation, and validation of the alternative technical architecture for converting and operating the Autodesk Industry Model under PostgreSQL/PostGIS.

---

## 1. Objective of Phase 5

The primary objective of Phase 5 is to implement an end-to-end technical architecture capable of exporting and operating an **Autodesk Infrastructure Administrator Industry Model** using a **PostgreSQL / PostGIS** spatial database, eliminating any dependency on Oracle, SQL Server, or the paid proprietary connector TKI PGP.

The solution satisfies two core requirements:
1. **Automated DDL Schema Generation (Approach A)**: Faithful translation of the SQLite Industry Model structure (feature classes, attributes, domain values, relationships, foreign keys, spatial indexes, and triggers) into PostgreSQL/PostGIS DDL.
2. **Real-time Bidirectional Exploitation (Approach E)**: Utilization of the native PostgreSQL FDO provider in AutoCAD Map 3D (`_MAPCONNECT`) for real-time spatial editing and querying.

---

## 2. Synthesis and Justification of Evaluated Architectures

To identify the optimal alternative to TKI PGP, 5 technical approaches were systematically evaluated:

| Approach | Description | Status | Decision Rationale |
|---|---|---|---|
| **A. Python DDL Generator** | Script inspecting the Autodesk SQLite metadata to generate PostGIS DDL scripts automatically. | **Retained (Step 1)** | Delivers total control over relational structure, FDO data typing, foreign keys, GiST indexes, and PL/pgSQL triggers. |
| **B. Periodic Batch Sync (ETL)** | Periodic data export/import between SQLite and PostgreSQL at scheduled intervals. | **Eliminated** | Incompatible with real-time collaborative editing. High risk of data conflicts and lack of responsiveness during cartographic edits. |
| **C. C# / .NET Plugin (Map 3D API)** | Client extension DLL directly integrated within AutoCAD Map 3D. | **Eliminated** | Excessive complexity and steep learning curve for the project timeline. Requires compilation and deployment on every client machine. |
| **D. Java Plugin (API)** | Extension or standalone application written in Java. | **Eliminated** | Autodesk ecosystem is exclusively oriented towards .NET / C++. No official Java API exists for AutoCAD Map 3D. |
| **E. Native PostgreSQL FDO Provider** | Built-in native PostgreSQL FDO provider in AutoCAD Map 3D (`_MAPCONNECT`). | **Retained (Step 2)** | Leverages Autodesk's official native spatial engine, ensuring seamless real-time editing without third-party plugins. |

---

## 3. Overall Retained Architecture (Combination A + E)

```
┌────────────────────────────────────────────────────────────────────────┐
│                   1. Source Data Model (SQLite)                        │
│    Extracted file from Autodesk Infrastructure Administrator           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    │ [Approach A - Python Engine]
                                    │ Introspection of 6 metadata catalogs
                                    │ Dynamic %TEMP% discovery & FK/PK resolution
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│               2. Target PostgreSQL / PostGIS Database                  │
│    - Feature Tables & PostGIS Geometries (Point, LineString, Polygon) │
│    - Domain Reference Tables (_TBD) & Enumerated Values Populated      │
│    - Dynamic Foreign Keys (FID for classes, ID for domain tables)      │
│    - GiST Spatial Indexes on geometry columns                          │
│    - PL/pgSQL Triggers (Automatic ST_Length calculations)             │
└───────────────────────────────────▲────────────────────────────────────┘
                                    │
                                    │ [Approach E - Native Provider]
                                    │ FDO PostgreSQL Provider (Map 3D)
                                    │ (Real-time read & write access)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 3. AutoCAD Map 3D Client Workstation                   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Converter Engine Specifications (`convert_autodesk_to_postgis.py`)

### 4.1 Introspection of the 6 Master Metadata Catalogs
The Autodesk SQLite file contains ~170 tables, mostly dedicated to UI configuration. Our converter targets the 6 master metadata catalogs identified during Phase 3 reverse engineering:

1. **`TB_DICTIONARY`**: Master registry of domain feature entities (`F_CLASS_NAME`), FDO object types (`F_CLASS_TYPE`: Point, LineString, Polygon, Table), and class inheritance (`MODEL_F_CLASS_ID`).
2. **`TB_ATTRIBUTE`**: List of custom business attributes configured per feature class.
3. **`fdo_columns`**: FDO logical data typing (`data_type`: Varchar, Number, Double, Boolean) and data precision/length.
4. **`geometry_columns`**: Definition of spatial column names (`GEOM`), OGC geometry types, and Coordinate Reference Systems (default EPSG 2154 / Lambert-93).
5. **`TB_DOMAIN` + `<DOMAIN>_TBD` Tables**: Extraction of domains/enumerations and automatic generation of `INSERT` statements.
6. **`TB_RELATIONS`**: Inter-class relationship metadata and attribute-to-domain bindings.

### 4.2 Dynamic Column Introspection & Foreign Key PK Resolution
* **Version-Variation Resilience**: The `find_col_name()` function inspects actual SQLite column names dynamically to handle Autodesk schema variations seamlessly.
* **Differentiated Foreign Key Resolution**: The `get_pk_column_name()` function dynamically inspects parent table primary keys:
  - References `FID` for parent feature classes.
  - References `ID` for domain reference tables (`_TBD`).

### 4.3 Spatial Indexing & PL/pgSQL Triggers
* **GiST Spatial Indexes**: Automatic creation of `USING GIST` indexes on all PostGIS geometry columns.
* **Automatic Metric Calculations**: Deployment of PL/pgSQL triggers (`fn_calc_autodesk_length`) to recalculate `ST_Length` on `INSERT` or `UPDATE` operations.

---

## 5. Background Sync Engine (`watch_and_sync.py`)

### 5.1 Generic Dynamic Discovery in `%TEMP%`
Autodesk Infrastructure Administrator extracts Industry Models into dynamic temporary subfolders with random GUIDs (`AppData\Local\Temp\Embedded\<GUID>\`).
* Uses `tempfile.gettempdir()` (%TEMP% on Windows) to avoid hardcoded user paths.
* Performs a generic recursive search validating the presence of `TB_DICTIONARY`.
* Filters and sorts matching candidates by modification timestamp (`st_mtime`) to select the newest instance automatically.

### 5.2 Non-Destructive Synchronization Logic
To protect existing spatial and tabular GIS data edited by cartographers in PostgreSQL:
* Employs `CREATE TABLE IF NOT EXISTS` for all feature tables.
* Inserts domain values safely using `INSERT ON CONFLICT DO NOTHING`.
* Handles schema additions via `ALTER TABLE ADD COLUMN IF NOT EXISTS`.

### 5.3 Automated Database Naming
PostgreSQL Database Name = SQLite Industry Model Name (e.g., `Industry model initial` → BDD `industry_model_initial`). This provides clear, consistent naming for end-user FDO connections in AutoCAD Map 3D.

---

## 6. Deployment Plan & Industrialization (Phase 6 Roadmap)

For enterprise production deployment (zero command-line interaction for end-users):

1. **Administrator GUI Panel**:
   - Developed using **CustomTkinter** (Python).
   - Allows administrators to enter PostgreSQL credentials and select discovery modes (Auto via `%TEMP%` or manual file selection).
   - Encrypted, one-time credential storage.
2. **Packaging & Windows Background Service**:
   - Compiled into a standalone binary (`.exe`) via **PyInstaller**.
   - Deployed as a **Windows Service** (via **NSSM**) starting automatically on Windows boot.
   - System Tray icon for real-time monitoring and sync status inspection.
3. **Concurrent Multi-Model Support**:
   - Background service concurrently watches and syncs multiple active Industry Models.
4. **End-User Experience in AutoCAD Map 3D**:
   - Shared FDO connection profiles (`.fdo` / `.xml`) pre-configured by administrators.
   - Cartographers click on saved connections and edit data directly without technical overhead.

---

## 7. Phase 5 Summary & Validation

Full integration testing was executed successfully on `Industry model initial`:
- Generated clean PostGIS DDL (`test_schema.sql`).
- Validated all 261 SQL statements covering feature classes, populated domain tables, adapted foreign key constraints (`ID`/`FID`), GiST indexes, and PL/pgSQL spatial triggers.
