# -*- coding: utf-8 -*-
"""
===============================================================================
PROJECT : Autocad-map-3d-PostgreSQL-Connector
MODULE  : Unit tests for convert_autodesk_to_postgis.py
===============================================================================
"""

import sys
import sqlite3
import pytest
from pathlib import Path

# Add parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from convert_autodesk_to_postgis import (
    generate_postgis_ddl,
    get_autodesk_classes,
    get_fdo_column_metadata,
    get_spatial_metadata,
    get_autodesk_relations,
    get_domain_tables,
    FDO_TO_POSTGRES_TYPES
)


def test_simple_class_ddl(temp_sqlite_file):
    """Test 1: Simple feature class generates valid CREATE TABLE."""
    conn = sqlite3.connect(temp_sqlite_file)
    cur = conn.cursor()
    cur.execute("INSERT INTO TB_DICTIONARY (F_CLASS_ID, F_CLASS_NAME, F_CLASS_TYPE, CAPTION) VALUES (1, 'V_PIPE', 'N', 'Pipe');")
    cur.execute("CREATE TABLE V_PIPE (FID INTEGER PRIMARY KEY, NAME TEXT);")
    conn.commit()
    conn.close()

    ddl = generate_postgis_ddl(temp_sqlite_file)
    assert 'CREATE TABLE IF NOT EXISTS "V_PIPE"' in ddl
    assert '"FID" integer NOT NULL' in ddl
    assert 'PRIMARY KEY ("FID")' in ddl


def test_varchar_length_attribute(temp_sqlite_file):
    """Test 2: Text attribute with length generates VARCHAR(10)."""
    conn = sqlite3.connect(temp_sqlite_file)
    cur = conn.cursor()
    cur.execute("INSERT INTO TB_DICTIONARY (F_CLASS_ID, F_CLASS_NAME, F_CLASS_TYPE) VALUES (1, 'V_VALVE', 'N');")
    cur.execute("INSERT INTO fdo_columns (featureclass_name, column_name, data_type, data_length) VALUES ('V_VALVE', 'CODE', 9, 10);")
    cur.execute("CREATE TABLE V_VALVE (FID INTEGER PRIMARY KEY, CODE TEXT);")
    conn.commit()
    conn.close()

    ddl = generate_postgis_ddl(temp_sqlite_file)
    assert '"CODE" varchar(10)' in ddl


def test_integer_attribute(temp_sqlite_file):
    """Test 3: Numeric attribute (FDO 6 = Int32) generates INTEGER."""
    conn = sqlite3.connect(temp_sqlite_file)
    cur = conn.cursor()
    cur.execute("INSERT INTO TB_DICTIONARY (F_CLASS_ID, F_CLASS_NAME, F_CLASS_TYPE) VALUES (1, 'V_PUMP', 'N');")
    cur.execute("INSERT INTO fdo_columns (featureclass_name, column_name, data_type) VALUES ('V_PUMP', 'POWER', 6);")
    cur.execute("CREATE TABLE V_PUMP (FID INTEGER PRIMARY KEY, POWER INTEGER);")
    conn.commit()
    conn.close()

    ddl = generate_postgis_ddl(temp_sqlite_file)
    assert '"POWER" integer' in ddl


def test_default_value(temp_sqlite_file):
    """Test 4: Default value in SQLite generates DEFAULT clause."""
    conn = sqlite3.connect(temp_sqlite_file)
    cur = conn.cursor()
    cur.execute("INSERT INTO TB_DICTIONARY (F_CLASS_ID, F_CLASS_NAME, F_CLASS_TYPE) VALUES (1, 'V_METER', 'N');")
    cur.execute("CREATE TABLE V_METER (FID INTEGER PRIMARY KEY, STATUS TEXT DEFAULT 'ACTIVE');")
    conn.commit()
    conn.close()

    ddl = generate_postgis_ddl(temp_sqlite_file)
    assert "DEFAULT 'ACTIVE'" in ddl


def test_not_null_constraint(temp_sqlite_file):
    """Test 5: NOT NULL column in SQLite generates NOT NULL in DDL."""
    conn = sqlite3.connect(temp_sqlite_file)
    cur = conn.cursor()
    cur.execute("INSERT INTO TB_DICTIONARY (F_CLASS_ID, F_CLASS_NAME, F_CLASS_TYPE) VALUES (1, 'V_NODE', 'N');")
    cur.execute("CREATE TABLE V_NODE (FID INTEGER PRIMARY KEY, SERIAL_NUM TEXT NOT NULL);")
    conn.commit()
    conn.close()

    ddl = generate_postgis_ddl(temp_sqlite_file)
    assert '"SERIAL_NUM" text NOT NULL' in ddl


def test_point_geometry(temp_sqlite_file):
    """Test 6: Point geometry class generates geometry(Point, 2154)."""
    conn = sqlite3.connect(temp_sqlite_file)
    cur = conn.cursor()
    cur.execute("INSERT INTO TB_DICTIONARY (F_CLASS_ID, F_CLASS_NAME, F_CLASS_TYPE) VALUES (1, 'V_HYDRANT', 'P');")
    cur.execute("INSERT INTO geometry_columns (f_table_name, f_geometry_column, geometry_type, srid) VALUES ('V_HYDRANT', 'GEOM', 1, 2154);")
    cur.execute("CREATE TABLE V_HYDRANT (FID INTEGER PRIMARY KEY, GEOM BLOB);")
    conn.commit()
    conn.close()

    ddl = generate_postgis_ddl(temp_sqlite_file)
    assert '"GEOM" geometry(Point, 2154)' in ddl
    assert 'CREATE INDEX IF NOT EXISTS "idx_V_HYDRANT_GEOM_gist"' in ddl


def test_line_geometry_trigger(temp_sqlite_file):
    """Test 7: Line geometry class generates PL/pgSQL trigger for ST_Length."""
    conn = sqlite3.connect(temp_sqlite_file)
    cur = conn.cursor()
    cur.execute("INSERT INTO TB_DICTIONARY (F_CLASS_ID, F_CLASS_NAME, F_CLASS_TYPE) VALUES (1, 'V_PIPE_LINE', 'L');")
    cur.execute("INSERT INTO geometry_columns (f_table_name, f_geometry_column, geometry_type, srid) VALUES ('V_PIPE_LINE', 'GEOM', 2, 2154);")
    cur.execute("CREATE TABLE V_PIPE_LINE (FID INTEGER PRIMARY KEY, GEOM BLOB, LENGTH REAL);")
    conn.commit()
    conn.close()

    ddl = generate_postgis_ddl(temp_sqlite_file)
    assert 'fn_calc_autodesk_length()' in ddl
    assert 'CREATE TRIGGER "trg_calc_length_V_PIPE_LINE"' in ddl


def test_domain_table(temp_sqlite_file):
    """Test 8: Domain table (_TBD) generates CREATE TABLE and INSERT statements."""
    conn = sqlite3.connect(temp_sqlite_file)
    cur = conn.cursor()
    cur.execute("CREATE TABLE MAT_TBD (ID INTEGER PRIMARY KEY, VALUE TEXT);")
    cur.execute("INSERT INTO MAT_TBD VALUES (1, 'PVC');")
    cur.execute("INSERT INTO MAT_TBD VALUES (2, 'STEEL');")
    conn.commit()
    conn.close()

    ddl = generate_postgis_ddl(temp_sqlite_file)
    assert 'CREATE TABLE IF NOT EXISTS "MAT_TBD"' in ddl
    assert "INSERT INTO \"MAT_TBD\" (\"ID\", \"VALUE\") VALUES (1, 'PVC')" in ddl
    assert "INSERT INTO \"MAT_TBD\" (\"ID\", \"VALUE\") VALUES (2, 'STEEL')" in ddl


def test_relation_cardinality_comment(temp_sqlite_file):
    """Test 9: Relation with cardinality generates COMMENT ON CONSTRAINT."""
    conn = sqlite3.connect(temp_sqlite_file)
    cur = conn.cursor()
    cur.execute("INSERT INTO TB_DICTIONARY (F_CLASS_ID, F_CLASS_NAME, F_CLASS_TYPE) VALUES (1, 'V_PARENT', 'N');")
    cur.execute("INSERT INTO TB_DICTIONARY (F_CLASS_ID, F_CLASS_NAME, F_CLASS_TYPE) VALUES (2, 'V_CHILD', 'N');")
    cur.execute("CREATE TABLE V_PARENT (FID INTEGER PRIMARY KEY);")
    cur.execute("CREATE TABLE V_CHILD (FID INTEGER PRIMARY KEY, V_PARENT_ID INTEGER);")
    cur.execute("""
        INSERT INTO TB_RELATIONS (parent_table_name, child_table_name, fk_column_name, cardinality, merge_mode, split_mode)
        VALUES ('V_PARENT', 'V_CHILD', 'V_PARENT_ID', '1:N', 'MERGE_ALL', 'SPLIT_NONE');
    """)
    conn.commit()
    conn.close()

    ddl = generate_postgis_ddl(temp_sqlite_file)
    assert 'FOREIGN KEY ("V_PARENT_ID") REFERENCES "V_PARENT"' in ddl
    assert 'COMMENT ON CONSTRAINT "fk_V_CHILD_V_PARENT_ID_V_PARENT"' in ddl
    assert "Cardinality: 1:N" in ddl
    assert "MergeMode: MERGE_ALL" in ddl
