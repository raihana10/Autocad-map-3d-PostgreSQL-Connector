# Phase 5 — Target Architecture & Alternative Solution

> **Phase 5 of the Project** — Definition and justification of the alternative solution for converting and utilizing Autodesk Data Models under PostgreSQL/PostGIS.

---

## 1. Phase Objective

The objective of Phase 5 is to define the technical architecture allowing an **Autodesk Infrastructure Administrator Data Model** to be operated with a **PostgreSQL / PostGIS** database, without relying on Oracle, SQL Server, or the paid commercial TKI PGP connector.

The solution must satisfy two core requirements:
1. **DDL Schema Generation**: Faithfully translate the SQLite Data Model structure to PostgreSQL/PostGIS.
2. **Real-time Editing**: Enable AutoCAD Map 3D to interact (read and write) directly with the PostgreSQL database.

---

## 2. Summary of Evaluated Architectures

| Approach | Description | Status | Justification |
|---|---|---|---|
| **A. SQL Script Generation (Python)** | Parse SQLite Data Model and automatically generate PostGIS DDL. | **Selected (Step 1)** | Generates exact, controlled relational and spatial structure. |
| **B. Periodic ETL Sync** | Batch synchronization script at regular intervals. | **Eliminated** | Does not allow real-time spatial editing required in CAD/GIS workflows. |
| **C. C# / .NET Plugin (Map 3D API)** | Native client extension developed inside Map 3D. | **Eliminated** | High complexity and steep learning curve for internship timeframe. |
| **D. Java Plugin** | Java client plugin. | **Eliminated** | Autodesk ecosystem is .NET-oriented; no official Java API exists for Map 3D. |
| **E. Native PostgreSQL FDO Connector** | Utilizing AutoCAD Map 3D's native PostgreSQL FDO provider. | **Selected (Step 2)** | Reuses Autodesk's native, official data access engine for real-time live editing. |

---

## 3. Selected Architecture: Combination A + E (Generator + Native FDO Connection)

The selected architecture combines **Approach A** and **Approach E** to provide a complete, robust, and live pipeline:

```
┌─────────────────────────────────────────────────────────┐
│              1. Source Data Model (SQLite)              │
└────────────────────────────┬────────────────────────────┘
                             │
                             │ [Approach A]
                             │ Specialized Python Script
                             │ (Metadata Parser)
                             ▼
┌─────────────────────────────────────────────────────────┐
│        2. PostgreSQL / PostGIS DB (DDL Schema)          │
└────────────────────────────▲────────────────────────────┘
                             │
                             │ [Approach E]
                             │ Native PostgreSQL FDO Provider
                             │ (Live Read/Write Editing)
                             ▼
┌─────────────────────────────────────────────────────────┐
│               3. AutoCAD Map 3D Client                  │
└─────────────────────────────────────────────────────────┘
```

### Operation of the A + E Combo:
* **Approach A (Initial Generation)**: A Python script parses the SQLite Data Model structure and outputs `schema_postgres.sql`. This prepares the receptacle in PostgreSQL (tables, FDO types, PostGIS geometries, foreign key constraints, and GiST spatial indexes).
* **Approach E (Dynamic Operation)**: AutoCAD Map 3D connects to PostgreSQL via its **native PostgreSQL FDO provider**. Every feature creation, edit, or deletion performed by the CAD technician in Map 3D is reflected **in real-time (Live Read/Write)** inside PostgreSQL.

---

## 4. Conversion Engine Particularities (Approach A)

### Why filter on 4 core tables instead of converting all tables?
The original SQLite export contains around 170 tables, over 150 of which are UI formatting or internal AutoCAD configuration tables (`TB_GN_*`, `TB_SETTINGS`, `TB_SEQUENCE_EMULATION`).

The Python script targets exclusively the **4 master metadata catalogues** identified in Phase 3:

1. **`TB_DICTIONARY`**: Lists domain feature classes (`F_CLASS_NAME`) and object types (`F_CLASS_TYPE`: Point, LineString, Polygon, or Attribute Table).
2. **`TB_ATTRIBUTE`**: Isolates user-defined domain attributes for each class.
3. **`fdo_columns`**: Returns **true FDO logical typing** (`fdo_data_type`: Varchar, Number, Double, Boolean) and length/precision (`fdo_data_length`).
4. **`geometry_columns`**: Provides spatial column names (`GEOM`) and OGC standard geometry types.

---

## 5. Step-by-Step Implementation Protocol

1. **Step 1 — Write Python Converter Script (`convert_autodesk_to_postgis.py`)**:
   Develop the parser reading `TB_DICTIONARY`, `TB_ATTRIBUTE`, `fdo_columns`, `geometry_columns`, and `TB_RELATIONS` to output PostgreSQL DDL.

2. **Step 2 — Validate DDL in PostgreSQL / PostGIS**:
   Execute the generated SQL script in PostgreSQL and verify feature tables, foreign keys, and GiST indexes.

3. **Step 3 — Establish Live Connection in AutoCAD Map 3D**:
   Connect via Map 3D native PostgreSQL FDO connector (`_MAPCONNECT`), load layers, and test live CRUD operations.

4. **Step 4 — Final Documentation and Validation**:
   Record proofs of bidirectional interaction between Map 3D and PostgreSQL to validate Phase 5.
