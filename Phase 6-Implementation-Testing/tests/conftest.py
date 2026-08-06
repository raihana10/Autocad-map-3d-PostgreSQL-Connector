# -*- coding: utf-8 -*-
"""
===============================================================================
PROJECT : Autocad-map-3d-PostgreSQL-Connector
MODULE  : pytest fixtures for unit and integration testing
===============================================================================
"""

import sqlite3
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def memory_sqlite_db():
    """
    Creates an in-memory SQLite database with minimal Autodesk Data Model catalog tables:
    - TB_DICTIONARY
    - fdo_columns
    - geometry_columns
    - TB_RELATIONS
    """
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # 1. TB_DICTIONARY
    cursor.execute("""
        CREATE TABLE "TB_DICTIONARY" (
            "F_CLASS_ID" INTEGER PRIMARY KEY,
            "F_CLASS_NAME" TEXT NOT NULL,
            "F_CLASS_TYPE" TEXT,
            "CAPTION" TEXT,
            "MODEL_F_CLASS_ID" INTEGER
        );
    """)

    # 2. fdo_columns
    cursor.execute("""
        CREATE TABLE "fdo_columns" (
            "featureclass_name" TEXT,
            "column_name" TEXT,
            "data_type" INTEGER,
            "data_length" INTEGER,
            "data_precision" INTEGER
        );
    """)

    # 3. geometry_columns
    cursor.execute("""
        CREATE TABLE "geometry_columns" (
            "f_table_name" TEXT,
            "f_geometry_column" TEXT,
            "geometry_type" INTEGER,
            "srid" INTEGER
        );
    """)

    # 4. TB_RELATIONS
    cursor.execute("""
        CREATE TABLE "TB_RELATIONS" (
            "parent_table_name" TEXT,
            "child_table_name" TEXT,
            "fk_column_name" TEXT,
            "merge_mode" TEXT,
            "split_mode" TEXT,
            "cardinality" TEXT,
            "relation_type" TEXT
        );
    """)

    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def temp_sqlite_file(tmp_path, memory_sqlite_db):
    """
    Writes a minimal Autodesk SQLite database to a temporary file on disk.
    """
    db_path = tmp_path / "autodesk_model.sqlite"
    file_conn = sqlite3.connect(str(db_path))
    memory_sqlite_db.backup(file_conn)
    file_conn.close()
    return str(db_path)


@pytest.fixture
def mock_pg_conn():
    """
    Returns a mocked psycopg2 connection with cursor mock.
    """
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchone.return_value = (True,)
    cursor.fetchall.return_value = []
    return conn
