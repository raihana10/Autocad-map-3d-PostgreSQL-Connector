# 03 — Analysis and Reverse Engineering of Autodesk Data Model

> **Phase 3 of the Research Project** — Understanding the internal operation of Autodesk Industry Models in order to develop an automated converter from Autodesk Data Model → PostgreSQL/PostGIS.

---

## Table of Contents

1. [Objective of the Phase](#1-objective-of-the-phase)
2. [Principle of Reverse Engineering](#2-principle-of-reverse-engineering)
3. [Tools Used](#3-tools-used)
4. [Complete Test Campaign](#4-complete-test-campaign)
5. [Tracking Table](#5-tracking-table)
6. [Final Analysis](#6-final-analysis)
7. [Conclusion](#7-conclusion)

---

## 1. Objective of the Phase

### 1.1 Why this Phase is the Most Critical of the Project

The overall project aims to build a tool capable of reading an **Autodesk Data Model** (as defined in **Autodesk Infrastructure Administrator**) and automatically generating a strictly equivalent **PostgreSQL/PostGIS schema**, without depending on Oracle or SQL Server as intermediate storage engines.

Such a converter can only be designed properly if we understand **exactly** how Autodesk translates, internally, the concepts manipulated in the graphical user interface (object classes, attributes, domains, relationships, graphical representations, etc.) into concrete relational structures. Phase 3 is therefore the **technical foundation** for the rest of the project:

- Any misinterpretation at this stage will mechanically impact the PostgreSQL/PostGIS schema generation phase.
- The conceptual mapping constructed here ("concept in Data Model = table(s)/column(s) in SQLite") will serve as the **functional specification** for the future conversion engine.
- Without this phase, all subsequent development would rely on unverified assumptions, which is unacceptable in a rigorous research context.

> **Note**
> This phase aims to produce **verified and documented knowledge**, not code. Code will come in a later phase once the internal model is stabilized.

### 1.2 Two Representations of the Same Object

It is essential to distinguish **two layers** describing the same Data Model:

1. **The conceptual / application layer**: The Data Model as **visible and configurable** in Infrastructure Administrator (class hierarchy, properties, domains, relationships, representation styles, etc.). This is the view intended for domain users.
2. **The physical / storage layer**: The **actual representation** of this Data Model, persisted in an **SQLite** file (`.sqlite`). This is the layer of interest for our conversion engine.

```
┌──────────────────────────────────────┐
│      Infrastructure Administrator    │
│  (conceptual view / UI interface)    │
│                                      │
│   Class "Valve"                      │
│     ├─ Attribute "Diameter" (Double) │
│     ├─ Attribute "Material" (Domain) │
│     └─ Geometry (Point)              │
└──────────────────┬───────────────────┘
                   │ internal persistence
                   ▼
┌──────────────────────────────────────┐
│          SQLite File (engine)        │
│    (physical / relational view)      │
│                                      │
│  Table TB_DICTIONARY                 │
│  Table TB_ATTRIBUTE                  │
│  Table TB_DOMAIN                     │
│  Table geometry_columns              │
│  ...                                 │
└──────────────────────────────────────┘
```

The objective of this phase is to build, **empirically and with evidence**, the mapping table between these two layers.

---

## 2. Principle of Reverse Engineering

### 2.1 General Methodology

The methodology adopted is **controlled differential analysis** reverse engineering. The principle is simple: observe the effect, in the SQLite file, of **a single controlled modification** performed in Infrastructure Administrator.

### 2.2 Absolute Rule: One Single Modification at a Time

**Never modify multiple parameters simultaneously.**

If two parameters are modified at the same time (e.g. adding an attribute *and* changing one of its properties), it becomes impossible to know which modification caused which change in the SQLite file.

### 2.3 Operational Cycle

Each test strictly follows this cycle:

```
   ┌──────────────────────────┐
   │    Single Modification   │
   └────────────┬─────────────┘
                ▼
   ┌──────────────────────────┐
   │           Save           │
   └────────────┬─────────────┘
                ▼
   ┌──────────────────────────┐
   │    Extract .sql files    │
   └────────────┬─────────────┘
                ▼
┌─────────────────────────────────────┐
│  Run Python Comparison Script to    │
│    generate diff report             │
└───────────────┬─────────────────────┘
                ▼
   ┌──────────────────────────┐
   │        Observation       │
   └────────────┬─────────────┘
                ▼
   ┌──────────────────────────┐
   │         Deduction        │
   └──────────────────────────┘
```

1. **Single Modification**: Perform one precise action in Infrastructure Administrator (e.g., adding an attribute).
2. **Save**: Save the Data Model to force persistence to the underlying SQLite file.
3. **Extract .sql files**: Export schema and data dump.
4. **Run Comparison Script**: Compare the current state with the previous state (before modification).
5. **Observation**: Note precisely which tables, columns, and values changed.
6. **Deduction**: Formulate a hypothesis on the role of each table/column affected.

---

## 3. Tools Used

| Tool | Role |
|---|---|
| **Infrastructure Administrator** | Autodesk UI to create, modify, and manage the Data Model. Generates the changes to observe. |
| **DB Browser for SQLite** | Graphical tool to browse and inspect SQLite schema and data visually. |
| **SQL Sheet** | SQL query interface to execute targeted `SELECT` queries against SQLite tables. |
| **sqlite3 CLI** | Command-line tool to automate schema export (`.schema`) and data dump (`.dump`). |
| **Python Comparison Script** | Python script (`compare_sqlite.py`) to automatically highlight differences between "before" and "after" SQL dumps. |

---

## 4. Complete Test Campaign

### Test 0 — Initial State (Baseline)
- **Goal**: Establish a baseline reference before any modification.
- **Modification**: None.
- **Observation**: 170 tables generated by default (system tables `TB_*`, spatial metadata `geometry_columns`, `spatial_ref_sys`).
- **Conclusion**: Infrastructure Administrator generates a rich set of default system tables upon initialization.

### Test 1 — Adding a Non-Geometric Class (`TEST_CLASSE_01`)
- **Goal**: Identify tables responsible for storing class definitions.
- **Modification**: Created non-geometric class `TEST_CLASSE_01`.
- **Observation**: Created physical SQLite table `TEST_CLASSE_01` with 5 auto-generated triggers (`_AD_FID`, `_AI_FID`, `_AU_FID`, `_BI_FID`, `_BU_FID`).
- **Key Tables Modified**: `TB_DICTIONARY` (+1 row), `TB_ATTRIBUTE` (+1 row for `FID`), `fdo_columns` (+1 row for `FID`), `TB_RULE_BASE` (+6 rows).
- **Conclusion**: `TB_DICTIONARY` is the master class catalogue. Every class creation triggers a physical SQL table creation in the database.

### Test 2 — Adding a Text Attribute (`TEST_ATTRIBUT_01`)
- **Goal**: Identify table storing class attributes.
- **Modification**: Added text attribute `TEST_ATTRIBUT_01` (max length 10) to `TEST_CLASSE_01`.
- **Observation**: Executed `ALTER TABLE` on `TEST_CLASSE_01` adding column `TEST_ATTRIBUT_01 VARCHAR2(10)`. Registered attribute in `TB_ATTRIBUTE` (`F_CLASS_ID=8`) and `fdo_columns` (`fdo_data_type: 9`, `fdo_data_length: 10`).
- **Conclusion**: `TB_ATTRIBUTE` is the master attribute catalogue, while `fdo_columns` stores exact FDO data types and length constraints.

### Test 3 — Adding a Numeric Attribute (`TEST_ATTRIBUT_02`)
- **Goal**: Identify encoding of numeric data types.
- **Modification**: Added numeric attribute `TEST_ATTRIBUT_02` (precision 10).
- **Observation**: `ALTER TABLE` added `TEST_ATTRIBUT_02 INTEGER(10)`. Registered in `fdo_columns` with `fdo_data_type: 7` (Number), `f_column_desc: 'Number'`.
- **Conclusion**: Data types are stored directly in SQL DDL and mapped to FDO type codes (`type 7` for Number vs `type 9` for Varchar).

### Test 4 — Default Value (`TEST_ATTRIBUT_03`)
- **Goal**: Locate default value storage.
- **Modification**: Set default value `0` on attribute `TEST_ATTRIBUT_03`.
- **Observation**: Column created with explicit DDL clause `TEST_ATTRIBUT_03 (INTEGER(10), DEFAULT 0)`.
- **Conclusion**: Infrastructure Administrator delegates default values directly to the underlying SQL engine DDL (`DEFAULT 0`).

### Test 5 — Mandatory Attribute (`TEST_ATTRIBUT_05`)
- **Goal**: Locate mandatory constraint storage.
- **Modification**: Checked "Mandatory" option on `TEST_ATTRIBUT_05`.
- **Observation**: Column created with DDL clause `NOT NULL`.
- **Conclusion**: Mandatory constraints rely natively on the SQL `NOT NULL` clause.

### Test 7 — New Point Feature Class (`TEST_CLASSE_GEO_01`)
- **Goal**: Identify structural differences between non-geometric and geometric classes.
- **Modification**: Created point feature class `TEST_CLASSE_GEO_01`.
- **Observation**: Registered in `geometry_columns` (`geometry_type: 1` Point). `TB_DICTIONARY` set `F_CLASS_TYPE: P`. Added automatic spatial columns (`Z`, `ORIENTATION`, `QUALITY`, `GEOM`) in physical table and `TB_ATTRIBUTE`.
- **Conclusion**: Follows OGC GIS standards (`geometry_columns`). Point classes inherit dedicated spatial columns upon creation.

### Test 8 — New Line Feature Class (`TEST_CLASS_GEO_02`)
- **Goal**: Identify line geometry storage and automatic attributes.
- **Modification**: Created line feature class `TEST_CLASS_GEO_02`.
- **Observation**: `geometry_columns` set `geometry_type: 2` (LineString). `TB_DICTIONARY` set `F_CLASS_TYPE: L`. Automatically added calculated attribute `LENGTH` (`fdo_data_type: 3`).
- **Conclusion**: Geometry types are designated by `F_CLASS_TYPE` ('L' vs 'P') and OGC `geometry_type` (2 vs 1). Line classes automatically include an analytical `LENGTH` column.

### Test 9 — Relationship Between Two Classes
- **Goal**: Identify relationship representation.
- **Modification**: Created 1-N relationship between `TEST_CLASSE_01` and `TEST_CLASSE_GEO_01`.
- **Observation**: Registered parent/child row in `TB_RELATIONS`. Added physical foreign key column `TEST_ATTRIBUT_09` in child table with dedicated index (`TEST_CLASSE_01_IX1`).
- **Conclusion**: Relationships instantiate a physical FK column in the child table and log metadata in `TB_RELATIONS`.

### Test 10.1 & 10.2 — Value Domain Creation & Attachment
- **Goal**: Locate domain value storage and attribute binding.
- **Modification**: Created domain `TEST_DOMAINE_10` (values: Acier, PVC, Fonte) and attached attribute `TEST_ATTRIBUT_10` to it.
- **Observation**: Created domain catalogue row in `TB_DOMAIN` and dedicated values table `TEST_DOMAINE_10_TBD`. Attachment created FK column in child table and row in `TB_RELATIONS` pointing to `TEST_DOMAINE_10_TBD` as parent table.
- **Conclusion**: Domains use dedicated value tables (`_TBD`) and are attached via the same `TB_RELATIONS` mechanism as class-to-class relationships.

### Test 11 — Domain Modification
- **Goal**: Observe effect of adding a domain value.
- **Modification**: Added value `Cuivre` to `TEST_DOMAINE_10`.
- **Observation**: Simple `INSERT` into `TEST_DOMAINE_10_TBD`.
- **Conclusion**: Domain modifications are purely incremental row inserts.

### Test 12 — Class Inheritance
- **Goal**: Locate class inheritance mechanism.
- **Modification**: Created child class `TEST_CLASSE_FILLE_01` inheriting from `TEST_CLASSE_01`.
- **Observation**: Physical table `TEST_CLASSE_FILLE_01` physically copied all parent columns, attributes, relations, and domain bindings. Logged in `TB_DICTIONARY` via `MODEL_F_CLASS_ID`.
- **Conclusion**: Autodesk uses **full physical inheritance**: child tables copy all parent columns and re-register inherited attributes/relations.

### Test 16 — Class Renaming
- **Goal**: Verify impact of renaming a class.
- **Modification**: Renamed `TEST_CLASSE_01` to `TEST_CLASSE_01_RENAME`.
- **Observation**: Updated `TB_DICTIONARY.CAPTION` and `FEATURE_REPRESENTATION`. Physical table name and technical ID (`F_CLASS_ID`) remained unchanged.
- **Conclusion**: Renaming is cosmetic UI metadata; physical table names and IDs are permanent.

### Test 17 & 18 — Class & Attribute Deletion
- **Goal**: Verify hard vs soft deletion.
- **Modification**: Deleted class `TEST_CLASSE_FILLE_01` (Test 17) and attribute `TEST_ATTRIBUT_01` (Test 18).
- **Observation**: Executed `DROP TABLE` and `ALTER TABLE DROP COLUMN`. Cascade deleted associated catalogue rows from `TB_DICTIONARY`, `TB_ATTRIBUTE`, `fdo_columns`, `TB_RELATIONS`.
- **Conclusion**: Hard cascade deletion is applied across all catalogues.

---

## 5. Tracking Table Summary

| Concept | Primary SQLite Master Table | Key Columns / Mechanism |
|---|---|---|
| **Class** | `TB_DICTIONARY` | `F_CLASS_NAME`, `F_CLASS_TYPE` ('P', 'L', 'N'), `F_CLASS_ID` |
| **Attribute** | `TB_ATTRIBUTE` & `fdo_columns` | `F_CLASS_ID`, `fdo_data_type`, `fdo_data_length`, `fdo_data_precision` |
| **Geometry** | `geometry_columns` | `f_table_name`, `f_geometry_column`, `geometry_type` (1=Point, 2=Line) |
| **Domain** | `TB_DOMAIN` & `<DOMAIN>_TBD` | Dedicated `<DOMAIN>_TBD` value table |
| **Relationship** | `TB_RELATIONS` | `PARENT_TABLE_NAME`, `CHILD_TABLE_NAME`, FK column in child table |
| **Inheritance** | `TB_DICTIONARY` | `MODEL_F_CLASS_ID` linking child to parent class |

---

## 6. Final Analysis & Next Steps

This reverse-engineering phase successfully unmasked the internal structure of Autodesk Infrastructure Administrator:
- The converter only needs to parse **4 core catalogues**: `TB_DICTIONARY`, `TB_ATTRIBUTE`, `fdo_columns`, and `geometry_columns` (along with `TB_RELATIONS` and `TB_DOMAIN`).
- All data models map cleanly to standard PostgreSQL/PostGIS constructs (tables, PostGIS geometries, foreign keys, and triggers).
- This opens the way for developing the automated SQLite → PostgreSQL DDL converter script in Phase 5.
