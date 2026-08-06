#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
PROJECT : Autocad-map-3d-PostgreSQL-Connector
MODULE  : Background automation and monitoring service (File Watcher)
PHASE   : Phase 5 -- Automation of relaunch (A + E) -- V2
===============================================================================

DESCRIPTION:
This script operates as a background service/daemon.
It monitors in real-time the SQLite Data Model file (`datamodel.sqlite`).

As soon as the administrator modifies and saves the Data Model in
Autodesk Infrastructure Administrator:
1. The script instantly detects the modification of the SQLite file.
2. It automatically re-executes the Python converter `convert_autodesk_to_postgis.py`.
3. It automatically creates the PostgreSQL database if it does not exist.
4. It automatically applies the updated DDL to the PostgreSQL database (via psycopg2).

V2 IMPROVEMENTS:
- Structured logging (replaces all print statements)
- Schema diff report (orphan column detection)
- Data synchronization (--sync-data with upsert)
- Watchdog-based file monitoring with polling fallback
- Log file support (--log-file)

===============================================================================
"""

import os
import sys
import time
import json
import sqlite3
import tempfile
import subprocess
import argparse
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Force UTF-8 encoding for Windows console to avoid charmap errors
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Check interval in seconds (used for polling fallback)
CHECK_INTERVAL_SECONDS = 2

# =============================================================================
# 0. LOGGING SETUP
# =============================================================================

def setup_logging(log_file=None, verbose=False):
    """
    Configures the root logger with console and optional file output.
    """
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s - %(levelname)s - %(message)s"
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=level, format=fmt, handlers=handlers)


# =============================================================================
# 1. SQL STATEMENT SPLITTING (unchanged logic, cleaned logging)
# =============================================================================

def split_sql_statements(sql_content: str):
    """
    Splits a SQL script into executable statements without breaking:
    - SQL comments (`--` and `/* ... */`)
    - Single-quoted strings / quoted identifiers
    - PL/pgSQL blocks delimited by $$ ... $$ or $tag$ ... $tag$
    """
    statements = []
    buffer = []
    i = 0
    length = len(sql_content)
    in_single = False
    in_double = False
    in_line_comment = False
    in_block_comment = False
    dollar_tag = None

    while i < length:
        ch = sql_content[i]
        nxt = sql_content[i + 1] if i + 1 < length else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue

        if dollar_tag is not None:
            if sql_content.startswith(dollar_tag, i):
                buffer.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
            else:
                buffer.append(ch)
                i += 1
            continue

        if in_single:
            buffer.append(ch)
            if ch == "'" and nxt == "'":
                buffer.append(nxt)
                i += 2
                continue
            if ch == "'":
                in_single = False
            i += 1
            continue

        if in_double:
            buffer.append(ch)
            if ch == '"':
                in_double = False
            i += 1
            continue

        if ch == "-" and nxt == "-":
            in_line_comment = True
            i += 2
            continue

        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue

        if ch == "'":
            in_single = True
            buffer.append(ch)
            i += 1
            continue

        if ch == '"':
            in_double = True
            buffer.append(ch)
            i += 1
            continue

        if ch == "$":
            end = sql_content.find("$", i + 1)
            if end != -1:
                candidate = sql_content[i:end + 1]
                if all(c.isalnum() or c == "_" or c == "$" for c in candidate):
                    dollar_tag = candidate
                    buffer.append(candidate)
                    i = end + 1
                    continue

        if ch == ";":
            stmt = "".join(buffer).strip()
            if stmt:
                statements.append(stmt)
            buffer = []
            i += 1
            continue

        buffer.append(ch)
        i += 1

    tail = "".join(buffer).strip()
    if tail:
        statements.append(tail)

    return statements


# =============================================================================
# 2. AUTODESK SQLITE DETECTION & FILE SEARCH
# =============================================================================

# Extensions that can never be an Autodesk SQLite -> immediate rejection without reading
_NON_SQLITE_EXTS = {
    ".txt", ".log", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico",
    ".xml", ".json", ".html", ".htm", ".css", ".js", ".ts",
    ".dll", ".exe", ".msi", ".bat", ".cmd", ".ps1", ".sh",
    ".zip", ".rar", ".7z", ".gz", ".tar", ".cab",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".py", ".pyo", ".pyc", ".ini", ".cfg", ".yaml", ".toml",
    ".dwg", ".dxf", ".bak", ".dat", ".db-wal", ".db-shm",
    ".tmp", ".temp", ".lock", ".pid",
}

# Magic signature of any SQLite3 file (first 16 bytes)
_SQLITE_MAGIC = b"SQLite format 3\x00"

_ANALYZED_SQLITES = {}  # file_path -> (mtime, is_valid)


def is_autodesk_sqlite(file_path: str) -> bool:
    """
    Checks if a SQLite file is a valid Autodesk Data Model.
    Uses an mtime-based cache to avoid re-reading the file unnecessarily.
    """
    try:
        if not os.path.isfile(file_path):
            return False

        mtime = os.path.getmtime(file_path)
        if file_path in _ANALYZED_SQLITES:
            cached_mtime, cached_val = _ANALYZED_SQLITES[file_path]
            if cached_mtime == mtime:
                return cached_val

        # Level 1: exclusion by extension
        ext = Path(file_path).suffix.lower()
        if ext in _NON_SQLITE_EXTS:
            _ANALYZED_SQLITES[file_path] = (mtime, False)
            return False

        # Level 2: exclusion of Autodesk system files
        fname = Path(file_path).name.lower()
        if "tbsys" in fname or "system" in fname:
            _ANALYZED_SQLITES[file_path] = (mtime, False)
            return False

        # Level 3: reading the 16-byte SQLite magic header
        try:
            with open(file_path, "rb") as f:
                header = f.read(16)
            if header != _SQLITE_MAGIC:
                _ANALYZED_SQLITES[file_path] = (mtime, False)
                return False
        except (OSError, PermissionError):
            return False

        logger.debug("Examining candidate SQLite file: %s", file_path)

        # Level 4: check for TB_DICTIONARY table (unique to Autodesk Data Models)
        conn = sqlite3.connect(file_path, timeout=2.0)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='TB_DICTIONARY';")
        has_tb_dict = cursor.fetchone() is not None
        conn.close()

        if has_tb_dict:
            logger.info("Valid Autodesk Industry Model found: %s", file_path)
        else:
            logger.debug("Table 'TB_DICTIONARY' absent in %s (not an Industry Model)", file_path)

        _ANALYZED_SQLITES[file_path] = (mtime, has_tb_dict)
        return has_tb_dict
    except Exception as e:
        logger.error("Error checking file '%s': %s", file_path, e, exc_info=True)
        return False


def find_autodesk_sqlite(search_dir: str = None, model_name: str = None) -> str:
    """
    Performs a general and dynamic search for an Autodesk SQLite file.
    Returns the path of the most recently modified valid file.
    """
    base_dir = search_dir if search_dir else tempfile.gettempdir()
    logger.info("General search in: %s", base_dir)

    candidates = []
    for root, _, files in os.walk(base_dir):
        for f in files:
            if model_name and model_name.lower() not in f.lower() and model_name.lower() not in root.lower():
                continue
            full_path = os.path.join(root, f)
            if is_autodesk_sqlite(full_path):
                mtime = os.path.getmtime(full_path)
                candidates.append((mtime, full_path))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def clean_postgres_db_name(name: str) -> str:
    """
    Cleans and formats a string to be a valid PostgreSQL database name.
    """
    if not name:
        return ""
    import re
    import unicodedata

    nfkd_form = unicodedata.normalize('NFKD', name)
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('ASCII')
    cleaned = only_ascii.lower()
    cleaned = re.sub(r'[^a-z0-9]+', '_', cleaned)
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    return cleaned


def get_industry_model_name(sqlite_path: str) -> str:
    """
    Reads the Industry Model name from the Autodesk system table 'TB_INFO'.
    """
    try:
        if not os.path.isfile(sqlite_path):
            return None
        conn = sqlite3.connect(sqlite_path, timeout=5.0)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='TB_INFO';")
        if not cursor.fetchone():
            conn.close()
            return None

        cursor.execute("SELECT VALUE_CHAR FROM TB_INFO WHERE PARAM = 'DOCUMENT_NAME';")
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            return row[0].strip()
    except Exception as e:
        logger.warning("Note while retrieving model name (TB_INFO): %s", e)
    return None


# =============================================================================
# 3. SCHEMA DIFF REPORT (V2 - Axis 2)
# =============================================================================

def detect_schema_differences(sqlite_path: str, pg_conn, allow_drop: bool = False) -> dict:
    """
    Compares the columns of PostgreSQL with those of the SQLite source
    for each business table. Generates a structured diff report.
    If allow_drop=True, automatically issues ALTER TABLE DROP COLUMN for orphan columns.
    """
    report = {}

    try:
        sq_conn = sqlite3.connect(sqlite_path)
        sq_cursor = sq_conn.cursor()

        sq_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='TB_DICTIONARY';")
        if not sq_cursor.fetchone():
            sq_conn.close()
            return report

        from convert_autodesk_to_postgis import (
            get_autodesk_classes,
            get_fdo_column_metadata,
            get_physical_column_info,
            FDO_TO_POSTGRES_TYPES
        )

        classes = get_autodesk_classes(sq_conn)
        fdo_meta = get_fdo_column_metadata(sq_conn)
        pg_cursor = pg_conn.cursor()

        for class_id, class_info in classes.items():
            tbl_name = class_info["name"]

            # Verify table exists in PG
            pg_cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s);",
                (tbl_name,)
            )
            if not pg_cursor.fetchone()[0]:
                continue

            # Get SQLite columns
            phys_cols = get_physical_column_info(sq_conn, tbl_name)
            sqlite_col_names = set(phys_cols.keys())

            # Get PostgreSQL columns with types
            pg_cursor.execute(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s;",
                (tbl_name,)
            )
            pg_cols_info = {row[0].upper(): row[1] for row in pg_cursor.fetchall()}
            pg_col_names = set(pg_cols_info.keys())

            missing_in_pg = sorted(sqlite_col_names - pg_col_names)
            orphan_in_pg = sorted(pg_col_names - sqlite_col_names)

            # Type comparison for common columns
            type_mismatch = {}
            for col_upper in sorted(sqlite_col_names & pg_col_names):
                sqlite_type = phys_cols[col_upper]["raw_type"].upper() if phys_cols[col_upper]["raw_type"] else ""
                pg_type = pg_cols_info[col_upper].upper()

                # Get the expected PG type from FDO metadata
                fmeta = fdo_meta.get((tbl_name.upper(), col_upper), {})
                fdo_dtype = fmeta.get("data_type")
                if fdo_dtype in FDO_TO_POSTGRES_TYPES:
                    expected_pg = FDO_TO_POSTGRES_TYPES[fdo_dtype].upper()
                else:
                    expected_pg = None

                if expected_pg and expected_pg not in pg_type and pg_type not in expected_pg:
                    type_mismatch[col_upper] = {
                        "sqlite": sqlite_type,
                        "pg": pg_type,
                        "expected_pg": expected_pg
                    }

            if missing_in_pg or orphan_in_pg or type_mismatch:
                report[tbl_name] = {
                    "missing_in_pg": missing_in_pg,
                    "orphan_in_pg": orphan_in_pg,
                    "type_mismatch": type_mismatch
                }

                if orphan_in_pg:
                    if allow_drop:
                        for col in orphan_in_pg:
                            try:
                                drop_sql = f'ALTER TABLE "{tbl_name}" DROP COLUMN "{col}";'
                                pg_cursor.execute(drop_sql)
                                pg_conn.commit()
                                logger.info("ALTER TABLE DROP COLUMN: Removed orphan column '%s' from PG table '%s'", col, tbl_name)
                            except Exception as e:
                                pg_conn.rollback()
                                logger.error("Failed to drop orphan column '%s' from '%s': %s", col, tbl_name, e)
                    else:
                        logger.warning(
                            "Table '%s': %d orphan column(s) in PostgreSQL (not in SQLite source): %s",
                            tbl_name, len(orphan_in_pg), orphan_in_pg
                        )
                if missing_in_pg:
                    logger.info(
                        "Table '%s': %d column(s) missing in PostgreSQL: %s",
                        tbl_name, len(missing_in_pg), missing_in_pg
                    )

        sq_conn.close()

    except Exception as e:
        logger.error("Error during schema difference detection: %s", e, exc_info=True)

    # Save report to JSON if not empty
    if report:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"schema_diff_{timestamp}.json"
        try:
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info("Schema diff report saved to: %s", report_file)
        except Exception as e:
            logger.error("Failed to save schema diff report: %s", e, exc_info=True)

    return report


# =============================================================================
# 4. DATA SYNCHRONIZATION (V2 - Axis 3)
# =============================================================================

def sync_data(sqlite_path: str, pg_conn, default_srid: int = 2154):
    """
    Synchronizes data from SQLite to PostgreSQL using upsert (INSERT ... ON CONFLICT DO UPDATE).
    Handles geometry conversion from SQLite BLOB (WKB) to PostGIS format.
    """
    # Optional tqdm progress bar
    try:
        from tqdm import tqdm
        has_tqdm = True
    except ImportError:
        has_tqdm = False

    try:
        sq_conn = sqlite3.connect(sqlite_path)
        sq_cursor = sq_conn.cursor()

        sq_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='TB_DICTIONARY';")
        if not sq_cursor.fetchone():
            sq_conn.close()
            return

        from convert_autodesk_to_postgis import (
            get_autodesk_classes,
            get_spatial_metadata,
            get_physical_column_info,
            get_pk_column_name
        )

        classes = get_autodesk_classes(sq_conn)
        spatial_meta = get_spatial_metadata(sq_conn)
        pg_cursor = pg_conn.cursor()

        table_iter = classes.items()
        if has_tqdm:
            table_iter = tqdm(list(table_iter), desc="Syncing tables", unit="table")

        for class_id, class_info in table_iter:
            tbl_name = class_info["name"]

            # Skip domain tables
            if tbl_name.upper().endswith("_TBD"):
                continue

            # Check if table exists in PostgreSQL
            pg_cursor.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s);",
                (tbl_name,)
            )
            if not pg_cursor.fetchone()[0]:
                continue

            # Get column info
            phys_cols = get_physical_column_info(sq_conn, tbl_name)
            if not phys_cols:
                continue

            # Get PK column
            pk_col = get_pk_column_name(sq_conn, tbl_name)
            tbl_spatial = spatial_meta.get(tbl_name.upper(), {})
            geom_col = tbl_spatial.get("geom_col", "GEOM").upper()
            srid = tbl_spatial.get("srid", default_srid)

            # Read all rows from SQLite
            try:
                col_names = [info["name"] for info in phys_cols.values()]
                sq_cursor.execute(f'SELECT * FROM "{tbl_name}";')
                rows = sq_cursor.fetchall()
            except Exception as e:
                logger.warning("Could not read data from SQLite table '%s': %s", tbl_name, e)
                continue

            if not rows:
                continue

            logger.info("Syncing %d row(s) from table '%s'", len(rows), tbl_name)

            row_iter = rows
            if has_tqdm:
                row_iter = tqdm(rows, desc=f"  {tbl_name}", unit="row", leave=False)

            synced = 0
            errors = 0
            for row in row_iter:
                try:
                    col_placeholders = []
                    values = []
                    update_parts = []

                    for i, (col_upper, pinfo) in enumerate(phys_cols.items()):
                        col_name = pinfo["name"]
                        val = row[i] if i < len(row) else None

                        if col_upper == geom_col and val is not None:
                            # Geometry column: handle WKB blob or WKT string
                            if isinstance(val, bytes):
                                col_placeholders.append(f"ST_GeomFromWKB(%s::bytea, {srid})")
                                values.append(val)
                            elif isinstance(val, str) and val.strip():
                                col_placeholders.append(f"ST_GeomFromText(%s, {srid})")
                                values.append(val)
                            else:
                                col_placeholders.append("%s")
                                values.append(None)
                        else:
                            col_placeholders.append("%s")
                            values.append(val)

                        if col_upper != pk_col.upper():
                            if col_upper == geom_col and val is not None:
                                if isinstance(val, bytes):
                                    update_parts.append(f'"{col_name}" = ST_GeomFromWKB(EXCLUDED."{col_name}"::bytea, {srid})')
                                elif isinstance(val, str) and val.strip():
                                    update_parts.append(f'"{col_name}" = ST_GeomFromText(EXCLUDED."{col_name}", {srid})')
                                else:
                                    update_parts.append(f'"{col_name}" = EXCLUDED."{col_name}"')
                            else:
                                update_parts.append(f'"{col_name}" = EXCLUDED."{col_name}"')

                    col_name_list = ", ".join([f'"{info["name"]}"' for info in phys_cols.values()])
                    placeholder_list = ", ".join(col_placeholders)

                    if update_parts:
                        update_clause = ", ".join(update_parts)
                        upsert_sql = (
                            f'INSERT INTO "{tbl_name}" ({col_name_list}) VALUES ({placeholder_list}) '
                            f'ON CONFLICT ("{pk_col}") DO UPDATE SET {update_clause};'
                        )
                    else:
                        upsert_sql = (
                            f'INSERT INTO "{tbl_name}" ({col_name_list}) VALUES ({placeholder_list}) '
                            f'ON CONFLICT ("{pk_col}") DO NOTHING;'
                        )

                    pg_cursor.execute(upsert_sql, values)
                    synced += 1

                except Exception as e:
                    errors += 1
                    logger.debug("Error syncing row in '%s': %s", tbl_name, e)

            pg_conn.commit()
            if errors > 0:
                logger.warning("Table '%s': %d synced, %d failed", tbl_name, synced, errors)
            else:
                logger.info("Table '%s': %d row(s) synced successfully", tbl_name, synced)

        sq_conn.close()

    except Exception as e:
        logger.error("Error during data synchronization: %s", e, exc_info=True)


# =============================================================================
# 5. COLUMN SYNCHRONIZATION (V1 logic with V2 logging)
# =============================================================================

def sync_table_columns(sqlite_path: str, pg_conn, default_srid=2154):
    """
    Dynamically synchronizes table columns from SQLite to PostgreSQL.
    For each column present in SQLite but absent in PostgreSQL,
    issues an ALTER TABLE ADD COLUMN command with the correct type.
    """
    try:
        sq_conn = sqlite3.connect(sqlite_path)
        sq_cursor = sq_conn.cursor()

        sq_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='TB_DICTIONARY';")
        if not sq_cursor.fetchone():
            sq_conn.close()
            return

        from convert_autodesk_to_postgis import (
            get_autodesk_classes,
            get_fdo_column_metadata,
            get_spatial_metadata,
            get_physical_column_info,
            FDO_TO_POSTGRES_TYPES
        )

        classes = get_autodesk_classes(sq_conn)
        fdo_meta = get_fdo_column_metadata(sq_conn)
        spatial_meta = get_spatial_metadata(sq_conn)

        pg_cursor = pg_conn.cursor()

        for class_id, class_info in classes.items():
            tbl_name = class_info["name"]
            class_type = class_info["type"]

            pg_cursor.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s);",
                (tbl_name,)
            )
            table_exists = pg_cursor.fetchone()[0]
            if not table_exists:
                continue

            phys_cols = get_physical_column_info(sq_conn, tbl_name)
            if not phys_cols:
                continue

            pg_cursor.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s;",
                (tbl_name,)
            )
            pg_cols = {row[0].upper() for row in pg_cursor.fetchall()}

            tbl_spatial = spatial_meta.get(tbl_name.upper(), {})

            for col_upper, pinfo in phys_cols.items():
                if col_upper in pg_cols:
                    continue

                col_name = pinfo["name"]

                if col_upper == tbl_spatial.get("geom_col", "GEOM").upper() or (class_type in ['P', 'L', 'S'] and col_upper == "GEOM"):
                    gtype = tbl_spatial.get("geom_type")
                    if not gtype or gtype == "Geometry":
                        if class_type == 'P': gtype = "Point"
                        elif class_type == 'L': gtype = "LineString"
                        elif class_type == 'S': gtype = "Polygon"
                        else: gtype = "Geometry"
                    srid = tbl_spatial.get("srid", default_srid)
                    pg_type = f"geometry({gtype}, {srid})"
                else:
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

                logger.info("ALTER TABLE: column '%s' (%s) missing in PG table '%s'", col_name, pg_type, tbl_name)
                alter_stmt = f'ALTER TABLE "{tbl_name}" ADD COLUMN "{col_name}" {pg_type}'
                if pinfo["default"] is not None:
                    alter_stmt += f" DEFAULT {pinfo['default']}"

                try:
                    pg_cursor.execute(alter_stmt + ";")
                    logger.info("Column '%s' added successfully to '%s'", col_name, tbl_name)
                except Exception as ex:
                    logger.error("Failed to add column '%s' to '%s': %s", col_name, tbl_name, ex, exc_info=True)

        pg_conn.commit()
        sq_conn.close()
    except Exception as e:
        logger.error("Error during dynamic column synchronization: %s", e, exc_info=True)


# =============================================================================
# 6. POSTGRESQL DATABASE MANAGEMENT
# =============================================================================

def ensure_pg_database_exists(host="localhost", port=5432, user="postgres", password="", dbname="autocad_test"):
    """
    Checks if the PostgreSQL database exists, and creates it automatically if needed.
    """
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

        conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname="postgres")
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s;", (dbname,))
        exists = cursor.fetchone()

        if not exists:
            logger.info("Database '%s' does not exist yet. Creating automatically...", dbname)
            cursor.execute(f'CREATE DATABASE "{dbname}";')
            logger.info("Database '%s' created successfully!", dbname)

            conn_new = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname)
            cursor_new = conn_new.cursor()
            cursor_new.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
            conn_new.commit()
            cursor_new.close()
            conn_new.close()
            logger.info("PostGIS extension enabled on '%s'.", dbname)

        cursor.close()
        conn.close()
    except Exception as e:
        logger.error("Error while checking/creating PostgreSQL database: %s", e, exc_info=True)


# =============================================================================
# 7. CONVERSION & APPLICATION ENGINE
# =============================================================================

# =============================================================================
# 6.5 HELPER FUNCTIONS FOR POSTGRESQL INSPECTION
# =============================================================================

def get_existing_tables(cursor) -> set:
    """Returns a set of uppercase table names in the public schema."""
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
    return {row[0].upper() for row in cursor.fetchall()}


def get_existing_indexes(cursor) -> set:
    """Returns a set of uppercase index names in the public schema."""
    cursor.execute("SELECT indexname FROM pg_indexes WHERE schemaname = 'public';")
    return {row[0].upper() for row in cursor.fetchall()}


def get_existing_triggers(cursor) -> set:
    """Returns a set of uppercase trigger names in the public schema."""
    cursor.execute("SELECT trigger_name FROM information_schema.triggers WHERE trigger_schema = 'public';")
    return {row[0].upper() for row in cursor.fetchall()}


# =============================================================================
# 7. CONVERSION & APPLICATION ENGINE
# =============================================================================

def run_conversion_and_apply(sqlite_path: str, output_sql: str, pg_host: str, pg_port: int,
                             pg_user: str, pg_pass: str, pg_db: str, srid: int,
                             sync_data_flag: bool = False, allow_drop: bool = False):
    """
    Executes the DDL conversion script on a SQLite file and applies the generated DDL to PostgreSQL.
    """
    cmd = [
        sys.executable,
        os.path.join(os.path.dirname(__file__), "convert_autodesk_to_postgis.py"),
        "--db", sqlite_path,
        "--out", output_sql,
        "--srid", str(srid)
    ]

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)

    if result.returncode == 0:
        logger.info("DDL conversion successful -> %s", output_sql)

        if pg_user and pg_pass:
            try:
                import psycopg2

                ensure_pg_database_exists(host=pg_host, port=pg_port, user=pg_user, password=pg_pass, dbname=pg_db)

                logger.info("Applying DDL to database '%s' (%s:%s)...", pg_db, pg_host, pg_port)
                conn = psycopg2.connect(host=pg_host, port=pg_port, user=pg_user, password=pg_pass, dbname=pg_db)
                conn.autocommit = True
                cursor = conn.cursor()
                sql_content = Path(output_sql).read_text(encoding="utf-8")

                success_count = 0
                created_tables = []
                created_domains = []
                created_indexes = []
                created_fks = 0
                created_triggers = []
                failed_statements = []

                logger.info("Schema application starting...")

                existing_pg_tables = get_existing_tables(cursor)
                existing_pg_indexes = get_existing_indexes(cursor)
                existing_pg_triggers = get_existing_triggers(cursor)

                statements = split_sql_statements(sql_content)

                for stmt in statements:
                    stmt_clean = stmt.strip()
                    if not stmt_clean or stmt_clean.startswith("--"):
                        continue

                    stmt_upper = stmt_clean.upper()
                    try:
                        cursor.execute(stmt_clean)
                        success_count += 1

                        if "CREATE TABLE" in stmt_upper:
                            parts = stmt_clean.split('"')
                            tname = parts[1] if len(parts) > 1 else "Table"
                            tname_upper = tname.upper()
                            if tname_upper not in existing_pg_tables:
                                existing_pg_tables.add(tname_upper)
                                if tname.endswith("_TBD") or tname == "TB_DOMAIN":
                                    created_domains.append(tname)
                                    logger.info("Domain table '%s' created", tname)
                                else:
                                    created_tables.append(tname)
                                    logger.info("Feature class '%s' created", tname)
                        elif "CREATE INDEX" in stmt_upper:
                            parts = stmt_clean.split('"')
                            idx_name = parts[1] if len(parts) > 1 else "Index"
                            idx_upper = idx_name.upper()
                            if idx_upper not in existing_pg_indexes:
                                existing_pg_indexes.add(idx_upper)
                                created_indexes.append(idx_name)
                                logger.info("Spatial index '%s' created", idx_name)
                        elif "FOREIGN KEY" in stmt_upper:
                            created_fks += 1
                        elif "CREATE TRIGGER" in stmt_upper:
                            parts = stmt_clean.split('"')
                            trg_name = parts[1] if len(parts) > 1 else "Trigger"
                            trg_upper = trg_name.upper()
                            if trg_upper not in existing_pg_triggers:
                                existing_pg_triggers.add(trg_upper)
                                created_triggers.append(trg_name)
                                logger.info("Trigger '%s' activated", trg_name)
                    except Exception as ex:
                        conn.rollback()
                        first_line = stmt_clean.splitlines()[0][:120]
                        failed_statements.append((first_line, str(ex)))
                        logger.error("SQL Error: %s -> %s", first_line, ex)

                # Column synchronization (ALTER TABLE)
                logger.info("Starting attribute synchronization...")
                sync_table_columns(sqlite_path, conn, srid)

                # V2: Schema diff report (with optional drop)
                logger.info("Detecting schema differences...")
                detect_schema_differences(sqlite_path, conn, allow_drop=allow_drop)

                # V2: Data synchronization (optional)
                if sync_data_flag:
                    logger.info("Starting data synchronization (upsert)...")
                    sync_data(sqlite_path, conn, srid)

                cursor.close()
                conn.close()

                # Summary
                logger.info("=== SYNCHRONIZATION SUMMARY ===")
                logger.info("Feature Classes: %d table(s) %s", len(created_tables),
                            f"-> {', '.join(created_tables)}" if created_tables else "")
                logger.info("Domain Tables:   %d table(s) %s", len(created_domains),
                            f"-> {', '.join(created_domains)}" if created_domains else "")
                logger.info("Spatial Indexes: %d, FK: %d, Triggers: %d",
                            len(created_indexes), created_fks, len(created_triggers))
                if failed_statements:
                    logger.warning("Partial sync: %d successful, %d failed", success_count, len(failed_statements))
                else:
                    logger.info("PostgreSQL synchronization 100%% successful (%d SQL queries)", success_count)

            except ImportError:
                logger.warning("Module 'psycopg2' not installed. Install with: pip install psycopg2-binary")
            except Exception as e:
                logger.error("Error while applying to PostgreSQL: %s", e, exc_info=True)
        else:
            logger.info("No PostgreSQL credentials provided. Only the SQL file was generated.")
    else:
        logger.error("DDL conversion failed: %s", result.stderr)


# =============================================================================
# 8. MULTI-MODEL FILE DISCOVERY
# =============================================================================

def find_all_autodesk_sqlites(search_dir: str = None, model_name: str = None) -> list:
    """
    Scans the temporary directory (%TEMP% by default) and returns ALL valid Autodesk SQLite files.
    """
    base_dir = search_dir if search_dir else tempfile.gettempdir()
    found_models = []
    seen_paths = set()
    used_db_names = {}

    for root, _, files in os.walk(base_dir):
        for f in files:
            if model_name and model_name.lower() not in f.lower() and model_name.lower() not in root.lower():
                continue

            full_path = os.path.join(root, f)
            if full_path in seen_paths:
                continue


            if is_autodesk_sqlite(full_path):
                seen_paths.add(full_path)

                file_stem = Path(full_path).stem

                # Use the filesystem name (file stem / parent folder) as the stable database identifier.
                # TB_INFO DOCUMENT_NAME is kept as a human-readable label but NOT used for db naming,
                # because Autodesk can write the same DOCUMENT_NAME into multiple temp files.
                doc_name = get_industry_model_name(full_path)  # human-readable label only

                if not file_stem.lower().startswith("drawing") and file_stem.lower() != "datamodel":
                    raw_name = file_stem
                else:
                    parent_name = Path(full_path).parent.name
                    raw_name = f"{file_stem}_{parent_name[:6]}"

                db_name = clean_postgres_db_name(raw_name)
                if not db_name:
                    db_name = "industry_model"

                # Strict deduplication by exact file path — no suffix appending
                if db_name in used_db_names:
                    existing_index = used_db_names[db_name]
                    if found_models[existing_index]["mtime"] < os.path.getmtime(full_path):
                        found_models[existing_index] = {
                            "path": full_path,
                            "model_name": doc_name or raw_name,
                            "db_name": db_name,
                            "output_sql": f"schema_{db_name}.sql",
                            "mtime": os.path.getmtime(full_path)
                        }
                    continue

                used_db_names[db_name] = len(found_models)
                mtime = os.path.getmtime(full_path)
                output_sql = f"schema_{db_name}.sql"

                found_models.append({
                    "path": full_path,
                    "model_name": doc_name or raw_name,
                    "db_name": db_name,
                    "output_sql": output_sql,
                    "mtime": mtime
                })



    return found_models


# =============================================================================
# 9. WATCHDOG HANDLER (V2 - Axis 6)
# =============================================================================

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False


class AutodeskSQLiteHandler:
    """
    Watchdog-based file system event handler for Autodesk SQLite files.
    Includes debounce mechanism to avoid duplicate triggers.
    """

    def __init__(self, pg_host, pg_port, pg_user, pg_pass, pg_db, srid, output_sql, sync_data_flag, model_name=None):
        if HAS_WATCHDOG:
            self._handler = _WatchdogHandler(
                pg_host, pg_port, pg_user, pg_pass, pg_db, srid, output_sql, sync_data_flag, model_name
            )
        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_user = pg_user
        self.pg_pass = pg_pass
        self.pg_db = pg_db
        self.srid = srid
        self.output_sql = output_sql
        self.sync_data_flag = sync_data_flag
        self.model_name = model_name


class _WatchdogHandler(FileSystemEventHandler):
        """Internal watchdog handler with debounce logic."""

        DEBOUNCE_SECONDS = 3.0

        def __init__(self, pg_host, pg_port, pg_user, pg_pass, pg_db, srid, output_sql, sync_data_flag, allow_drop, model_name):
            super().__init__()
            self.pg_host = pg_host
            self.pg_port = pg_port
            self.pg_user = pg_user
            self.pg_pass = pg_pass
            self.pg_db = pg_db
            self.srid = srid
            self.output_sql = output_sql
            self.sync_data_flag = sync_data_flag
            self.allow_drop = allow_drop
            self.model_name = model_name
            self._last_triggered = {}  # file_path -> timestamp
            self._monitored = {}  # file_path -> {db_name, output_sql}

        def _should_process(self, file_path: str) -> bool:
            """Debounce: skip if triggered too recently."""
            now = time.time()
            last = self._last_triggered.get(file_path, 0)
            if now - last < self.DEBOUNCE_SECONDS:
                return False
            self._last_triggered[file_path] = now
            return True

        def _handle_event(self, event):
            if event.is_directory:
                return

            file_path = event.src_path

            if self.model_name and self.model_name.lower() not in file_path.lower():
                return

            if not self._should_process(file_path):
                return

            if not is_autodesk_sqlite(file_path):
                return

            logger.info("Watchdog: change detected in %s", file_path)

            db_name = self.pg_db
            out_sql = self.output_sql
            if not db_name:
                model_name_from_file = get_industry_model_name(file_path)
                if model_name_from_file:
                    db_name = clean_postgres_db_name(model_name_from_file)
                if not db_name:
                    db_name = clean_postgres_db_name(Path(file_path).stem)
            if not out_sql:
                out_sql = f"schema_{db_name}.sql"

            run_conversion_and_apply(
                sqlite_path=file_path,
                output_sql=out_sql,
                pg_host=self.pg_host,
                pg_port=self.pg_port,
                pg_user=self.pg_user,
                pg_pass=self.pg_pass,
                pg_db=db_name,
                srid=self.srid,
                sync_data_flag=self.sync_data_flag,
                allow_drop=self.allow_drop
            )

        def on_modified(self, event):
            self._handle_event(event)

        def on_created(self, event):
            self._handle_event(event)


# =============================================================================
# 10. MAIN MONITORING SERVICE
# =============================================================================

def watch_file(sqlite_path: str = None, search_dir: str = None, model_name: str = None,
               output_sql: str = None, pg_host="localhost", pg_port=5432, pg_user=None,
               pg_pass=None, pg_db=None, srid: int = 2154, run_initial_sync: bool = False,
               sync_data_flag: bool = False, allow_drop: bool = False):
    """
    Multi-model monitoring service:
    Uses watchdog (if available) or polling fallback.
    """
    logger.info("===================================================================")
    logger.info(" AUTODESK MULTI-MODEL AUTOMATIC MONITORING SERVICE")
    logger.info("===================================================================")
    watch_dir = search_dir or tempfile.gettempdir()
    logger.info("Monitoring zone: %s", watch_dir)

    if pg_user and pg_pass:
        logger.info("Mode: DDL generation + automatic PostgreSQL application")
    else:
        logger.info("Mode: DDL file generation only")

    # Initial detection
    if sqlite_path and os.path.exists(sqlite_path):
        raw_name = Path(sqlite_path).stem
        target_db = pg_db or clean_postgres_db_name(raw_name)
        out_sql = output_sql or f"schema_{target_db}.sql"
        initial_list = [{
            "path": sqlite_path,
            "model_name": raw_name,
            "db_name": target_db,
            "output_sql": out_sql,
            "mtime": os.path.getmtime(sqlite_path)
        }]
    else:
        initial_list = find_all_autodesk_sqlites(search_dir=search_dir, model_name=model_name)

    if not initial_list:
        logger.warning("No active Autodesk Industry Model found at this time.")
        logger.info("Service is waiting for a Data Model to be opened...")

    monitored = {}
    for m in initial_list:
        fpath = m["path"]
        db = m["db_name"]
        logger.info("Industry Model detected: '%s'", m["model_name"])
        logger.info("  SQLite source: %s", fpath)
        logger.info("  PostgreSQL DB: '%s'", db)
        logger.info("  DDL file:      '%s'", m["output_sql"])

        monitored[fpath] = {
            "db_name": db,
            "mtime": m["mtime"],
            "output_sql": m["output_sql"]
        }

        if run_initial_sync:
            run_conversion_and_apply(
                sqlite_path=fpath,
                output_sql=m["output_sql"],
                pg_host=pg_host,
                pg_port=pg_port,
                pg_user=pg_user,
                pg_pass=pg_pass,
                pg_db=db,
                srid=srid,
                sync_data_flag=sync_data_flag,
                allow_drop=allow_drop
            )

    # V2: Choose watchdog or polling
    if HAS_WATCHDOG:
        logger.info("Watchdog mode active (event-driven monitoring). Press CTRL+C to stop.")
        _watch_with_watchdog(
            watch_dir=watch_dir,
            pg_host=pg_host, pg_port=pg_port, pg_user=pg_user, pg_pass=pg_pass,
            pg_db=pg_db, srid=srid, output_sql=output_sql,
            sync_data_flag=sync_data_flag, allow_drop=allow_drop, model_name=model_name
        )
    else:
        logger.warning("Watchdog not installed. Falling back to polling mode (every %ds). "
                       "Install with: pip install watchdog", CHECK_INTERVAL_SECONDS)
        _watch_with_polling(
            sqlite_path=sqlite_path, search_dir=search_dir, model_name=model_name,
            output_sql=output_sql, pg_host=pg_host, pg_port=pg_port, pg_user=pg_user,
            pg_pass=pg_pass, pg_db=pg_db, srid=srid, monitored=monitored,
            sync_data_flag=sync_data_flag, allow_drop=allow_drop
        )


def _watch_with_watchdog(watch_dir, pg_host, pg_port, pg_user, pg_pass, pg_db, srid,
                          output_sql, sync_data_flag, allow_drop, model_name):
    """Run monitoring using watchdog Observer."""
    handler = _WatchdogHandler(
        pg_host=pg_host, pg_port=pg_port, pg_user=pg_user, pg_pass=pg_pass,
        pg_db=pg_db, srid=srid, output_sql=output_sql,
        sync_data_flag=sync_data_flag, allow_drop=allow_drop, model_name=model_name
    )
    observer = Observer()
    observer.schedule(handler, watch_dir, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping watchdog observer...")
        observer.stop()
    observer.join()
    logger.info("Multi-model monitoring service stopped.")


def _watch_with_polling(sqlite_path, search_dir, model_name, output_sql,
                         pg_host, pg_port, pg_user, pg_pass, pg_db, srid,
                         monitored, sync_data_flag, allow_drop):
    """Run monitoring using polling fallback."""
    logger.info("Polling mode active (every %ds). Press CTRL+C to stop.", CHECK_INTERVAL_SECONDS)

    try:
        heartbeat_counter = 0
        HEARTBEAT_EVERY = 5

        while True:
            time.sleep(CHECK_INTERVAL_SECONDS)
            heartbeat_counter += 1

            if sqlite_path and os.path.exists(sqlite_path):
                raw_name = Path(sqlite_path).stem
                target_db = pg_db or clean_postgres_db_name(raw_name)
                out_sql = output_sql or f"schema_{target_db}.sql"
                active_models = [{
                    "path": sqlite_path,
                    "model_name": raw_name,
                    "db_name": target_db,
                    "output_sql": out_sql,
                    "mtime": os.path.getmtime(sqlite_path)
                }]
            else:
                active_models = find_all_autodesk_sqlites(search_dir=search_dir, model_name=model_name)

            any_change = False
            for m in active_models:
                fpath = m["path"]
                db = m["db_name"]
                curr_mtime = m["mtime"]
                out_sql = m["output_sql"]

                if fpath not in monitored:
                    any_change = True
                    logger.info("New Data Model detected: '%s'", m["model_name"])
                    logger.info("  SQLite: %s | DB: '%s' | DDL: '%s'", fpath, db, out_sql)

                    monitored[fpath] = {
                        "db_name": db,
                        "mtime": curr_mtime,
                        "output_sql": out_sql
                    }

                    run_conversion_and_apply(
                        sqlite_path=fpath, output_sql=out_sql,
                        pg_host=pg_host, pg_port=pg_port, pg_user=pg_user,
                        pg_pass=pg_pass, pg_db=db, srid=srid,
                        sync_data_flag=sync_data_flag, allow_drop=allow_drop
                    )

                elif curr_mtime != monitored[fpath]["mtime"]:
                    any_change = True
                    monitored[fpath]["mtime"] = curr_mtime
                    run_conversion_and_apply(
                        sqlite_path=fpath, output_sql=out_sql,
                        pg_host=pg_host, pg_port=pg_port, pg_user=pg_user,
                        pg_pass=pg_pass, pg_db=db, srid=srid,
                        sync_data_flag=sync_data_flag, allow_drop=allow_drop
                    )

            if not any_change and heartbeat_counter >= HEARTBEAT_EVERY:
                heartbeat_counter = 0
                logger.debug("Active monitoring -- %d model(s) under observation. Waiting...", len(monitored))

    except KeyboardInterrupt:
        logger.info("Multi-model monitoring service stopped.")


# =============================================================================
# 11. CLI ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Monitors one or more Autodesk Data Models and automatically applies DDL to PostgreSQL."
    )
    parser.add_argument("--db", dest="sqlite_file", default=None, help="Explicit path to a Data Model SQLite file (optional)")
    parser.add_argument("--dir", dest="search_dir", default=None, help="Root directory for general search (default: %%TEMP%%)")
    parser.add_argument("--name", dest="model_name", default=None, help="Specific Industry Model name to search for (optional)")
    parser.add_argument("--out", dest="output_sql", default=None, help="Generated SQL file (default: schema_<dbname>.sql)")

    # PostgreSQL parameters
    parser.add_argument("--pg-host", dest="pg_host", default="localhost", help="PostgreSQL server host (default: localhost)")
    parser.add_argument("--pg-port", dest="pg_port", type=int, default=5432, help="PostgreSQL port (default: 5432)")
    parser.add_argument("--pg-user", dest="pg_user", default=os.getenv("PG_USER"), help="PostgreSQL username (e.g. postgres)")
    parser.add_argument("--pg-pass", dest="pg_pass", default=os.getenv("PG_PASSWORD"), help="PostgreSQL password")
    parser.add_argument("--pg-db", dest="pg_db", default=None, help="Target PostgreSQL database name (optional)")

    parser.add_argument("--srid", type=int, default=2154, help="EPSG / SRID spatial code for PostGIS (default: 2154)")
    parser.add_argument("--initial-sync", action="store_true", help="Execute an immediate synchronization at startup.")

    # V2 options
    parser.add_argument("--sync-data", dest="sync_data", action="store_true", default=True,
                        help="Enable data synchronization (upsert) in addition to schema sync (default: True).")
    parser.add_argument("--no-sync-data", dest="sync_data", action="store_false",
                        help="Disable data synchronization (only sync schema).")
    parser.add_argument("--allow-drop", dest="allow_drop", action="store_true", default=False,
                        help="Automatically drop PostgreSQL columns/tables that were deleted from the Autodesk Industry Model.")
    parser.add_argument("--log-file", dest="log_file", default="connector_sync.log",
                        help="Path to log file (default: connector_sync.log)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose/debug logging")

    args = parser.parse_args()

    setup_logging(log_file=args.log_file, verbose=args.verbose)

    watch_file(
        sqlite_path=args.sqlite_file,
        search_dir=args.search_dir,
        model_name=args.model_name,
        output_sql=args.output_sql,
        pg_host=args.pg_host,
        pg_port=args.pg_port,
        pg_user=args.pg_user,
        pg_pass=args.pg_pass,
        pg_db=args.pg_db,
        srid=args.srid,
        run_initial_sync=args.initial_sync,
        sync_data_flag=args.sync_data,
        allow_drop=args.allow_drop
    )
