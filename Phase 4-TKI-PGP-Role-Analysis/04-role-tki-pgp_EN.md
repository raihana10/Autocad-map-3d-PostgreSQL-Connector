# Phase 4 — Role of TKI PGP in Autodesk Architecture

> Legend (identical to project README):
> - **[DOCUMENTED]** = information confirmed by an official Autodesk or TKI source.
> - **[HYPOTHESIS]** = reasonable deduction, unconfirmed by an official source.
> - **[TO VERIFY]** = missing information requiring testing / confirmation from advisor or Autodesk support.
>
> Sources are numbered `[n]` and listed in the Annex at the end of the document.

---

## 1. Presentation of TKI PGP

**TKI PGP** stands for **PostgreSQL Provider**. It is connectivity software developed by **TKI Software / TKI Chemnitz**, intended to enable **Autodesk Industry Models (*Fachschalen*)** to use a **PostgreSQL** database rather than Oracle or SQL Server. Official documentation describes it as the **"effective connector"** between AutoCAD Map 3D and PostgreSQL **[DOCUMENTED] [1]**.

Technically, PGP is:
- A **provider** in the functional sense, allowing an Autodesk client application to work with PostgreSQL following *Fachschalen* domain logic **[DOCUMENTED] [1]**;
- An **application connector**, with administration and data exchange capabilities, rather than a simple database driver **[DOCUMENTED] [3]**;
- A **commercial, versioned product**, requiring an active license on a network license server, with strict version compatibility requirements with AutoCAD Map 3D **[DOCUMENTED] [8]**.

The product is published by **TKI**, referred to on official sites and help portals as either **TKI Software** or **TKI Chemnitz** **[DOCUMENTED] [5]**. The TKI Help Center contains a dedicated section for PGP, confirming it is an official product rather than a community plugin **[DOCUMENTED] [7]**.

Its primary function is to allow Autodesk *Fachschalen* to operate on PostgreSQL instead of natively supported DBMSs (Oracle, SQL Server) **[DOCUMENTED] [4]**. Documentation indicates it supports:
- **Infrastructure Administrator** features **[DOCUMENTED] [1]**;
- **PostgreSQL dump import/export** **[DOCUMENTED] [6]**;
- Map 3D **SQL sheet** **[DOCUMENTED] [3]**.

---

## 2. Functional Analysis in Autodesk Architecture

TKI PGP inserts into the Autodesk architecture as a **specialized link layer** between Autodesk Industry Models / *Fachschalen* and a PostgreSQL database. It does not merely open a database connection; it adapts the operation of the Autodesk model to the PostgreSQL environment **[DOCUMENTED] [2]**.

In this architecture, PGP acts as an intermediary between three levels:
1. **The Autodesk Application** — AutoCAD Map 3D and Infrastructure Administrator.
2. **The Autodesk Business Logic** — *Fachschalen*, their objects, attributes, and administrative workflows.
3. **The PostgreSQL RDBMS** — storing data and ensuring persistence.

PGP maps Autodesk ecosystem expectations to PostgreSQL capabilities **[DOCUMENTED] [1]**.

### Functional Summary

PGP can be understood as a tool that:
- Connects Autodesk *Fachschalen* to PostgreSQL **[DOCUMENTED] [1]**;
- Preserves administrative workflows used in the Autodesk environment **[DOCUMENTED] [2]**;
- Facilitates data exchange via database dumps **[DOCUMENTED] [6]**;
- Enables operational usage via SQL sheet **[DOCUMENTED] [1]**;
- Reduces friction when transitioning to PostgreSQL **[DOCUMENTED] [1]**.

This positions it as a **functional pivot**: PGP replaces neither Autodesk nor PostgreSQL; it renders both compatible within a specific domain framework **[DOCUMENTED] [1]**.

---

## 3. Comparison: Oracle / SQL Server / TKI PGP

| Feature / Criteria | Oracle (Native) | SQL Server (Native) | TKI PGP (PostgreSQL) |
|---|---|---|---|
| Official Autodesk Database Industry Model Support | Yes **[DOCUMENTED]** | Yes **[DOCUMENTED]** | Non-native — via 3rd-party connector **[DOCUMENTED] [1]** |
| Publisher | Oracle Corporation | Microsoft | TKI Software / TKI Chemnitz **[DOCUMENTED] [5]** |
| License Model | Commercial (Oracle license) | Commercial (SQL Server license) | Commercial — PGP license on server, **on top of** free PostgreSQL/PostGIS **[DOCUMENTED] [8]** |
| Infrastructure Administrator Integration | Native | Native | Preserves Infrastructure Administrator features **[DOCUMENTED] [1]** |
| Import / Export | Native Oracle tools | Native SQL Server tools | PostgreSQL dump import/export supported by PGP **[DOCUMENTED] [6]** |
| Map 3D SQL Sheet | Natively supported | Natively supported | Supported via PGP **[DOCUMENTED] [3]** |
| Total Cost (DBMS + Connector) | High (DBMS license) | High (DBMS license) | PGP License + Free PostgreSQL/PostGIS — key cost argument by TKI **[DOCUMENTED] [2]** |
| Vendor Lock-in | No | No | Yes — dependence on TKI for connector **[DOCUMENTED] [8]** |
| Internal Schema Mapping Mechanism | Documented by Autodesk | Documented by Autodesk | Not publicly documented **[TO VERIFY]** |

---

## 4. Summary Table — Documented / Hypothesis / To Verify

| # | Item | Status | Source / Note |
|---|---|---|---|
| 1 | PGP is described as the "effective connector" between Map 3D and PostgreSQL | **[DOCUMENTED]** | [1] |
| 2 | PGP supports Infrastructure Administrator features | **[DOCUMENTED]** | [1] [2] |
| 3 | PGP manages PostgreSQL dump import/export | **[DOCUMENTED]** | [6] |
| 4 | PGP supports Map 3D SQL sheet | **[DOCUMENTED]** | [1] [3] |
| 5 | PGP requires a license server activation | **[DOCUMENTED]** | [8] |
| 6 | PGP is compatible only with specific Map 3D versions | **[DOCUMENTED]** | [7] [8] |
| 7 | Vendor is named TKI Software or TKI Chemnitz | **[DOCUMENTED]** | [3] [4] [5] |
| 8 | Cost saving argument (avoiding Oracle/SQL Server) | **[DOCUMENTED]** | [2] |
| 9 | TKI PGP is distinct from TKI NET (complete FTTx solution) | **[DOCUMENTED]** | README §1.3 |
| 10 | Does PGP create a brand new schema or replicate Oracle structure? | **[TO VERIFY]** | Open question #2 in README |
| 11 | Does PGP rely on native Map 3D PostgreSQL FDO connector? | **[HYPOTHESIS]** | Likely, but unconfirmed |
| 12 | Does PGP handle business rules & Form Designer? | **[TO VERIFY]** | Open question #7 in README |

---

## 5. Annex — Consulted Sources

| Ref. | Description | URL |
|---|---|---|
| [1] | TKI Help Center — Introduction PostgreSQL Provider (EN) | https://help.tki-chemnitz.de/hc/en-gb/articles/360015894560-Introduction-PostgreSQL-provider |
| [2] | TKI Help Center — Einführung PostgreSQL Provider (DE) | https://help.tki-chemnitz.de/hc/de/articles/360015894560-Einführung-PostgreSQL-Provider |
| [3] | TKI Chemnitz — PGP Product Page (EN) | https://www.tki-chemnitz.com/software/products/pgp.html |
| [4] | TKI Chemnitz — PGP Product Page (DE) | https://www.tki-chemnitz.de/de/software/produkte/pgp.html |
| [5] | TKI Net — PGP Product Page | https://www.tki-net.com/products/pgp.html |
| [6] | TKI Help Center — PostgreSQL dump import/export | https://help.tki-chemnitz.de/hc/en-gb/articles/360015674100-Importing-and-Exporting-PostgreSQL-database-dump |
| [7] | TKI Help Center — PGP Section | https://help.tki-chemnitz.de/hc/en-gb/sections/360004497540-PostgreSQL-Provider-PGP |
| [8] | TKI Help Center — Licensing Information | https://help.tki-chemnitz.de/hc/en-gb/articles/360015914979-General-Information-about-TKI-Licensing |
