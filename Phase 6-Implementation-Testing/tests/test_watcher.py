# -*- coding: utf-8 -*-
"""
===============================================================================
PROJECT : Autocad-map-3d-PostgreSQL-Connector
MODULE  : Integration tests for watch_and_sync.py
===============================================================================
"""

import sys
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from watch_and_sync import (
    is_autodesk_sqlite,
    detect_schema_differences,
    sync_data,
    clean_postgres_db_name,
    split_sql_statements
)


def test_is_autodesk_sqlite(temp_sqlite_file):
    """Test identification of valid Autodesk SQLite file."""
    conn = sqlite3.connect(temp_sqlite_file)
    cur = conn.cursor()
    cur.execute("INSERT INTO TB_DICTIONARY (F_CLASS_ID, F_CLASS_NAME) VALUES (1, 'TEST');")
    conn.commit()
    conn.close()

    assert is_autodesk_sqlite(temp_sqlite_file) is True


def test_is_not_autodesk_sqlite(tmp_path):
    """Test rejection of non-Autodesk file."""
    non_autodesk = tmp_path / "regular.sqlite"
    conn = sqlite3.connect(str(non_autodesk))
    cur = conn.cursor()
    cur.execute("CREATE TABLE foo (id INT);")
    conn.commit()
    conn.close()

    assert is_autodesk_sqlite(str(non_autodesk)) is False


def test_clean_postgres_db_name():
    """Test cleaning of database names."""
    assert clean_postgres_db_name("Modèle Eau & Assainissement") == "modele_eau_assainissement"
    assert clean_postgres_db_name("My-Database_v1.0!") == "my_database_v1_0"
    assert clean_postgres_db_name("") == ""


def test_detect_schema_differences(temp_sqlite_file, mock_pg_conn):
    """Test schema difference detection with mocked PG connection."""
    conn = sqlite3.connect(temp_sqlite_file)
    cur = conn.cursor()
    cur.execute("INSERT INTO TB_DICTIONARY (F_CLASS_ID, F_CLASS_NAME, F_CLASS_TYPE) VALUES (1, 'V_TEST', 'N');")
    cur.execute("CREATE TABLE V_TEST (FID INTEGER PRIMARY KEY, COL_A TEXT, COL_B INTEGER);")
    conn.commit()
    conn.close()

    # Mock PG responses:
    # 1. EXISTS query -> True
    # 2. PG tables query -> [("V_TEST",)]
    # 3. PG columns query -> return COL_A and COL_ORPHAN (COL_B missing in PG, COL_ORPHAN extra in PG)
    pg_cursor = mock_pg_conn.cursor.return_value
    pg_cursor.fetchone.side_effect = [(True,)]
    pg_cursor.fetchall.side_effect = [
        [("V_TEST",)],
        [("COL_A", "text"), ("COL_ORPHAN", "varchar")]
    ]

    report = detect_schema_differences(temp_sqlite_file, mock_pg_conn)
    assert "V_TEST" in report
    assert "COL_B" in report["V_TEST"]["missing_in_pg"]
    assert "COL_ORPHAN" in report["V_TEST"]["orphan_in_pg"]


def test_sync_data(temp_sqlite_file, mock_pg_conn):
    """Test data synchronization (upsert) with mocked PG connection."""
    conn = sqlite3.connect(temp_sqlite_file)
    cur = conn.cursor()
    cur.execute("INSERT INTO TB_DICTIONARY (F_CLASS_ID, F_CLASS_NAME, F_CLASS_TYPE) VALUES (1, 'V_TEST_DATA', 'N');")
    cur.execute("CREATE TABLE V_TEST_DATA (FID INTEGER PRIMARY KEY, NAME TEXT);")
    cur.execute("INSERT INTO V_TEST_DATA VALUES (1, 'Item 1');")
    cur.execute("INSERT INTO V_TEST_DATA VALUES (2, 'Item 2');")
    conn.commit()
    conn.close()

    pg_cursor = mock_pg_conn.cursor.return_value
    pg_cursor.fetchone.return_value = (True,)

    sync_data(temp_sqlite_file, mock_pg_conn)

    # Verify execute was called with upsert query
    assert pg_cursor.execute.call_count >= 2
    first_call_sql = pg_cursor.execute.call_args_list[1][0][0]
    assert 'INSERT INTO "V_TEST_DATA"' in first_call_sql
    assert 'ON CONFLICT ("FID") DO UPDATE' in first_call_sql


def test_split_sql_statements():
    """Test robust SQL statement splitting."""
    sql = """
    CREATE TABLE t1 (id INT);
    -- line comment;
    CREATE OR REPLACE FUNCTION fn() RETURNS TRIGGER AS $$
    BEGIN
        NEW.val := 1;
    END;
    $$ LANGUAGE plpgsql;
    INSERT INTO t1 VALUES (1);
    """
    stmts = split_sql_statements(sql)
    assert len(stmts) == 3
    assert "CREATE TABLE t1" in stmts[0]
    assert "fn_calc" not in stmts[1] and "$$" in stmts[1]
    assert "INSERT INTO t1" in stmts[2]
