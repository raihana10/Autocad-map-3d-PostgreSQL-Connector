# -*- coding: utf-8 -*-
"""
===============================================================================
PROJECT : Autocad-map-3d-PostgreSQL-Connector
MODULE  : Unit tests for multiple inheritance support in convert_autodesk_to_postgis.py
===============================================================================
"""

import sys
import sqlite3
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from convert_autodesk_to_postgis import (
    generate_postgis_ddl,
    get_autodesk_classes,
    resolve_inheritance,
    get_inherited_columns
)


def test_multiple_inheritance(temp_sqlite_file):
    """
    Test basic inheritance:
    - Parent (V_ASSET): F_CLASS_ID=10, has column 'ASSET_NUM'
    - Child (V_PUMP_STATION): F_CLASS_ID=100, inherits from Parent (MODEL_F_CLASS_ID=10)
    - Verification: Child table DDL includes inherited column 'ASSET_NUM'
    """
    conn = sqlite3.connect(temp_sqlite_file)
    cur = conn.cursor()

    cur.execute("INSERT INTO TB_DICTIONARY (F_CLASS_ID, F_CLASS_NAME, F_CLASS_TYPE) VALUES (10, 'V_ASSET', 'N');")
    cur.execute("INSERT INTO TB_DICTIONARY (F_CLASS_ID, F_CLASS_NAME, F_CLASS_TYPE, MODEL_F_CLASS_ID) VALUES (100, 'V_PUMP_STATION', 'N', 10);")

    cur.execute("CREATE TABLE V_ASSET (FID INTEGER PRIMARY KEY, ASSET_NUM TEXT);")
    cur.execute("CREATE TABLE V_PUMP_STATION (FID INTEGER PRIMARY KEY, FLOW_RATE REAL);")

    conn.commit()
    conn.close()

    conn = sqlite3.connect(temp_sqlite_file)
    classes = get_autodesk_classes(conn)
    inheritance_map = resolve_inheritance(classes, conn)

    assert 100 in inheritance_map
    assert 10 in inheritance_map[100]

    conn.close()

    ddl = generate_postgis_ddl(temp_sqlite_file)
    assert 'CREATE TABLE IF NOT EXISTS "V_PUMP_STATION"' in ddl
    assert '"ASSET_NUM" text' in ddl
    assert '"FLOW_RATE" double precision' in ddl


def test_column_name_conflict_resolution(temp_sqlite_file):
    """
    Test conflict resolution in multiple inheritance:
    - Parent A (V_PARENT_A): has column 'ID' and 'NAME'
    - Parent B (V_PARENT_B): has column 'ID' and 'NAME'
    - Child (V_CHILD): inherits from Parent A and Parent B
    - Verification: get_inherited_columns renames conflicting columns to V_PARENT_A_ID, V_PARENT_B_ID, etc.
    """
    conn = sqlite3.connect(temp_sqlite_file)
    cur = conn.cursor()

    cur.execute("CREATE TABLE V_PARENT_A (FID INTEGER PRIMARY KEY, ID TEXT, NAME TEXT, CODE_A TEXT);")
    cur.execute("CREATE TABLE V_PARENT_B (FID INTEGER PRIMARY KEY, ID TEXT, NAME TEXT, CODE_B TEXT);")

    conn.commit()

    classes = {
        1: {"name": "V_PARENT_A", "type": "N", "parent_id": None},
        2: {"name": "V_PARENT_B", "type": "N", "parent_id": None},
        3: {"name": "V_CHILD", "type": "N", "parent_id": 1}
    }
    # Multiple parents for child 3: [1, 2]
    inheritance_map = {3: [1, 2]}

    merged_cols = get_inherited_columns(3, classes, inheritance_map, conn)
    conn.close()

    # Non-conflicting columns kept as-is
    assert "CODE_A" in merged_cols
    assert "CODE_B" in merged_cols

    # Conflicting columns renamed with parent prefix
    assert "V_PARENT_A_ID" in merged_cols
    assert "V_PARENT_B_ID" in merged_cols
    assert "V_PARENT_A_NAME" in merged_cols
    assert "V_PARENT_B_NAME" in merged_cols

    assert merged_cols["V_PARENT_A_ID"]["name"] == "V_PARENT_A_ID"
    assert merged_cols["V_PARENT_B_ID"]["name"] == "V_PARENT_B_ID"
