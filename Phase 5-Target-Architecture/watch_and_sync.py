#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
PROJECT : Autocad-map-3d-PostgreSQL-Connector
MODULE  : Background automation and monitoring service (File Watcher)
PHASE   : Phase 5 -- Automation of relaunch (A + E)
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

AUTOMATIC GENERAL SEARCH:
It performs a dynamic and generic search in the system temporary directory (%TEMP%)
or in a specified folder, without depending on a fixed or custom path.

===============================================================================
"""

import os
import sys
import time
import glob
import sqlite3
import tempfile
import subprocess
import argparse
from pathlib import Path

# Force UTF-8 encoding for Windows console to avoid charmap errors
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Check interval in seconds
CHECK_INTERVAL_SECONDS = 2


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
    Uses an mtime-based cache to avoid re-reading the file unnecessarily
    and to limit repetitive logs.
    """
    try:
        if not os.path.isfile(file_path):
            return False
            
        mtime = os.path.getmtime(file_path)
        if file_path in _ANALYZED_SQLITES:
            cached_mtime, cached_val = _ANALYZED_SQLITES[file_path]
            if cached_mtime == mtime:
                return cached_val

        # Level 1: exclusion by extension (0.001 ms)
        ext = Path(file_path).suffix.lower()
        if ext in _NON_SQLITE_EXTS:
            _ANALYZED_SQLITES[file_path] = (mtime, False)
            return False

        # Level 2: exclusion of Autodesk system files
        fname = Path(file_path).name.lower()
        if "tbsys" in fname or "system" in fname:
            _ANALYZED_SQLITES[file_path] = (mtime, False)
            return False

        # Level 3: reading the 16-byte SQLite magic header (0.01 ms)
        try:
            with open(file_path, "rb") as f:
                header = f.read(16)
            if header != _SQLITE_MAGIC:
                _ANALYZED_SQLITES[file_path] = (mtime, False)
                return False
        except (OSError, PermissionError):
            return False

        # Log the exact path where the script identifies an Industry Model candidate
        print(f"[SCAN] Examining candidate SQLite file: {file_path}")

        # Level 4: check for TB_DICTIONARY table (unique to Autodesk Data Models)
        conn = sqlite3.connect(file_path, timeout=2.0)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='TB_DICTIONARY';")
        has_tb_dict = cursor.fetchone() is not None
        conn.close()
        
        if has_tb_dict:
            print(f"    +-- [OK] System table 'TB_DICTIONARY' found in database.")
            print(f"    +-- [OK] Identified as a valid Autodesk Industry Model.")
        else:
            print(f"    +-- [SKIP] Table 'TB_DICTIONARY' absent (not an Industry Model).")

        _ANALYZED_SQLITES[file_path] = (mtime, has_tb_dict)
        return has_tb_dict
    except Exception:
        return False


def find_autodesk_sqlite(search_dir: str = None, model_name: str = None) -> str:
    """
    Performs a general and dynamic search for an Autodesk SQLite file.
    - search_dir: root directory to search (default: system %TEMP%).
    - model_name: specific Industry Model name (optional).
    
    Returns the path of the most recently modified valid file.
    """
    base_dir = search_dir if search_dir else tempfile.gettempdir()
    print(f"[SCAN] General search in: {base_dir}")
    
    candidates = []
    
    # Recursive traversal of subdirectories
    for root, _, files in os.walk(base_dir):
        for f in files:
            # Optional filtering by name if specified
            if model_name and model_name.lower() not in f.lower() and model_name.lower() not in root.lower():
                continue
                
            full_path = os.path.join(root, f)
            
            # Check if it is a valid Autodesk SQLite file
            if is_autodesk_sqlite(full_path):
                mtime = os.path.getmtime(full_path)
                candidates.append((mtime, full_path))
                
    if not candidates:
        return None
        
    # Sort by modification date (most recent first)
    candidates.sort(key=lambda x: x[0], reverse=True)
    latest_file = candidates[0][1]
    return latest_file


def clean_postgres_db_name(name: str) -> str:
    """
    Cleans and formats a string to be a valid PostgreSQL database name.
    """
    if not name:
        return ""
    import re
    import unicodedata
    
    # Normalize to remove accents (e.g. donne -> donne)
    nfkd_form = unicodedata.normalize('NFKD', name)
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('ASCII')
    
    # Convert to lowercase
    cleaned = only_ascii.lower()
    # Replace any non-alphanumeric character with underscores
    cleaned = re.sub(r'[^a-z0-9]+', '_', cleaned)
    # Remove multiple or trailing underscores
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    
    return cleaned


def get_industry_model_name(sqlite_path: str) -> str:
    """
    Reads the Industry Model name from the Autodesk system table 'TB_INFO'.
    Returns None if the table or 'DOCUMENT_NAME' key does not exist.
    """
    try:
        if not os.path.isfile(sqlite_path):
            return None
        conn = sqlite3.connect(sqlite_path, timeout=5.0)
        cursor = conn.cursor()
        # First check if TB_INFO table exists to avoid raising an unnecessary exception
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
        print(f"[WARNING] Note while retrieving model name (TB_INFO): {e}")
    return None


def sync_table_columns(sqlite_path: str, pg_conn, default_srid=2154):
    """
    Dynamically synchronizes table columns from SQLite to PostgreSQL.
    For each column present in SQLite but absent in PostgreSQL,
    issues an ALTER TABLE ADD COLUMN command with the correct type.
    """
    try:
        sq_conn = sqlite3.connect(sqlite_path)
        sq_cursor = sq_conn.cursor()
        
        # If TB_DICTIONARY does not exist, this is not a valid Autodesk SQLite
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
            
            # Check if the table exists in PostgreSQL (respecting exact case)
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
                
                # Geometry column case
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
                
                print(f"[ALTER TABLE] Attribute detected in SQLite but missing in PostgreSQL: table '{tbl_name}', column '{col_name}' ({pg_type})")
                alter_stmt = f'ALTER TABLE "{tbl_name}" ADD COLUMN "{col_name}" {pg_type}'
                if pinfo["default"] is not None:
                    alter_stmt += f" DEFAULT {pinfo['default']}"
                
                try:
                    pg_cursor.execute(alter_stmt + ";")
                    print(f"    +-- [OK] Column '{col_name}' added successfully.")
                except Exception as ex:
                    print(f"    +-- [FAIL] Failed to add column '{col_name}': {ex}")
                    
        pg_conn.commit()
        sq_conn.close()
    except Exception as e:
        print(f"[WARNING] Note during dynamic column synchronization: {e}")


def ensure_pg_database_exists(host="localhost", port=5432, user="postgres", password="", dbname="autocad_test"):
    """
    Checks if the PostgreSQL database exists, and creates it automatically if needed.
    """
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
        
        # 1. Connect to the default 'postgres' database
        conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname="postgres")
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # 2. Check if the target database exists
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s;", (dbname,))
        exists = cursor.fetchone()
        
        if not exists:
            print(f"[INFO] Database '{dbname}' does not exist yet. Creating automatically...")
            cursor.execute(f'CREATE DATABASE "{dbname}";')
            print(f"[OK] Database '{dbname}' created successfully!")
            
            # Enable PostGIS extension on the new database
            conn_new = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname)
            cursor_new = conn_new.cursor()
            cursor_new.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
            conn_new.commit()
            cursor_new.close()
            conn_new.close()
            print(f"[OK] PostGIS extension enabled on '{dbname}'.")
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[WARNING] Note while checking PostgreSQL database: {e}")


def run_conversion_and_apply(sqlite_path: str, output_sql: str, pg_host="localhost", pg_port=5432, pg_user="postgres", pg_pass="", pg_db=None, srid: int = 2154):
    """
    Executes the conversion script and applies the DDL directly to PostgreSQL.
    """
    print(f"\n[AUTO-SYNC] Modification detected in {Path(sqlite_path).name}!")
    print(f"[INFO] Launching Python converter automatically...")
    
    # If no DB name is provided, attempt to retrieve it from the filename or system table
    if not pg_db:
        model_name = get_industry_model_name(sqlite_path)
        if model_name:
            cleaned_db = clean_postgres_db_name(model_name)
            if cleaned_db:
                print(f"[INFO] Autodesk Industry Model detected in SQLite: '{model_name}' -> Target PostgreSQL database: '{cleaned_db}'")
                pg_db = cleaned_db
            else:
                pg_db = clean_postgres_db_name(Path(sqlite_path).stem)
        else:
            pg_db = clean_postgres_db_name(Path(sqlite_path).stem)
        
    script_dir = Path(__file__).parent
    converter_script = script_dir / "convert_autodesk_to_postgis.py"
    
    cmd = [
        sys.executable,
        str(converter_script),
        "--db", sqlite_path,
        "--out", output_sql,
        "--srid", str(srid)
    ]
    
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    
    if result.returncode == 0:
        print(f"[OK] DDL conversion successful -> {output_sql}")
        
        if pg_user and pg_pass:
            try:
                import psycopg2
                
                # Ensure the database exists
                ensure_pg_database_exists(host=pg_host, port=pg_port, user=pg_user, password=pg_pass, dbname=pg_db)
                
                print(f"[INFO] Automatically applying DDL to database '{pg_db}' ({pg_host}:{pg_port})...")
                conn = psycopg2.connect(host=pg_host, port=pg_port, user=pg_user, password=pg_pass, dbname=pg_db)
                conn.autocommit = True
                cursor = conn.cursor()
                sql_content = Path(output_sql).read_text(encoding="utf-8")
                
                # SQL statement execution with detailed logging
                success_count = 0
                created_tables = []
                created_domains = []
                created_indexes = []
                created_fks = 0
                created_triggers = []
                failed_statements = []
                
                print("\n[SCHEMA APPLICATION START - POSTGRESQL]")
                
                # Retrieve current state of the PostgreSQL database to only display new elements
                cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
                existing_pg_tables = {row[0].upper() for row in cursor.fetchall()}
                
                cursor.execute("SELECT indexname FROM pg_indexes WHERE schemaname = 'public';")
                existing_pg_indexes = {row[0].upper() for row in cursor.fetchall()}
                
                cursor.execute("SELECT trigger_name FROM information_schema.triggers WHERE trigger_schema = 'public';")
                existing_pg_triggers = {row[0].upper() for row in cursor.fetchall()}
                
                for stmt_clean in split_sql_statements(sql_content):
                    stmt_upper = stmt_clean.upper()
                    try:
                        cursor.execute(stmt_clean + ";")
                        conn.commit()
                        success_count += 1

                        # Detect query type for detailed display (only if element did not exist before)
                        if "CREATE TABLE IF NOT EXISTS" in stmt_upper or "CREATE TABLE" in stmt_upper:
                            parts = stmt_clean.split('"')
                            tname = parts[1] if len(parts) > 1 else "Table"
                            tname_upper = tname.upper()
                            if tname_upper not in existing_pg_tables:
                                existing_pg_tables.add(tname_upper)
                                if tname.endswith("_TBD") or tname == "TB_DOMAIN":
                                    created_domains.append(tname)
                                    print(f"    [Domain Table]  '{tname}' created (new)")
                                else:
                                    created_tables.append(tname)
                                    print(f"    [Feature Class] '{tname}' created (new)")
                        elif "CREATE INDEX" in stmt_upper:
                            parts = stmt_clean.split('"')
                            idx_name = parts[1] if len(parts) > 1 else "Index"
                            idx_upper = idx_name.upper()
                            if idx_upper not in existing_pg_indexes:
                                existing_pg_indexes.add(idx_upper)
                                created_indexes.append(idx_name)
                                print(f"    [Spatial Index]  '{idx_name}' created (new)")
                        elif "FOREIGN KEY" in stmt_upper:
                            created_fks += 1
                        elif "CREATE TRIGGER" in stmt_upper:
                            parts = stmt_clean.split('"')
                            trg_name = parts[1] if len(parts) > 1 else "Trigger"
                            trg_upper = trg_name.upper()
                            if trg_upper not in existing_pg_triggers:
                                existing_pg_triggers.add(trg_upper)
                                created_triggers.append(trg_name)
                                print(f"    [Trigger PL/pgSQL] '{trg_name}' activated (new)")
                    except Exception as ex:
                        conn.rollback()
                        first_line = stmt_clean.splitlines()[0][:120]
                        failed_statements.append((first_line, str(ex)))
                        print(f"    [SQL ERROR] {first_line}")
                        print(f"         -> {ex}")
                            
                # Launch dynamic column synchronization (ALTER TABLE)
                print("\n[ATTRIBUTE SYNCHRONIZATION]")
                sync_table_columns(sqlite_path, conn, srid)
                
                cursor.close()
                conn.close()
                
                print("\n[SUMMARY OF TABLES AND ELEMENTS CREATED IN DATABASE]")
                print(f"    Feature Classes (Business): {len(created_tables)} table(s)")
                if created_tables:
                    print(f"       -> {', '.join(created_tables)}")
                print(f"    Domain Tables (_TBD):       {len(created_domains)} table(s)")
                if created_domains:
                    print(f"       -> {', '.join(created_domains)}")
                print(f"    GiST Spatial Indexes:       {len(created_indexes)} index(es)")
                print(f"    Foreign Keys (FK):          {created_fks} constraint(s)")
                print(f"    PL/pgSQL Spatial Triggers:  {len(created_triggers)} trigger(s)")
                if failed_statements:
                    print(f"    Failed Statements:          {len(failed_statements)}")
                    print(f"[WARNING] Partial synchronization ({success_count} SQL queries executed, {len(failed_statements)} failed).\n")
                else:
                    print(f"[OK] PostgreSQL synchronization 100% successful ({success_count} SQL queries executed)!\n")
            except ImportError:
                print("[INFO] Module 'psycopg2' not installed. Install it with: pip install psycopg2-binary")
            except Exception as e:
                print(f"[ERROR] Error while applying to PostgreSQL: {e}")
        else:
            print("[INFO] No PostgreSQL credentials provided. Only the SQL file was generated.")
    else:
        print(f"[ERROR] DDL conversion failed: {result.stderr}")


def find_all_autodesk_sqlites(search_dir: str = None, model_name: str = None) -> list:
    """
    Scans the temporary directory (%TEMP% by default) and returns ALL valid Autodesk SQLite files.
    Each model is associated with a unique and clean PostgreSQL database name.
    """
    base_dir = search_dir if search_dir else tempfile.gettempdir()
    found_models = []
    seen_paths = set()
    used_db_names = {}  # db_name -> count for deduplication
    
    for root, _, files in os.walk(base_dir):
        for f in files:
            if model_name and model_name.lower() not in f.lower() and model_name.lower() not in root.lower():
                continue
                
            full_path = os.path.join(root, f)
            if full_path in seen_paths:
                continue
                
            if is_autodesk_sqlite(full_path):
                seen_paths.add(full_path)
                
                # Priority to the Data Model filename (stem) for readability
                file_stem = Path(full_path).stem
                
                # If the filename is too generic ("Drawing1", "datamodel"), infer from folder or TB_INFO
                if file_stem.lower().startswith("drawing") or file_stem.lower() == "datamodel":
                    doc_name = get_industry_model_name(full_path)
                    if doc_name and doc_name.lower() != "industry model 1":
                        raw_name = doc_name
                    else:
                        # Use the parent GUID folder name
                        parent_name = Path(full_path).parent.name
                        raw_name = f"{file_stem}_{parent_name[:6]}"
                else:
                    raw_name = file_stem
                    
                db_name = clean_postgres_db_name(raw_name)
                if not db_name:
                    db_name = "industry_model"
                    
                # Deduplicate DB names if two physical files generate the same name
                if db_name in used_db_names:
                    used_db_names[db_name] += 1
                    db_name = f"{db_name}_{used_db_names[db_name]}"
                else:
                    used_db_names[db_name] = 1
                    
                mtime = os.path.getmtime(full_path)
                output_sql = f"schema_{db_name}.sql"
                
                found_models.append({
                    "path": full_path,
                    "model_name": raw_name,
                    "db_name": db_name,
                    "output_sql": output_sql,
                    "mtime": mtime
                })
                
    return found_models


def watch_file(sqlite_path: str = None, search_dir: str = None, model_name: str = None, output_sql: str = None, pg_host="localhost", pg_port=5432, pg_user=None, pg_pass=None, pg_db=None, srid: int = 2154, run_initial_sync: bool = False):
    """
    Multi-model monitoring service (Multi-Watcher):
    Simultaneously monitors ALL active Autodesk Industry Models in %TEMP% (or a target model).
    Each model is synchronized to its own dedicated PostgreSQL database without interference.
    """
    print("===================================================================")
    print(" AUTODESK MULTI-MODEL AUTOMATIC MONITORING SERVICE")
    print("===================================================================")
    print(f"[SCAN] Monitoring zone: {search_dir or tempfile.gettempdir()}")
    print(f"[INFO] Check frequency: Every {CHECK_INTERVAL_SECONDS} seconds.")
    if pg_user and pg_pass:
        print("[INFO] Mode: DDL generation + automatic PostgreSQL application (dedicated databases per model)")
    else:
        print("[INFO] Mode: DDL file generation only")
    print("[Press CTRL+C to stop the service]\n")

    # Indexed by ABSOLUTE FILE PATH (full_path) -> no conflict or infinite loop!
    monitored = {}  # full_path -> { "db_name": ..., "mtime": ..., "output_sql": ... }
    
    # First detection pass
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
        print("[WARNING] No active Autodesk Industry Model found at this time.")
        print("[WATCH] Service is waiting for a Data Model to be opened...\n")

    for m in initial_list:
        fpath = m["path"]
        db = m["db_name"]
        print(f"[INDUSTRY MODEL DETECTED] '{m['model_name']}'")
        print(f"    +-- SQLite source  : {fpath}")
        print(f"    +-- PostgreSQL DB  : '{db}'")
        print(f"    +-- DDL file       : '{m['output_sql']}'\n")
        
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
                srid=srid
            )
            
    try:
        heartbeat_counter = 0
        HEARTBEAT_EVERY = 5  # Display a status message every N iterations (~10s)

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

                # New SQLite file discovered during execution
                if fpath not in monitored:
                    any_change = True
                    print(f"\n[NEW DATA MODEL DETECTED] '{m['model_name']}'")
                    print(f"    +-- SQLite source  : {fpath}")
                    print(f"    +-- PostgreSQL DB  : '{db}'")
                    print(f"    +-- DDL file       : '{out_sql}'")

                    monitored[fpath] = {
                        "db_name": db,
                        "mtime": curr_mtime,
                        "output_sql": out_sql
                    }

                    run_conversion_and_apply(
                        sqlite_path=fpath,
                        output_sql=out_sql,
                        pg_host=pg_host,
                        pg_port=pg_port,
                        pg_user=pg_user,
                        pg_pass=pg_pass,
                        pg_db=db,
                        srid=srid
                    )
                # Existing model that has been modified by the user
                elif curr_mtime != monitored[fpath]["mtime"]:
                    any_change = True
                    monitored[fpath]["mtime"] = curr_mtime
                    run_conversion_and_apply(
                        sqlite_path=fpath,
                        output_sql=out_sql,
                        pg_host=pg_host,
                        pg_port=pg_port,
                        pg_user=pg_user,
                        pg_pass=pg_pass,
                        pg_db=db,
                        srid=srid
                    )

            # Heartbeat: presence log every N seconds if no modification
            if not any_change and heartbeat_counter >= HEARTBEAT_EVERY:
                heartbeat_counter = 0
                ts = time.strftime("%H:%M:%S")
                print(f"[WATCH {ts}] Active monitoring -- {len(monitored)} model(s) under observation. Waiting for modifications...")

    except KeyboardInterrupt:
        print("\n[STOP] Multi-model automatic monitoring service stopped.")


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

    args = parser.parse_args()

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
        run_initial_sync=args.initial_sync
    )
