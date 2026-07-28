# 02 — PostgreSQL / PostGIS

> Phase 2 of the work plan. The Autodesk aspect (Infrastructure Administrator, Industry Model choice, Enterprise menu) is already covered in deliverable **`01-autodesk-architecture.md`** and is not repeated here.

Definitions:
- **PostgreSQL**: Robust, extensible open-source relational database management system used to store and manage structured data.
- **PostGIS**: Spatial extension for PostgreSQL adding geometry types, GIS functions, and spatial indexes to handle geographic data.

## 1. Installation and Verification

Test database `map3d_test` created under PostgreSQL 18, with the PostGIS extension installed on it.

<img src="./Screenshot 2026-07-10 135323.png" alt="Creation of map3d_test database" />
*Creation of the `map3d_test` database.*

```sql
CREATE EXTENSION postgis;
```

<img src="./Screenshot 2026-07-10 135519.png" alt="PostGIS Extension installed" />

```sql
SELECT PostGIS_Version();
```

<img src="./Screenshot 2026-07-10 135533.png" alt="PostGIS_Version Result" />
*Result: PostGIS 3.6, GEOS/PROJ active.*

**[DONE]**: PostgreSQL/PostGIS environment operational.

## 2. Dedicated Schema

A `fibre` schema was created to isolate project tables (fiber optic network / FTTx use case).

```sql
CREATE SCHEMA fibre;
```

<img src="./Screenshot 2026-07-10 135803.png" alt="Creation of fibre schema" />

Verification:

```sql
SELECT schema_name FROM information_schema.schemata;
```

<img src="./Screenshot 2026-07-10 135838.png" alt="List of schemas" />

*The `public` and `fibre` schemas are present.*

## 3. Demonstration SQL Script

Standalone script provided separately: **[`demo_schema_fibre.sql`](demo_schema_fibre.sql)**.

It creates four spatial tables in the `fibre` schema (`chambre` as POINT, `poteau` as POINT, `cable` as LINESTRING with foreign keys to `chambre`, `zone_desserte` as POLYGON), with GiST indexes and test queries (cable length, spatial inclusion).

Objective: practice manual spatial modeling (geometry types, PK/FK, indexes) before attempting to generate it automatically from an Autodesk Data Model in Phase 3.

## 4. Map 3D Native FDO PostgreSQL Connector

**[DONE]** — Map 3D's native "Bring in features from PostgreSQL/PostGIS" connector was successfully tested: connection to `map3d_test` database, displaying and editing objects from the `fibre` schema confirmed functional in bidirectional read/write mode.

### 4.1 Connecting to the Database

Connection established via **Data Connect → Add PostgreSQL Connection**, authenticating against the `map3d_test` database (`localhost:5432` service, user `postgres`).

<img src="./Screenshot 2026-07-13 150450.png" alt="PostgreSQL connection via Map 3D" />
*PostgreSQL connection window — entering credentials for `map3d_test`.*

Selecting the `map3d_test` datastore from the list of available databases on the instance.

<img src="./Screenshot 2026-07-13 150502.png" alt="PostgreSQL datastore selection" />
*Choosing data store among detected databases (`map3d_test`, `postgis_36_sample`, `postgres`).*

### 4.2 Adding Layers to the Drawing

Once connected, the `fibre` schema hierarchy appears with the spatial tables created in section 3 (`cable`, `chambre`, `commune`, `conduit`, `zone`), each recognized with its coordinate reference system (LL84).

<img src="./Screenshot 2026-07-13 150525.png" alt="Adding layers to drawing" />
*“Add Data to Map” panel — selecting `fibre` schema layers to add to drawing.*

The `chambre` table was added to the drawing (`Add to Map`), the two existing records display correctly with their attributes (`id`, `nom`, `type`) in the associated data table.

<img src="./Screenshot 2026-07-13 162158.png" alt="Displaying chambre in drawing" />
*`chambre` object displayed in drawing, Map 3D data table synchronized (CH-001, CH-002).*

### 4.3 Edit Test (Bidirectional Editing)

The name of record `id=2` was modified in Map 3D (`CH-002` → confirmed, `CH-01` renamed on source side).

Direct verification in pgAdmin, query `SELECT * FROM fibre.chambre;`: edits made from Map 3D are reflected in PostgreSQL, with geometry (`geom`) intact.

<img src="./Screenshot 2026-07-13 162636.png" alt="Database verification via pgAdmin" />
*Database verification via pgAdmin — attributes modified in Map 3D are persisted in `fibre.chambre`.*

Selecting object `CH-002` in the drawing confirms visual correspondence with the database record.

<img src="./Screenshot 2026-07-13 162654.png" alt="Selection of modified object" />
*Selecting object `CH-002` in drawing — confirmed match with database.*

### 4.4 Findings

The native FDO connector works well for basic CRUD display and editing (reading, updating, immediate synchronization with PostgreSQL, with no explicit visible commit step).

**Remains to be tested** to settle open questions (domain classes / rules):
- Behavior when encountering a violated CHECK constraint or foreign key
- Value domain management / dropdown lists
- Representation of relationships or inheritance between classes

## 5. Synthesis

| Planned | Status |
|---|---|
| Install PostgreSQL + PostGIS | **[DONE]** |
| Create test database/schema with `geometry` tables | **[DONE]** |
| Practice POINT / LINESTRING / POLYGON | **[DONE]** (MULTIPOLYGON untested) |
| Schemas, PK/FK, GiST indexes | **[DONE]** (views untested) |
| Test Map 3D PostgreSQL FDO connector (display/edit) | **[DONE]** |

## 6. Technical Conclusion of Phase 2

The goal of this phase was to determine whether Autodesk AutoCAD Map 3D could communicate directly with a PostgreSQL/PostGIS database without using the commercial TKI PGP connector.

Experiments show that this connection is indeed possible thanks to the **OSGeo FDO Provider for PostgreSQL/PostGIS** built into AutoCAD Map 3D.

The following features were validated:
- Connection to a PostgreSQL/PostGIS database;
- Display of spatial tables as map layers;
- Geometry reading (POINT, LINESTRING, POLYGON);
- Attribute modification;
- Immediate synchronization of edits with PostgreSQL;
- Direct spatial table usage without intermediate conversion.

These results demonstrate that AutoCAD Map 3D natively works with PostgreSQL/PostGIS for standard GIS data.

## What the FDO Connector Actually Does

The FDO provider acts purely as a connector between AutoCAD Map 3D and the database.

Its role consists of:
- Opening a connection to PostgreSQL;
- Reading tables containing geometries;
- Displaying these features in the drawing;
- Enabling creation, modification, and deletion of features;
- Automatically saving modifications to PostgreSQL.

In this configuration, each PostgreSQL table is simply interpreted as a map layer.

For instance:
```
PostgreSQL Table
----------------
fibre.chambre
```
is displayed in AutoCAD Map 3D as a layer containing POINT features.

However, the FDO provider possesses no knowledge of the domain logic represented by these features. For FDO, the `chambre` table is simply an SQL table with some attributes and a `geometry` column.

## What FDO Does Not Provide

Experiments also show that the FDO connector does not automatically transform a PostgreSQL database into a true Industry Model (*Fachschale*).

Specifically, it does not provide:
- Industry Model domain classes;
- Business rules;
- Specialized forms;
- Business relationships between objects;
- Metadata specific to Autodesk Industry Models;
- Specific behaviors used in Infrastructure Administrator.

In other words, FDO only provides access to geographic data. It does not provide the domain layer that characterizes a *Fachschale*.

## Position of TKI PGP

From the experiments conducted, TKI PGP does not serve solely to connect PostgreSQL to AutoCAD Map 3D (which FDO already does).

The added value of TKI PGP lies at a higher level: allowing the use of an **Autodesk Industry Model** on PostgreSQL by bringing the elements that go beyond simple reading of spatial tables (metadata management, Industry Model integration).

## Difference Between FDO and an Industry Model

```
                 FDO PostgreSQL
                 --------------

PostgreSQL
      │
      ▼
Table Reading
      │
      ▼
Layer Display
      │
      ▼
Feature Editing
      │
      ▼
Saving to PostgreSQL


==============================


             Industry Model (Fachschale)

Domain Definition
      │
      ▼
Domain Classes
      │
      ▼
Relationships Between Objects
      │
      ▼
Business Rules
      │
      ▼
Specialized Forms
      │
      ▼
Data Model
      │
      ▼
PostgreSQL
      │
      ▼
AutoCAD Map 3D
```

## Conclusion

Experiments in this phase conclude that PostgreSQL/PostGIS is fully compatible with AutoCAD Map 3D for spatial data storage and editing via the native FDO provider.

However, these tests also demonstrate that a simple FDO connection is insufficient to replicate the complete behavior of an Autodesk *Fachschale*.

The next phase of the project will focus on understanding how an **Industry Model** is defined, transformed into a **Data Model**, what metadata Autodesk generates, and what additional capabilities TKI PGP brings to enable a complete *Fachschale* on PostgreSQL.
