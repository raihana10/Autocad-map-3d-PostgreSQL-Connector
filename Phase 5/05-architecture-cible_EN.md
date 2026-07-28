# Phase 5 — Target Architecture & Alternative Solution

> **Phase 5 of the Project** — Definition and justification of the alternative solution for converting and utilizing Autodesk Data Models under PostgreSQL/PostGIS.

---

## 1. Phase Objective

The objective of Phase 5 is to define the technical architecture allowing an **Autodesk Infrastructure Administrator Data Model** to be operated with a **PostgreSQL / PostGIS** database, without relying on Oracle, SQL Server, or the paid commercial TKI PGP connector.

The solution must satisfy two core requirements:
1. **DDL Schema Generation**: Faithfully translate the SQLite Data Model structure (classes, attributes, domains, relationships, inheritance) to PostgreSQL/PostGIS.
2. **Real-time Editing**: Enable AutoCAD Map 3D to interact (read and write) directly with the PostgreSQL database with a level of functionality equivalent to TKI PGP.

---

## 2. Summary of Evaluated Architectures

| Approach | Description | Status | Justification |
|---|---|---|---|
| **A. SQL Script Generation (Python)** | Parse SQLite Data Model and automatically generate PostGIS DDL. | **Selected (Step 1)** | Generates exact, controlled relational, spatial, and constraint structure. |
| **B. Periodic ETL Sync** | Batch synchronization script at regular intervals. | **Eliminated** | Does not allow real-time spatial editing required in CAD/GIS workflows. |
| **C. C# / .NET Plugin (Map 3D API)** | Native client extension developed inside Map 3D. | **Eliminated** | High complexity and steep learning curve for internship timeframe. |
| **D. Java Plugin** | Java client plugin. | **Eliminated** | Autodesk ecosystem is .NET-oriented; no official Java API exists for Map 3D. |
| **E. Native PostgreSQL FDO Connector** | Utilizing AutoCAD Map 3D's native PostgreSQL FDO provider. | **Selected (Step 2)** | Reuses Autodesk's native, official data access engine for real-time live editing. |

---

## 3. Selected Architecture: Combination A + E (Generator + Native FDO Connection + Triggers)

The selected architecture combines **Approach A** and **Approach E** enhanced with PostgreSQL database intelligence:

```
┌─────────────────────────────────────────────────────────┐
│              1. Source Data Model (SQLite)              │
└────────────────────────────┬────────────────────────────┘
                             │
                             │ [Approach A]
                             │ Specialized Python Script
                             │ (Parsing 6 Master Metadata Catalogues)
                             ▼
┌─────────────────────────────────────────────────────────┐
│        2. PostgreSQL / PostGIS DB (DDL Schema)          │
│    - Feature Tables & PostGIS Geometries                │
│    - Domain Tables & Foreign Keys (_TBD)                │
│    - Parent-Child Relationships (TB_RELATIONS)          │
│    - PL/pgSQL Triggers (Calculations & Business Rules)  │
└────────────────────────────▲────────────────────────────┘
                             │
                             │ [Approach E]
                             │ Native PostgreSQL FDO Provider
                             │ (Live Read/Write Editing)
                             ▼
┌─────────────────────────────────────────────────────────┐
│               3. AutoCAD Map 3D Client                  │
└────────────────────────────▲────────────────────────────┘
```

---

## 4. Conversion Engine Particularities (Approach A)

### The 6 Master Catalogues Identified in Phase 3

The original SQLite export contains around 170 tables, over 150 of which are UI formatting or internal AutoCAD configuration tables (`TB_GN_*`, `TB_SETTINGS`, `TB_SEQUENCE_EMULATION`).

To cover the complete functional scope of an Industry Model and match TKI PGP, our Python script targets the **6 master metadata catalogues** validated during Phase 3 testing:

1. **`TB_DICTIONARY`**: Lists feature classes (`F_CLASS_NAME`), object types (`F_CLASS_TYPE`: Point, LineString, Polygon, Table), and handles class inheritance (`MODEL_F_CLASS_ID`, validated in Test 12).
2. **`TB_ATTRIBUTE`**: Isolates user-defined domain attributes for each class (validated in Tests 2, 3, 4, 5).
3. **`fdo_columns`**: Returns **true FDO logical typing** (`fdo_data_type`: Varchar, Number, Double, Boolean) and precision/length (`fdo_data_length`).
4. **`geometry_columns`**: Provides spatial column names (`GEOM`) and standard OGC geometry types (validated in Tests 7, 8).
5. **`TB_DOMAIN` + `<DOMAIN>_TBD` Tables**: Stores allowed value lists / enumerations (e.g. material, status) (validated in Tests 10.1, 11).
6. **`TB_RELATIONS`**: Stores inter-class relationships and attribute bindings to domain tables (validated in Tests 9, 10.2).

---

## 5. Handling Business Logic Mechanisms (TKI PGP Equivalence)

Our solution translates every Infrastructure Administrator business mechanism directly into native PostgreSQL database constructs:

### 1. Value Domains (Dropdown Lists)
* **Autodesk Mechanism**: Reference tables `_TBD` (Test 10.1).
* **PostgreSQL Translation**: Creating domain tables in PostgreSQL and adding `FOREIGN KEY` constraints linking feature attributes to domain tables.

### 2. Parent / Child Relationships & Inheritance
* **Autodesk Mechanism**: Table `TB_RELATIONS` (Test 9) and inheritance `MODEL_F_CLASS_ID` (Test 12).
* **PostgreSQL Translation**: Automatic creation of `FK` columns in child tables and copying inherited attributes with `ON DELETE CASCADE` constraints.

### 3. Automatic Calculations & Topological Integrity
* **Autodesk Mechanism**: `TB_RULE_BASE` and application rules.
* **PostgreSQL Translation**: Creating **PL/pgSQL Triggers** in PostgreSQL (e.g. automatic length calculation `ST_Length(geom)` on cable insertion or update).

---

## 6. Step-by-Step Implementation Protocol

1. **Step 1 — Write Python Converter Script (`convert_autodesk_to_postgis.py`)**:
   Develop the script reading `TB_DICTIONARY`, `TB_ATTRIBUTE`, `fdo_columns`, `geometry_columns`, `TB_DOMAIN`, and `TB_RELATIONS` to generate complete PostgreSQL DDL (Tables, Foreign Keys, Triggers).

2. **Step 2 — Validate DDL in PostgreSQL / PostGIS**:
   Execute SQL in PostgreSQL and verify feature tables, domain tables, FK constraints, GiST indexes, and Triggers.

3. **Step 3 — Establish Live Connection in AutoCAD Map 3D**:
   Connect via Map 3D native PostgreSQL FDO connector (`_MAPCONNECT`), load layers, and test live CRUD operations.

4. **Step 4 — Final Documentation and Validation**:
   Record proofs of bidirectional interaction between Map 3D and PostgreSQL to validate Phase 5.
