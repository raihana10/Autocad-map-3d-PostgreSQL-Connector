#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
PROJECT : Autocad-map-3d-PostgreSQL-Connector
MODULE  : Autodesk Data Model (SQLite) -> PostgreSQL / PostGIS Converter
PHASE   : Phase 5 -- Target Architecture (Approach A) -- V2
===============================================================================

DESCRIPTION:
This script acts as the core DDL translation engine. It parses an Autodesk 
Industry Model SQLite file exported from Autodesk Infrastructure Administrator,
analyzes the 6 core Autodesk metadata catalog tables identified during Phase 3
(TB_DICTIONARY, TB_ATTRIBUTE, fdo_columns, geometry_columns, TB_DOMAIN, TB_RELATIONS),
and generates a production-ready PostgreSQL / PostGIS DDL SQL script containing:
- Feature class tables with exact FDO-to-PostgreSQL data type mapping
- PostGIS spatial geometry columns (Point, LineString, Polygon) and GiST spatial indexes
- Domain value tables (_TBD) populated with domain values (ON CONFLICT DO NOTHING)
- Foreign key constraints (FOREIGN KEY) for class-to-class and class-to-domain relations
- PL/pgSQL triggers for automated spatial attribute calculations (e.g. ST_Length)
- Multiple inheritance resolution and column collision prefixing

===============================================================================
"""

import sqlite3
import sys
import argparse
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Force UTF-8 encoding for Windows console to avoid charmap encoding errors
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# =============================================================================
# 0. LOGGING SETUP
# =============================================================================

def setup_logging(log_file=None, verbose=False):
    """
    Configures the root logger with console and optional file output.
    
    Args:
        log_file (str, optional): Path to output log file.
        verbose (bool): If True, enables DEBUG log level; otherwise INFO level.
    """
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s - %(levelname)s - %(message)s"
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=level, format=fmt, handlers=handlers)


# =============================================================================
# 1. TYPE MAPPING TABLES (FDO & OGC -> POSTGRESQL / POSTGIS)
# =============================================================================

# Maps Autodesk FDO (Feature Data Objects) data type integer IDs to PostgreSQL data types
FDO_TO_POSTGRES_TYPES = {
    1: "boolean",           # FDO Boolean -> PostgreSQL boolean
    2: "smallint",          # FDO Byte -> PostgreSQL smallint
    3: "double precision",  # FDO Double (e.g. LENGTH, ORIENTATION) -> double precision
    4: "numeric",           # FDO Decimal -> PostgreSQL numeric
    5: "smallint",          # FDO Int16 -> PostgreSQL smallint
    6: "integer",           # FDO Int32 -> PostgreSQL integer
    7: "integer",           # FDO Int64 / Number -> PostgreSQL integer
    9: "varchar",           # FDO String / Text -> PostgreSQL varchar
    10: "timestamp",        # FDO DateTime -> PostgreSQL timestamp
    11: "date",             # FDO Date -> PostgreSQL date
    13: "bytea"             # FDO BLOB / Binary -> PostgreSQL bytea
}

# Maps OGC Geometry integer type IDs to PostGIS Geometry type strings
GEOM_TYPE_MAP = {
    1: "Point",
    2: "LineString",
    3: "Polygon",
    4: "MultiPoint",
    5: "MultiLineString",
    6: "MultiPolygon"
}


# =============================================================================
# 2. AUTODESK DATA MODEL METADATA CATALOG READERS
# =============================================================================

def find_col_name(cursor: sqlite3.Cursor, table_name: str, candidates: list):
    """
    Dynamically inspects the physical columns of a SQLite metadata table to find
    the exact column name from a list of candidate names.
    
    This handles naming variations across different versions of Autodesk Infrastructure
    Administrator schema exports (e.g. 'f_class_id' vs 'class_id' vs 'id').

    Args:
        cursor (sqlite3.Cursor): Active SQLite cursor.
        table_name (str): Name of the SQLite table to inspect.
        candidates (list): List of potential column name strings.

    Returns:
        str or None: The actual column name found in the table, or None if no match.
    """
    try:
        cursor.execute(f'PRAGMA table_info("{table_name}");')
        cols = [row[1] for row in cursor.fetchall()]
        cols_lower = [c.lower() for c in cols]
        for cand in candidates:
            if cand.lower() in cols_lower:
                idx = cols_lower.index(cand.lower())
                return cols[idx]
    except Exception as e:
        logger.error("Error inspecting columns of table '%s': %s", table_name, e, exc_info=True)
    return None


def get_autodesk_classes(conn: sqlite3.Connection) -> dict:
    """
    Queries `TB_DICTIONARY` (the master Autodesk class catalog) to discover all feature
    classes, their unique class IDs, table names, class types (Point, Line, Polygon, Alpha),
    captions, and parent class IDs for inheritance hierarchy.

    Args:
        conn (sqlite3.Connection): SQLite database connection.

    Returns:
        dict: Mapping of class_id -> {
            "name": str (table name),
            "type": str (class type code),
            "caption": str (human-readable label),
            "parent_id": int/str (parent class ID for inheritance)
        }

    Raises:
        ValueError: If `TB_DICTIONARY` is absent or the class name column cannot be identified.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='TB_DICTIONARY';")
    if not cursor.fetchone():
        raise ValueError("Error: System table 'TB_DICTIONARY' not found. This SQLite file is not a valid Autodesk Data Model.")

    id_col = find_col_name(cursor, "TB_DICTIONARY", ["f_class_id", "class_id", "id"])
    name_col = find_col_name(cursor, "TB_DICTIONARY", ["f_class_name", "class_name", "name", "table_name"])
    type_col = find_col_name(cursor, "TB_DICTIONARY", ["f_class_type", "class_type", "type"])
    caption_col = find_col_name(cursor, "TB_DICTIONARY", ["caption", "label", "description", "title"])
    parent_col = find_col_name(cursor, "TB_DICTIONARY", ["model_f_class_id", "parent_class_id", "parent_id"])

    if not name_col:
        raise ValueError("Error: Unable to identify the class name column in 'TB_DICTIONARY'.")

    id_str = f'"{id_col}"' if id_col else "rowid"
    type_str = f'"{type_col}"' if type_col else "'N'"
    cap_str = f'"{caption_col}"' if caption_col else f'"{name_col}"'
    parent_str = f'"{parent_col}"' if parent_col else "NULL"

    query = f"SELECT {id_str}, \"{name_col}\", {type_str}, {cap_str}, {parent_str} FROM \"TB_DICTIONARY\" WHERE \"{name_col}\" IS NOT NULL AND \"{name_col}\" != '';"
    cursor.execute(query)
    classes = {}
    for row in cursor.fetchall():
        class_id, class_name, class_type, caption, parent_id = row
        classes[class_id] = {
            "name": str(class_name).strip(),
            "type": str(class_type).strip() if class_type else "N",
            "caption": str(caption).strip() if caption else str(class_name),
            "parent_id": parent_id
        }
    return classes


def resolve_inheritance(classes: dict, conn: sqlite3.Connection) -> dict:
    """
    Builds an inheritance mapping tree. Detects whether a child class inherits from
    one or multiple parent classes (multiple inheritance support).

    Args:
        classes (dict): Master class dictionary returned by `get_autodesk_classes`.
        conn (sqlite3.Connection): SQLite connection.

    Returns:
        dict: Mapping of child_class_id -> list of parent_class_ids.
    """
    inheritance_map = {}
    for class_id, info in classes.items():
        parent_id = info.get("parent_id")
        if parent_id is not None and parent_id != class_id:
            if class_id not in inheritance_map:
                inheritance_map[class_id] = []
            inheritance_map[class_id].append(parent_id)

    # Validate and log multiple inheritance occurrences
    multi_inherit = {cid: parents for cid, parents in inheritance_map.items() if len(parents) > 1}
    if multi_inherit:
        for cid, parents in multi_inherit.items():
            class_name = classes.get(cid, {}).get("name", cid)
            parent_names = [classes.get(pid, {}).get("name", str(pid)) for pid in parents]
            logger.warning(
                "Multiple inheritance detected for class '%s' (ID=%s): parents = %s",
                class_name, cid, parent_names
            )

    return inheritance_map


def get_inherited_columns(class_id, classes: dict, inheritance_map: dict, conn: sqlite3.Connection) -> dict:
    """
    Retrieves and merges physical column definitions inherited from parent classes.
    Resolves naming collisions between multiple parent classes by prefixing conflicting
    columns with the parent table name (e.g. `PARENT_A_ID`, `PARENT_B_ID`).

    Args:
        class_id: The ID of the child feature class.
        classes (dict): Master class dictionary.
        inheritance_map (dict): Child-to-parents inheritance dictionary.
        conn (sqlite3.Connection): SQLite database connection.

    Returns:
        dict: Merged dictionary of column metadata inherited from parents.
    """
    parent_ids = inheritance_map.get(class_id, [])
    child_name = classes.get(class_id, {}).get("name", str(class_id))
    merged_cols = {}
    seen_col_sources = {}  # col_key -> parent_table_name

    for pid in parent_ids:
        parent_info = classes.get(pid)
        if parent_info:
            parent_name = parent_info["name"]
            parent_cols = get_physical_column_info(conn, parent_name)

            for col_key, col_info in parent_cols.items():
                if col_key in merged_cols:
                    first_parent = seen_col_sources[col_key]

                    # Collision detected: rename both occurrences to avoid ambiguity
                    renamed_first_key = f"{first_parent.upper()}_{col_key}"
                    renamed_current_key = f"{parent_name.upper()}_{col_key}"

                    logger.warning(
                        "Column conflict in multiple inheritance for child class '%s': "
                        "Column '%s' exists in both parent '%s' and parent '%s'. "
                        "Renaming to '%s' and '%s'.",
                        child_name, col_key, first_parent, parent_name,
                        renamed_first_key, renamed_current_key
                    )

                    # Update first parent column key and name
                    if col_key in merged_cols:
                        first_col_info = merged_cols.pop(col_key)
                        first_col_info["name"] = f"{first_parent}_{first_col_info['name']}"
                        merged_cols[renamed_first_key] = first_col_info

                    # Add current parent column with table prefix
                    new_col_info = dict(col_info)
                    new_col_info["name"] = f"{parent_name}_{col_info['name']}"
                    merged_cols[renamed_current_key] = new_col_info
                else:
                    merged_cols[col_key] = col_info
                    seen_col_sources[col_key] = parent_name

    return merged_cols


def get_fdo_column_metadata(conn: sqlite3.Connection) -> dict:
    """
    Queries `fdo_columns` (the FDO dictionary) to extract exact FDO data types,
    string lengths, and numeric precision for all feature class attributes.

    Returns:
        dict: Keyed by `(TABLE_NAME_UPPER, COLUMN_NAME_UPPER)` -> {
            "data_type": int (FDO type code),
            "length": int,
            "precision": int
        }
    """
    cursor = conn.cursor()
    fdo_meta = {}

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fdo_columns';")
    if cursor.fetchone():
        tbl_col = find_col_name(cursor, "fdo_columns", ["featureclass_name", "feature_class_name", "fdo_feature_class_name", "table_name", "class_name"])
        col_col = find_col_name(cursor, "fdo_columns", ["column_name", "fdo_column_name", "name"])
        type_col = find_col_name(cursor, "fdo_columns", ["data_type", "fdo_data_type", "type"])
        len_col = find_col_name(cursor, "fdo_columns", ["data_length", "fdo_data_length", "length"])
        prec_col = find_col_name(cursor, "fdo_columns", ["data_precision", "fdo_data_precision", "precision"])

        if tbl_col and col_col and type_col:
            len_str = f'"{len_col}"' if len_col else "NULL"
            prec_str = f'"{prec_col}"' if prec_col else "NULL"
            query = f'SELECT "{tbl_col}", "{col_col}", "{type_col}", {len_str}, {prec_str} FROM "fdo_columns";'
            cursor.execute(query)
            for tbl, col, dtype, dlen, dprec in cursor.fetchall():
                if tbl and col:
                    fdo_meta[(str(tbl).strip().upper(), str(col).strip().upper())] = {
                        "data_type": dtype,
                        "length": dlen,
                        "precision": dprec
                    }
    return fdo_meta


def get_spatial_metadata(conn: sqlite3.Connection) -> dict:
    """
    Queries `geometry_columns` (the OGC spatial metadata catalog table) to determine
    the spatial geometry column name, geometry type, and SRID for each spatial table.

    Returns:
        dict: Keyed by `TABLE_NAME_UPPER` -> {
            "geom_col": str (e.g. 'GEOM'),
            "geom_type": str (e.g. 'LineString'),
            "srid": int (e.g. 2154)
        }
    """
    cursor = conn.cursor()
    spatial_meta = {}

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='geometry_columns';")
    if cursor.fetchone():
        tbl_col = find_col_name(cursor, "geometry_columns", ["f_table_name", "table_name", "feature_class_name"])
        geom_col = find_col_name(cursor, "geometry_columns", ["f_geometry_column", "geometry_column", "column_name", "geom_column"])
        type_col = find_col_name(cursor, "geometry_columns", ["geometry_type", "type", "spatial_type"])
        srid_col = find_col_name(cursor, "geometry_columns", ["srid", "spatial_ref_sys_id", "epsg"])

        if tbl_col and geom_col:
            type_str = f'"{type_col}"' if type_col else "NULL"
            srid_str = f'"{srid_col}"' if srid_col else "NULL"
            query = f'SELECT "{tbl_col}", "{geom_col}", {type_str}, {srid_str} FROM "geometry_columns";'
            cursor.execute(query)
            for tbl, gcol, gtype, srid in cursor.fetchall():
                if tbl:
                    spatial_meta[str(tbl).strip().upper()] = {
                        "geom_col": str(gcol).strip() if gcol else "GEOM",
                        "geom_type": GEOM_TYPE_MAP.get(gtype, "Geometry") if isinstance(gtype, int) else (gtype or "Geometry"),
                        "srid": srid if (isinstance(srid, int) and srid > 0) else 2154
                    }
    return spatial_meta


def get_physical_column_info(conn: sqlite3.Connection, table_name: str) -> dict:
    """
    Queries SQLite `PRAGMA table_info(table)` to retrieve physical column names,
    raw data types, NOT NULL constraints, default values, and primary key flags.

    Args:
        conn (sqlite3.Connection): SQLite database connection.
        table_name (str): Physical table name in SQLite.

    Returns:
        dict: Mapping of COLUMN_NAME_UPPER -> {
            "name": str,
            "raw_type": str,
            "notnull": bool,
            "default": str/None,
            "pk": bool
        }
    """
    cursor = conn.cursor()
    try:
        cursor.execute(f'PRAGMA table_info("{table_name}");')
        cols = {}
        for row in cursor.fetchall():
            col_name = row[1].strip()
            cols[col_name.upper()] = {
                "name": col_name,
                "raw_type": row[2],
                "notnull": bool(row[3]),
                "default": row[4],
                "pk": bool(row[5])
            }
        return cols
    except Exception as e:
        logger.debug("Could not read PRAGMA table_info for '%s': %s", table_name, e)
        return {}


def get_autodesk_relations(conn: sqlite3.Connection) -> list:
    """
    Queries `TB_RELATIONS` (the relationship catalog) to extract foreign key links
    between feature classes and to domain lookup tables. Also extracts cardinality metadata
    (MERGE_MODE, SPLIT_MODE, CARDINALITY, RELATION_TYPE).

    Returns:
        list of dict: List of relation objects -> {
            "parent": str,
            "child": str,
            "fk_col": str,
            "merge_mode": str (optional),
            "split_mode": str (optional),
            "cardinality": str (optional),
            "relation_type": str (optional)
        }
    """
    cursor = conn.cursor()
    relations = []

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='TB_RELATIONS';")
    if cursor.fetchone():
        p_col = find_col_name(cursor, "TB_RELATIONS", ["parent_table_name", "parent_table", "parent_class_name", "parent_name", "table_name_parent"])
        c_col = find_col_name(cursor, "TB_RELATIONS", ["child_table_name", "child_table", "child_class_name", "child_name", "table_name_child"])
        fk_col = find_col_name(cursor, "TB_RELATIONS", ["fk_column_name", "fk_column", "foreign_key", "fk_name", "column_name", "fk_field"])

        merge_col = find_col_name(cursor, "TB_RELATIONS", ["merge_mode", "mergemode"])
        split_col = find_col_name(cursor, "TB_RELATIONS", ["split_mode", "splitmode"])
        card_col = find_col_name(cursor, "TB_RELATIONS", ["cardinality", "relation_cardinality"])
        reltype_col = find_col_name(cursor, "TB_RELATIONS", ["relation_type", "reltype", "rel_type"])

        if p_col and c_col:
            fk_str = f'"{fk_col}"' if fk_col else "NULL"
            merge_str = f'"{merge_col}"' if merge_col else "NULL"
            split_str = f'"{split_col}"' if split_col else "NULL"
            card_str = f'"{card_col}"' if card_col else "NULL"
            reltype_str = f'"{reltype_col}"' if reltype_col else "NULL"

            query = (
                f'SELECT "{p_col}", "{c_col}", {fk_str}, {merge_str}, {split_str}, {card_str}, {reltype_str} '
                f'FROM "TB_RELATIONS" WHERE "{p_col}" IS NOT NULL AND "{c_col}" IS NOT NULL;'
            )
            try:
                cursor.execute(query)
                for row in cursor.fetchall():
                    parent, child, fk, merge, split, card, reltype = row
                    if parent and child:
                        rel = {
                            "parent": str(parent).strip(),
                            "child": str(child).strip(),
                            "fk_col": str(fk).strip() if fk else f"{str(parent).strip()}_ID"
                        }
                        if merge is not None: rel["merge_mode"] = str(merge).strip()
                        if split is not None: rel["split_mode"] = str(split).strip()
                        if card is not None: rel["cardinality"] = str(card).strip()
                        if reltype is not None: rel["relation_type"] = str(reltype).strip()
                        relations.append(rel)
            except Exception as e:
                logger.error("Error reading TB_RELATIONS: %s", e, exc_info=True)
    return relations


def get_pk_column_name(conn: sqlite3.Connection, table_name: str) -> str:
    """
    Identifies the exact primary key column name for a SQLite table.
    Prioritizes explicit PK flags from PRAGMA table_info, defaulting to 'FID'.
    """
    cursor = conn.cursor()
    try:
        cursor.execute(f'PRAGMA table_info("{table_name}");')
        pk_cols = [(row[1], row[5]) for row in cursor.fetchall() if row[5] > 0]
        if pk_cols:
            return pk_cols[0][0]
    except Exception as e:
        logger.debug("Could not determine PK for '%s': %s", table_name, e)
    return "FID"


def get_domain_tables(conn: sqlite3.Connection) -> dict:
    """
    Finds all domain lookup tables (ending with `_TBD` or starting with `TB_DOM_`).
    Reads their physical schema and all stored records (enumerated domain values).

    Returns:
        dict: Mapping of domain_table_name -> {
            "columns": list of column names,
            "rows": list of tuples representing data rows
        }
    """
    cursor = conn.cursor()
    domain_tables = {}

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%_TBD' OR name LIKE 'TB_DOM_%');")
    tbd_names = [r[0] for r in cursor.fetchall()]

    for tname in tbd_names:
        try:
            cursor.execute(f'PRAGMA table_info("{tname}");')
            cols = [r[1] for r in cursor.fetchall()]

            cursor.execute(f'SELECT * FROM "{tname}";')
            rows = cursor.fetchall()

            domain_tables[tname] = {
                "columns": cols,
                "rows": rows
            }
        except Exception as e:
            logger.error("Error reading domain table '%s': %s", tname, e, exc_info=True)
    return domain_tables


# =============================================================================
# 3. POSTGRESQL / POSTGIS DDL GENERATION ENGINE
# =============================================================================

def generate_postgis_ddl(sqlite_path: str, default_srid: int = 2154) -> str:
    """
    Core translation coordinator. Reads the Autodesk SQLite file, parses all metadata catalogs,
    and generates a complete PostGIS DDL script formatted as valid SQL.

    Args:
        sqlite_path (str): Path to the source Autodesk SQLite file.
        default_srid (int): Default PostGIS Spatial Reference Identifier (EPSG code, default: 2154).

    Returns:
        str: Fully rendered SQL script content ready for execution in PostgreSQL.
    """
    conn = sqlite3.connect(sqlite_path)

    # Step 1: Read all metadata catalogs
    classes = get_autodesk_classes(conn)
    fdo_meta = get_fdo_column_metadata(conn)
    spatial_meta = get_spatial_metadata(conn)
    relations = get_autodesk_relations(conn)
    domain_tables = get_domain_tables(conn)
    inheritance_map = resolve_inheritance(classes, conn)

    ddl_lines = []
    ddl_lines.append("-- ============================================================")
    ddl_lines.append("-- DDL GENERATED AUTOMATICALLY BY Autocad-map-3d-PostgreSQL-Connector")
    ddl_lines.append(f"-- Source File : {Path(sqlite_path).name}")
    ddl_lines.append(f"-- Target Database : PostgreSQL / PostGIS (SRID {default_srid})")
    ddl_lines.append("-- ============================================================\n")
    ddl_lines.append("CREATE EXTENSION IF NOT EXISTS postgis;\n")

    # -------------------------------------------------------------------------
    # A. Domain Value Tables (_TBD) Generation & Initial Data Population
    # -------------------------------------------------------------------------
    if domain_tables:
        ddl_lines.append("-- ============================================================")
        ddl_lines.append("-- 1. DOMAIN VALUE TABLES (_TBD) & ENUMERATED VALUES")
        ddl_lines.append("-- ============================================================\n")
        for dt_name, dt_info in domain_tables.items():
            cols = dt_info["columns"]
            rows = dt_info["rows"]

            ddl_lines.append(f'CREATE TABLE IF NOT EXISTS "{dt_name}" (')
            col_defs = []
            for col in cols:
                if col.upper() in ["ID", "FID"]:
                    col_defs.append(f'    "{col}" integer PRIMARY KEY')
                else:
                    col_defs.append(f'    "{col}" text')
            ddl_lines.append(",\n".join(col_defs))
            ddl_lines.append(");\n")

            for r in rows:
                val_strs = []
                for val in r:
                    if val is None:
                        val_strs.append("NULL")
                    elif isinstance(val, (int, float)):
                        val_strs.append(str(val))
                    else:
                        escaped = str(val).replace("'", "''")
                        val_strs.append(f"'{escaped}'")
                col_names = ", ".join([f'"{c}"' for c in cols])
                ddl_lines.append(f'INSERT INTO "{dt_name}" ({col_names}) VALUES ({", ".join(val_strs)}) ON CONFLICT DO NOTHING;')
            ddl_lines.append("")

    # -------------------------------------------------------------------------
    # B. Feature Classes (Business Tables & PostGIS Geometry Columns)
    # -------------------------------------------------------------------------
    ddl_lines.append("-- ============================================================")
    ddl_lines.append("-- 2. FEATURE CLASSES (BUSINESS TABLES AND POSTGIS GEOMETRIES)")
    ddl_lines.append("-- ============================================================\n")

    triggers_to_generate = []

    for class_id, class_info in classes.items():
        tbl_name = class_info["name"]
        class_type = class_info["type"]
        caption = class_info["caption"]

        # Skip domain tables already handled in Section A
        if tbl_name in domain_tables or tbl_name.upper().endswith("_TBD"):
            continue

        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND LOWER(name) = LOWER(?);", (tbl_name,))
        row = cursor.fetchone()

        if row:
            real_tbl_name = row[0]
            phys_cols = get_physical_column_info(conn, real_tbl_name)
        else:
            phys_cols = {}

        # Merge inherited columns from all parents
        inherited_cols = get_inherited_columns(class_id, classes, inheritance_map, conn)
        for col_key, col_info in inherited_cols.items():
            if col_key not in phys_cols:
                phys_cols[col_key] = col_info
                logger.debug("Inherited column '%s' added to class '%s'", col_info["name"], tbl_name)

        # Fallback column structure if table is empty in SQLite
        if not phys_cols:
            phys_cols = {
                "FID": {"name": "FID", "raw_type": "INTEGER", "notnull": True, "default": None, "pk": True}
            }
            if class_type in ['P', 'L', 'S', '1', '2', '3']:
                phys_cols["GEOM"] = {"name": "GEOM", "raw_type": "GEOMETRY", "notnull": False, "default": None, "pk": False}
            if class_type == 'L':
                phys_cols["LENGTH"] = {"name": "LENGTH", "raw_type": "DOUBLE", "notnull": False, "default": None, "pk": False}

            for (f_tbl, f_col), f_info in fdo_meta.items():
                if f_tbl == tbl_name.upper() and f_col not in phys_cols:
                    phys_cols[f_col] = {"name": f_col, "raw_type": "VARCHAR", "notnull": False, "default": None, "pk": False}

        tbl_spatial = spatial_meta.get(tbl_name.upper(), {})

        ddl_lines.append(f"-- ------------------------------------------------------------")
        ddl_lines.append(f"-- Feature Class: {tbl_name} ({caption}) [FDO Type: {class_type}]")
        ddl_lines.append(f"-- ------------------------------------------------------------")
        ddl_lines.append(f'CREATE TABLE IF NOT EXISTS "{tbl_name}" (')

        column_defs = []
        pk_columns = []
        spatial_columns_to_index = []
        has_length_col = False
        geom_col_name = "GEOM"

        for col_upper, pinfo in phys_cols.items():
            col_name = pinfo["name"]

            if col_upper == "LENGTH":
                has_length_col = True

            if pinfo["pk"] or col_upper == "FID":
                pk_columns.append(f'"{col_name}"')
                column_defs.append(f'    "{col_name}" SERIAL NOT NULL')
                continue

            if col_upper == tbl_spatial.get("geom_col", "GEOM").upper() or (class_type in ['P', 'L', 'S'] and col_upper == "GEOM"):
                gtype = tbl_spatial.get("geom_type")
                if not gtype or gtype == "Geometry":
                    if class_type == 'P': gtype = "Point"
                    elif class_type == 'L': gtype = "LineString"
                    elif class_type == 'S': gtype = "Polygon"
                    else: gtype = "Geometry"

                srid = tbl_spatial.get("srid", default_srid)
                column_defs.append(f'    "{col_name}" geometry({gtype}, {srid})')
                spatial_columns_to_index.append((col_name, tbl_name))
                geom_col_name = col_name
                continue

            fmeta = fdo_meta.get((tbl_name.upper(), col_upper), {})
            fdo_dtype = fmeta.get("data_type")

            if fdo_dtype in FDO_TO_POSTGRES_TYPES:
                pg_type = FDO_TO_POSTGRES_TYPES[fdo_dtype]
                if pg_type == "varchar" and fmeta.get("length"):
                    pg_type = f"varchar({fmeta['length']})"
            else:
                raw = pinfo["raw_type"].upper()
                if "INT" in raw: pg_type = "integer"
                elif "CHAR" in raw or "TEXT" in raw: pg_type = "text"
                elif "REAL" in raw or "DOUBLE" in raw or "FLOAT" in raw: pg_type = "double precision"
                else: pg_type = "text"

            col_str = f'    "{col_name}" {pg_type}'
            if pinfo["notnull"]:
                col_str += " NOT NULL"
            if pinfo["default"] is not None:
                col_str += f" DEFAULT {pinfo['default']}"

            column_defs.append(col_str)

        if pk_columns:
            column_defs.append(f'    PRIMARY KEY ({", ".join(pk_columns)})')

        ddl_lines.append(",\n".join(column_defs))
        ddl_lines.append(");\n")

        # Create GiST spatial index on PostGIS geometry column
        for gcol, tname in spatial_columns_to_index:
            idx_name = f"idx_{tname}_{gcol}_gist"
            ddl_lines.append(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{tname}" USING GIST ("{gcol}");\n')

        # Register table for length calculation trigger if LineString with LENGTH column
        if class_type == 'L' and has_length_col:
            length_col_name = "LENGTH"
            for c_up, c_info in phys_cols.items():
                if c_up == "LENGTH":
                    length_col_name = c_info["name"]
                    break
            triggers_to_generate.append((tbl_name, geom_col_name, length_col_name))

    # -------------------------------------------------------------------------
    # C. Foreign Keys & Relations (TB_RELATIONS)
    # -------------------------------------------------------------------------
    if relations:
        ddl_lines.append("-- ============================================================")
        ddl_lines.append("-- 3. FOREIGN KEYS & RELATIONS (TB_RELATIONS)")
        ddl_lines.append("-- ============================================================\n")
        for rel in relations:
            parent = rel["parent"]
            child = rel["child"]
            fk_col = rel["fk_col"]

            child_cols = get_physical_column_info(conn, child)
            if not child_cols:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND LOWER(name) = LOWER(?);", (child,))
                row = cursor.fetchone()
                if row:
                    child_cols = get_physical_column_info(conn, row[0])

            if not child_cols or fk_col.upper() not in child_cols:
                continue

            fk_constraint_name = f"fk_{child}_{fk_col}_{parent}"
            parent_pk = get_pk_column_name(conn, parent)
            ddl_lines.append(
                f'ALTER TABLE "{child}" ADD CONSTRAINT "{fk_constraint_name}" '
                f'FOREIGN KEY ("{fk_col}") REFERENCES "{parent}" ("{parent_pk}") ON DELETE SET NULL;'
            )

            # Document cardinality in PostgreSQL constraint comment
            comment_parts = []
            if "cardinality" in rel: comment_parts.append(f"Cardinality: {rel['cardinality']}")
            if "merge_mode" in rel: comment_parts.append(f"MergeMode: {rel['merge_mode']}")
            if "split_mode" in rel: comment_parts.append(f"SplitMode: {rel['split_mode']}")
            if "relation_type" in rel: comment_parts.append(f"RelationType: {rel['relation_type']}")
            if comment_parts:
                comment_text = "; ".join(comment_parts).replace("'", "''")
                ddl_lines.append(
                    f"COMMENT ON CONSTRAINT \"{fk_constraint_name}\" ON \"{child}\" IS '{comment_text}';"
                )
        ddl_lines.append("")

    # -------------------------------------------------------------------------
    # D. PL/pgSQL Triggers for Automatic Calculations (ST_Length)
    # -------------------------------------------------------------------------
    if triggers_to_generate:
        ddl_lines.append("-- ============================================================")
        ddl_lines.append("-- 4. PL/PGSQL TRIGGERS FOR AUTOMATIC CALCULATIONS (E.G. ST_LENGTH)")
        ddl_lines.append("-- ============================================================\n")

        for tname, gcol, lcol in triggers_to_generate:
            func_name = f"fn_calc_length_{tname}"
            trigger_name = f"trg_calc_length_{tname}"
            ddl_lines.append(f"""
CREATE OR REPLACE FUNCTION "{func_name}"()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW."{gcol}" IS NOT NULL THEN
        NEW."{lcol}" := ST_Length(NEW."{gcol}");
    END IF;
    RETURN NEW;
EXCEPTION WHEN OTHERS THEN
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
""")
            ddl_lines.append(f'DROP TRIGGER IF EXISTS "{trigger_name}" ON "{tname}";')
            ddl_lines.append(
                f'CREATE TRIGGER "{trigger_name}" '
                f'BEFORE INSERT OR UPDATE OF "{gcol}" ON "{tname}" '
                f'FOR EACH ROW EXECUTE FUNCTION "{func_name}"();\n'
            )

    conn.close()
    return "\n".join(ddl_lines)


# =============================================================================
# 4. CLI ENTRY POINT
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Autodesk Data Model SQLite -> PostgreSQL/PostGIS DDL Script Converter"
    )
    parser.add_argument("--db", required=True, help="Path to the Data Model SQLite file (*.sqlite)")
    parser.add_argument("--out", default="schema_postgis.sql", help="Name of the generated SQL file (default: schema_postgis.sql)")
    parser.add_argument("--srid", type=int, default=2154, help="EPSG / SRID spatial code for PostGIS (default: 2154 / Lambert-93)")
    parser.add_argument("--log-file", dest="log_file", default=None, help="Path to log file (e.g. converter.log)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose/debug logging")

    args = parser.parse_args()

    setup_logging(log_file=args.log_file, verbose=args.verbose)

    db_file = Path(args.db)
    if not db_file.exists():
        logger.error("File not found: %s", args.db)
        sys.exit(1)

    logger.info("Analyzing Autodesk Data Model: %s", db_file.name)
    try:
        ddl_result = generate_postgis_ddl(str(db_file), default_srid=args.srid)
        out_file = Path(args.out)
        out_file.write_text(ddl_result, encoding="utf-8")
        logger.info("Generation successful! DDL file created: %s", out_file.resolve())
    except Exception as e:
        logger.error("Conversion failed: %s", e, exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
