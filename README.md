# Open-Source Alternative to TKI PGP — Autodesk Industry Model to PostgreSQL/PostGIS

> End-of-year internship project (PFA) aiming to design an open-source alternative to the commercial connector **TKI PGP**, enabling **PostgreSQL/PostGIS** to be used as the storage engine for an Autodesk **Industry Model** (*Fachschale*), instead of Oracle or Microsoft SQL Server.

---

[ Version Française (French Version) ](README_FR.md) | **English Version**

---

## Table of Contents

- [Context](#context)
- [Problem Statement](#problem-statement)
- [Project Objectives](#project-objectives)
- [Architecture](#architecture)
- [Repository Structure](#repository-structure)
- [Technologies Used](#technologies-used)
- [Methodology](#methodology)
- [Limits and Scope](#limits-and-scope)
- [Authors](#authors)
- [License](#license)

---

## Context

**AutoCAD Map 3D**, combined with **Autodesk Infrastructure Administrator**, allows creating **Industry Models** (called *Fachschalen*): domain data models dedicated to managing infrastructure (water, electricity, gas, telecommunications networks, etc.).

Officially, a database-based Industry Model can only be created on **Oracle** or **Microsoft SQL Server**. **PostgreSQL** is not natively offered, even though it is a free, open-source relational database management system with **PostGIS**, a mature spatial extension.

To bridge this gap, **TKI** commercializes a connector, **TKI PGP (PostgreSQL Provider)**, which allows using PostgreSQL/PostGIS as the storage engine for an Industry Model. However, this connector is a **commercial and licensed** product.

## Problem Statement

How to allow an Autodesk Industry Model to be stored and used in PostgreSQL/PostGIS, with a functional level comparable to TKI PGP (schema creation, reading, creating, updating, and deleting objects from AutoCAD Map 3D), **without relying on a commercial product**?

## Project Objectives

1. Understand in detail the internal operation of the Autodesk **Data Model** (how object classes, attributes, geometries, domains, and relationships are translated into relational structures).
2. Understand the exact functional scope of **TKI PGP**, based on its public documentation and observable behavior, without reverse-engineering its code.
3. Design and compare several possible architectures for an alternative solution.
4. Develop a tool capable of automatically generating an equivalent **PostgreSQL/PostGIS** schema from an Autodesk Data Model.
5. Validate the solution through an end-to-end scenario in AutoCAD Map 3D.

## Architecture

### Official Autodesk Architecture (Reference)

```
Infrastructure Administrator ──► Data Model ──► Industry Model (Fachschale)
                                                        │
                                           ┌─────────────┴─────────────┐
                                           ▼                           ▼
                                        Oracle                    SQL Server
                                           │                           │
                                           └─────────────┬─────────────┘
                                                         ▼
                                                  AutoCAD Map 3D
```

### Project Target Architecture

```
Infrastructure Administrator ──► Data Model (SQLite export)
                                           │
                                           ▼
                         PostgreSQL/PostGIS Schema Generator
                                   [Python Script]
                                           │
                                           ▼
                                 PostgreSQL + PostGIS
                                           │
                                           ▼
                                  AutoCAD Map 3D
                            [Native FDO PostgreSQL Provider]
```

## Repository Structure

```
.
├── Phase 1-FDO-Provider-Analysis/
│   ├── 01-autodesk-architecture.md      # Phase 1 — Observed Autodesk architecture (FR)
│   └── 01-autodesk-architecture_EN.md   # Phase 1 — Observed Autodesk architecture (EN)
├── Phase 2-PostGIS-Direct-Connection/
│   ├── 02-postgis-postgresql.md         # Phase 2 — PostgreSQL/PostGIS and FDO connector (FR)
│   └── 02-postgis-postgresql_EN.md      # Phase 2 — PostgreSQL/PostGIS and FDO connector (EN)
├── Phase 3-SQLite-Reverse-Engineering/
│   ├── 03-data-model-analyse.md         # Phase 3 — Data Model analysis & reverse engineering (FR)
│   ├── 03-data-model-analyse_EN.md      # Phase 3 — Data Model analysis & reverse engineering (EN)
│   ├── compare_sqlite.py                # Automated comparison script for SQLite exports
│   ├── rapport_test1_vs_test2.md        # Example comparison report
│   ├── Test0/ ... Test18/               # Differential test campaign (schema + SQL dump per test)
│   └── PFA-Phase 3.xlsx                 # Synthesis spreadsheet
├── Phase 4-TKI-PGP-Role-Analysis/
│   ├── 04-role-tki-pgp.md               # Phase 4 — Role of TKI PGP in Autodesk architecture (FR)
│   └── 04-role-tki-pgp_EN.md            # Phase 4 — Role of TKI PGP in Autodesk architecture (EN)
├── Phase 5-Target-Architecture/
│   ├── 05-architecture-cible.md         # Phase 5 — Target architecture & alternative solution (FR)
│   └── 05-architecture-cible_EN.md      # Phase 5 — Target architecture & alternative solution (EN)
├── Phase 6-Implementation-Testing/
│   ├── scripts/
│   │   ├── convert_autodesk_to_postgis.py   # Automated SQLite to PostgreSQL DDL converter
│   │   └── watch_and_sync.py                # Live watcher and auto-sync service
│   ├── tests/
│   │   ├── conftest.py                      # Pytest fixtures and shared configuration
│   │   ├── test_converter.py                # Unit tests for the DDL converter
│   │   ├── test_inheritance.py              # Unit tests for table inheritance logic
│   │   └── test_watcher.py                  # Unit tests for the watcher service
│   └── requirements-dev.txt                 # Development and testing dependencies
├── README_FR.md                         # Main README (French)
└── README.md                            # Main README (English)
```

## Technologies Used

- **AutoCAD Map 3D** / **Autodesk Infrastructure Administrator** — Reference environment
- **PostgreSQL** / **PostGIS** — Target database
- **SQLite** — Intermediate Data Model storage format, analyzed in Phase 3
- **Python** — Analysis, comparison, and DDL generation scripts (`compare_sqlite.py`, `convert_autodesk_to_postgis.py`)
- **Git** — Version control

## Methodology

Understanding the Autodesk Data Model relies on a **controlled differential reverse-engineering** method: each test consists of performing **a single modification** in Infrastructure Administrator (adding a class, attribute, relationship, etc.), then automatically comparing the state of the SQLite schema before and after to deduce, through reproducible observation, the mapping logic between the conceptual model and its physical representation.

## Scope and Limits

- The project focuses exclusively on **TKI PGP**; the **TKI NET** industry solution is outside the scope of the internship.
- No reverse-engineering of TKI PGP's code is performed: the analysis is based solely on public documentation and observable product behavior.
- Development relies on test Data Models created specifically for this project, not on production data.

## Authors

Project carried out as part of an end-of-year internship (PFA), in a team of two.

## License

© 2026 — All rights reserved.

This project was carried out as part of an end-of-year internship. Its intellectual property status is not yet permanently settled. No license to use, copy, modify, or redistribute is granted at this stage. The code is publicly visible for demonstration/portfolio purposes only.
