#!/usr/bin/env python3
"""
compare_sqlite.py
==================

Test 19 - Automated Autodesk Data Model analysis tool
------------------------------------------------------

Purpose
-------
Compare two successive SQLite exports (schema_testXX.sql / dump_testXX.sql)
generated from Infrastructure Administrator, and produce a structured report
of STRUCTURAL changes and DATA changes.

Why this architecture?
----------------------
We do NOT perform a textual diff (difflib) of the .sql files: a simple
reordering of lines, or an equivalent rewrite of a CREATE TABLE, would
produce false positives. We would not understand the SQL objects, only
their textual representation.

Instead, we load each .sql file into a temporary in-memory SQLite database
(":memory:"), and delegate parsing to SQLite itself via:

    - sqlite_master              -> tables, indexes, triggers, views (+ raw SQL)
    - PRAGMA table_info(table)   -> columns, types, NOT NULL, default, PK
    - PRAGMA foreign_key_list()  -> relationships between classes (Test 9)

This ensures we compare the LOGICAL structure, not the formatting.

For the dump (data), we load the file into its own in-memory database and
read rows via SELECT * FROM table. If a primary key exists, comparison is
done BY KEY (not by simple set membership), which allows detecting "modified
values" (implicit UPDATE) and not only added/removed rows.

Usage
-----
    python compare_sqlite.py schema_testN.sql schema_testN1.sql \\
                              dump_testN.sql   dump_testN1.sql \\
                              -o report_testN_vs_testN1.md

The 4 files are positional and in that order. The report is written in
Markdown, directly embeddable in a PFE thesis.
"""

import argparse
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# 1. Robust splitting of a SQL script into individual statements
# ---------------------------------------------------------------------------
_TRANSACTION_STARTERS = {"TRANSACTION", "DEFERRED", "IMMEDIATE", "EXCLUSIVE"}

# Detects Inf / -Inf / +Inf / Infinity / NaN tokens written WITHOUT quotes
# in a .sql file -- typical of an export containing bounding box coordinates
# that are "unbounded" (common in geomatics/FDO).
# In standard SQL, these are NOT valid numeric literals: without quotes,
# SQLite interprets them as column names, which causes the entire INSERT
# to fail with "no such column: Inf" and SILENTLY loses the corresponding
# data row (until the warning).
#
# (?<![\w'"]) / (?![\w'"]) : the token must not be adjacent to a letter,
# underscore, or quote -- which excludes both longer words
# (e.g. "Infrastructure") AND occurrences already correctly quoted
# (e.g. 'Inf' as a real text value), which do not need correction.
_SPECIAL_FLOAT_RE = re.compile(
    r"(?<![\w'\"])([+-]?(?:Infinity|Inf|NaN))(?![\w'\"])", re.IGNORECASE)


def normalize_special_floats(sql_text: str) -> str:
    """
    Rewrites unquoted Inf/-Inf/+Inf/Infinity/NaN tokens into valid text
    literals ('Inf', '-Inf', ...), so that the SQL statement remains
    executable and the value remains comparable between two exports (we
    lose the exact numeric semantics of infinity, but gain the ability
    to detect if the value has changed -- sufficient for a comparison
    tool, not for calculation).
    """
    return _SPECIAL_FLOAT_RE.sub(lambda m: f"'{m.group(1)}'", sql_text)



def _next_word_after(text: str, i: int) -> str:
    """
    Returns the next "word" (sequence of alphanumeric characters) after
    position i, skipping whitespace/newlines. Used to distinguish
    BEGIN TRANSACTION (which does NOT have a matching END -- it terminates
    with COMMIT/ROLLBACK) from the BEGIN that opens the body of a trigger
    or view (which terminates with END).
    """
    j = i
    n = len(text)
    while j < n and text[j].isspace():
        j += 1
    start = j
    while j < n and (text[j].isalnum() or text[j] == "_"):
        j += 1
    return text[start:j].upper()


def _match_keyword_at(text: str, i: int):
    """
    Checks if a SQL keyword (BEGIN, CASE, END) starts exactly at position
    i in `text`, respecting word boundaries (the character before and after
    must not be alphanumeric/underscore -- otherwise we would match "END"
    inside "APPEND" for example).

    Returns the keyword found ("BEGIN", "CASE" or "END") or None.

    Special case: "BEGIN TRANSACTION" (and its variants DEFERRED /
    IMMEDIATE / EXCLUSIVE) does NOT open a block in the sense we mean here
    -- this BEGIN terminates with COMMIT/ROLLBACK, never with END. Counting
    it as a BEGIN...END block would break the depth counting for the rest
    of the file (the real BEGIN...END of a trigger further down would never
    "close" this fake block). We detect it and treat it as a neutral keyword
    (ignored) rather than a block opener.
    """
    if i > 0 and (text[i - 1].isalnum() or text[i - 1] == "_"):
        return None
    for kw in ("BEGIN", "CASE", "END"):
        length = len(kw)
        if text[i:i + length].upper() == kw:
            nxt = text[i + length] if i + length < len(text) else ""
            if not (nxt.isalnum() or nxt == "_"):
                if kw == "BEGIN" and _next_word_after(text, i + length) in _TRANSACTION_STARTERS:
                    return "BEGIN_TRANSACTION"  # neutral: neither open nor close
                return kw
    return None


def split_sql_statements(sql_text: str):
    """
    Splits a SQL text into statements separated by ';', respecting:

    1. String literals ('...' and "...") to avoid splitting on a semicolon
       that is inside a value (e.g. a dump containing free text with ';').

    2. BEGIN...END and CASE...END blocks, which contain internal ';' WITHOUT
       those terminating the enclosing statement. Typical case of a
       CREATE TRIGGER:

           CREATE TRIGGER trg_check BEFORE INSERT ON tb_class
           BEGIN
               SELECT CASE WHEN NEW.FID IS NULL
                   THEN RAISE(ABORT, 'FID required') END;
               UPDATE tb_class SET x = NEW.FID WHERE id = NEW.id;
           END;

       Without this tracking, the first internal ';' (after the CASE...END,
       or after the first UPDATE) would be taken as the end of the CREATE
       TRIGGER -- the remaining fragment, executed outside trigger context,
       causes cascading errors ("RAISE() may only be used within a
       trigger-program", "no such column: new.FID", etc.) that have nothing
       to do with a real problem in the source file.

       We maintain a `block_depth` counter, incremented on BEGIN and CASE
       (both end with END), decremented on END. A split on ';' is only
       allowed if block_depth == 0 -- i.e. outside any BEGIN...END or
       CASE...END block.

    We avoid raw executescript() because a .dump file generated by Autodesk/
    sqlite3 may contain a CREATE TABLE already present (replayed multiple
    times) or an unsupported statement: we want to be able to ignore a
    failing statement WITHOUT losing the rest of the file.
    """
    statements = []  # what we will return at the end
    buf = []  # current statement being built (list of characters)
    in_single = False  # at the start, we are not inside any string
    in_double = False
    block_depth = 0
    i = 0  # read index in the text
    n = len(sql_text)  # total length, to know when to stop
    # we use a while loop so we can skip characters in some cases
    # (escaping, or multi-character BEGIN/CASE/END keywords)
    while i < n:
        ch = sql_text[i]

        if not in_single and not in_double and ch.isalpha():
            kw = _match_keyword_at(sql_text, i)
            if kw:
                if kw in ("BEGIN", "CASE"):
                    block_depth += 1
                elif kw == "END":
                    block_depth = max(0, block_depth - 1)
                # "BEGIN_TRANSACTION": neutral keyword, no effect on
                # block_depth (see _match_keyword_at)
                kw_len = 5 if kw == "BEGIN_TRANSACTION" else len(kw)
                buf.append(sql_text[i:i + kw_len])
                i += kw_len
                continue

        # each character read (except BEGIN/CASE/END keywords handled above)
        # is added to the buffer
        buf.append(ch)
        # Condition: the character is an apostrophe, AND we are not already
        # inside a "..." string (the not in_double is important: if we are
        # between "", a ' is just a normal text character, e.g. "L'objet":
        # it should not trigger anything).
        if ch == "'" and not in_double:
            # handle '' escaping (literal apostrophe in SQLite,
            # e.g.: INSERT INTO tb_class VALUES(1, 'L''objet');)
            # in_single: we are indeed already in a string (so this
            #   apostrophe could be end-of-string OR an escape)
            # i + 1 < n: at least one character remains after (safety check
            #   to not go past end of text)
            # sql_text[i + 1] == "'": the next character is also an apostrophe
            if in_single and i + 1 < n and sql_text[i + 1] == "'":
                buf.append(sql_text[i + 1])
                i += 2  # advance index by 2 because ''
                continue
            in_single = not in_single  # if not inside a string, enter it
            # (False -> True); if inside, exit it (True -> False)
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == ";" and not in_single and not in_double and block_depth == 0:
            # the character is a ';' AND we are not inside any string AND
            # outside any BEGIN...END/CASE...END block, so this is the end
            # of a complete SQL statement
            stmt = "".join(buf).strip()
            if stmt and stmt != ";":
                statements.append(stmt)
            buf = []  # reset the buffer to start accumulating the next statement
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements



def safe_executescript(conn: sqlite3.Connection, sql_text: str, label: str):
    """
    Executes a SQL script statement by statement, ignoring individual
    errors (table already exists, unsupported syntax, etc.) but logging
    them to stderr. We favor recovering as much information as possible
    rather than a hard stop: the goal is comparison, not perfect
    database restoration.
    """
    cur = conn.cursor()
    errors = 0
    for stmt in split_sql_statements(sql_text):
        try:
            cur.execute(stmt)
        except sqlite3.Error as exc:
            errors += 1
            print(f"[warning] {label}: statement ignored ({exc})",
                  file=sys.stderr)
    conn.commit()
    return errors


# ---------------------------------------------------------------------------
# 2. Data structures
# ---------------------------------------------------------------------------
# We need these structures to store information extracted from SQLite in an
# exploitable Python format, in order to compare schemas and dumps
# efficiently and structurally.
# They transform "SQL that we have to reparse at each comparison" into
# "Python objects that we compare once and for all".
@dataclass
class ColumnInfo:
    name: str
    type: str
    notnull: bool
    default: object
    pk: int  # 0 = not PK, otherwise position in the composite primary key


@dataclass
class TableSchema:
    name: str
    create_sql: str
    columns: dict = field(default_factory=dict)      # name -> ColumnInfo
    foreign_keys: list = field(default_factory=list)  # list of tuples


@dataclass
class SchemaSnapshot:
    tables: dict = field(default_factory=dict)   # name -> TableSchema
    indexes: dict = field(default_factory=dict)  # name -> sql
    triggers: dict = field(default_factory=dict)  # name -> sql
    views: dict = field(default_factory=dict)    # name -> sql


# ---------------------------------------------------------------------------
# 3. Loading the schema (schema_testXX.sql)
# ---------------------------------------------------------------------------
def load_schema(path: str) -> SchemaSnapshot:
    # isolation_level=None disables the IMPLICIT transaction management of
    # the sqlite3 module (which normally opens an automatic transaction
    # before any INSERT/UPDATE/DELETE/CREATE). Without this, a "BEGIN
    # TRANSACTION;" or "COMMIT;" explicitly present in the source file
    # conflicts with this automatic management and fails with "cannot
    # commit - no transaction is active". In autocommit mode, the file's
    # own statements control transactions alone, exactly as the official
    # sqlite3 CLI would do.
    conn = sqlite3.connect(":memory:")
    conn.isolation_level = None
    sql_text = Path(path).read_text(encoding="utf-8", errors="replace")
    sql_text = normalize_special_floats(sql_text)
    safe_executescript(conn, sql_text, label=path)

    snap = SchemaSnapshot()
    cur = conn.cursor()

    cur.execute("""
        SELECT type, name, sql FROM sqlite_master
        WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'
    """)
    rows = cur.fetchall()

    for obj_type, name, sql in rows:
        if obj_type == "table":
            table = TableSchema(name=name, create_sql=sql)

            cur.execute(f'PRAGMA table_info("{name}")')
            for cid, col_name, col_type, notnull, dflt, pk in cur.fetchall():
                table.columns[col_name] = ColumnInfo(
                    name=col_name,
                    type=(col_type or "").strip().upper(),
                    notnull=bool(notnull),
                    default=dflt,
                    pk=pk,
                )

            cur.execute(f'PRAGMA foreign_key_list("{name}")')
            table.foreign_keys = cur.fetchall()

            snap.tables[name] = table
        elif obj_type == "index":
            snap.indexes[name] = sql
        elif obj_type == "trigger":
            snap.triggers[name] = sql
        elif obj_type == "view":
            snap.views[name] = sql

    conn.close()
    return snap


# ---------------------------------------------------------------------------
# 4. Loading the dump (dump_testXX.sql)
# ---------------------------------------------------------------------------
def load_dump(path: str, fallback_schema_path: str = None) -> dict:
    """
    Returns { table_name: {"columns": [...], "pk": [...], "rows": {key: row}} }

    If the dump file contains ONLY INSERTs (no CREATE TABLE), we first
    create the tables from a fallback schema (typically the schema_testXX.sql
    from the same test) to be able to execute the INSERTs.
    """
    conn = sqlite3.connect(":memory:")
    conn.isolation_level = None  # see comment in load_schema()

    dump_sql = Path(path).read_text(encoding="utf-8", errors="replace")
    dump_sql = normalize_special_floats(dump_sql)
    dump_defines_tables = "CREATE TABLE" in dump_sql.upper()

    # We only load the fallback schema IF the dump does not already contain
    # its own CREATE TABLE statements (case of an export containing only
    # INSERTs). This avoids unnecessary "table already exists" warnings
    # when the dump is self-sufficient (classic `.dump` output from sqlite3).
    if fallback_schema_path and not dump_defines_tables:
        schema_sql = Path(fallback_schema_path).read_text(
            encoding="utf-8", errors="replace")
        schema_sql = normalize_special_floats(schema_sql)
        safe_executescript(conn, schema_sql, label=fallback_schema_path)

    safe_executescript(conn, dump_sql, label=path)

    cur = conn.cursor()
    cur.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
    """)
    table_names = [r[0] for r in cur.fetchall()]

    dump = {}
    for name in table_names:
        cur.execute(f'PRAGMA table_info("{name}")')
        table_info = cur.fetchall()
        col_names = [c[1] for c in table_info]
        pk_cols = [c[1] for c in sorted(
            (c for c in table_info if c[5] > 0), key=lambda c: c[5])]

        try:
            cur.execute(f'SELECT * FROM "{name}"')
            raw_rows = cur.fetchall()
        except sqlite3.Error as exc:
            print(f"[warning] unable to read table {name} ({exc})",
                  file=sys.stderr)
            raw_rows = []

        rows = {}
        for r in raw_rows:
            row_dict = dict(zip(col_names, r))
            if pk_cols:
                key = tuple(row_dict[c] for c in pk_cols)
            else:
                # no known PK -> the entire row is its own key
                key = tuple(r)
            rows[key] = row_dict

        dump[name] = {"columns": col_names, "pk": pk_cols, "rows": rows}

    conn.close()
    return dump


# ---------------------------------------------------------------------------
# 5. Schema comparison
# ---------------------------------------------------------------------------
def compare_schemas(old: SchemaSnapshot, new: SchemaSnapshot) -> dict:
    diff = {
        "tables_added": [],
        "tables_removed": [],
        "columns_added": {},     # table -> [ColumnInfo]
        "columns_removed": {},   # table -> [ColumnInfo]
        "columns_modified": {},  # table -> [(col_name, old, new)]
        "fk_added": {},
        "fk_removed": {},
        "indexes_added": [],
        "indexes_removed": [],
        "triggers_added": [],
        "triggers_removed": [],
        "views_added": [],
        "views_removed": [],
    }

    old_tables, new_tables = set(old.tables), set(new.tables)
    diff["tables_added"] = sorted(new_tables - old_tables)
    diff["tables_removed"] = sorted(old_tables - new_tables)

    for tname in sorted(old_tables & new_tables):
        old_t, new_t = old.tables[tname], new.tables[tname]
        old_cols, new_cols = set(old_t.columns), set(new_t.columns)

        added = sorted(new_cols - old_cols)
        removed = sorted(old_cols - new_cols)
        if added:
            diff["columns_added"][tname] = [new_t.columns[c] for c in added]
        if removed:
            diff["columns_removed"][tname] = [old_t.columns[c] for c in removed]

        modified = []
        for cname in sorted(old_cols & new_cols):
            oc, nc = old_t.columns[cname], new_t.columns[cname]
            changes = {}
            if oc.type != nc.type:
                changes["type"] = (oc.type, nc.type)
            if oc.notnull != nc.notnull:
                changes["notnull"] = (oc.notnull, nc.notnull)
            if oc.default != nc.default:
                changes["default"] = (oc.default, nc.default)
            if oc.pk != nc.pk:
                changes["pk"] = (oc.pk, nc.pk)
            if changes:
                modified.append((cname, changes))
        if modified:
            diff["columns_modified"][tname] = modified

        # Relations (foreign keys) -- Test 9
        old_fk = {tuple(fk) for fk in old_t.foreign_keys}
        new_fk = {tuple(fk) for fk in new_t.foreign_keys}
        if new_fk - old_fk:
            diff["fk_added"][tname] = new_fk - old_fk
        if old_fk - new_fk:
            diff["fk_removed"][tname] = old_fk - new_fk

    def diff_named_objects(old_dict, new_dict):
        return (sorted(set(new_dict) - set(old_dict)),
                sorted(set(old_dict) - set(new_dict)))

    diff["indexes_added"], diff["indexes_removed"] = \
        diff_named_objects(old.indexes, new.indexes)
    diff["triggers_added"], diff["triggers_removed"] = \
        diff_named_objects(old.triggers, new.triggers)
    diff["views_added"], diff["views_removed"] = \
        diff_named_objects(old.views, new.views)

    return diff


# ---------------------------------------------------------------------------
# 6. Dump comparison (data)
# ---------------------------------------------------------------------------
def compare_dumps(old_dump: dict, new_dump: dict) -> dict:
    diff = {}  # table -> {"added": [...], "removed": [...], "modified": [...]}

    all_tables = set(old_dump) | set(new_dump)
    for tname in sorted(all_tables):
        old_t = old_dump.get(tname, {"rows": {}, "columns": []})
        new_t = new_dump.get(tname, {"rows": {}, "columns": []})

        old_keys, new_keys = set(old_t["rows"]), set(new_t["rows"])
        added_keys = new_keys - old_keys
        removed_keys = old_keys - new_keys
        common_keys = old_keys & new_keys

        added = [new_t["rows"][k] for k in added_keys]
        removed = [old_t["rows"][k] for k in removed_keys]

        modified = []
        for k in common_keys:
            old_row, new_row = old_t["rows"][k], new_t["rows"][k]
            changed_cols = {
                col: (old_row[col], new_row[col])
                for col in new_row
                if col in old_row and old_row[col] != new_row[col]
            }
            if changed_cols:
                modified.append((k, changed_cols))

        if added or removed or modified:
            diff[tname] = {"added": added, "removed": removed,
                            "modified": modified, "pk": new_t.get("pk") or old_t.get("pk")}

    return diff


def summarize_diff(schema_diff: dict, dump_diff: dict) -> dict:
    """
    Reduces a (schema_diff, dump_diff) pair to simple counters.
    Used to build the summary line for a transition in the consolidated
    report of batch mode (--batch-dir).
    """
    n_cols_added = sum(len(v) for v in schema_diff["columns_added"].values())
    n_cols_removed = sum(len(v) for v in schema_diff["columns_removed"].values())
    n_cols_modified = sum(len(v) for v in schema_diff["columns_modified"].values())
    n_fk_added = sum(len(v) for v in schema_diff["fk_added"].values())
    n_fk_removed = sum(len(v) for v in schema_diff["fk_removed"].values())

    n_rows_added = sum(len(d["added"]) for d in dump_diff.values())
    n_rows_removed = sum(len(d["removed"]) for d in dump_diff.values())
    n_rows_modified = sum(len(d["modified"]) for d in dump_diff.values())

    return {
        "tables_added": len(schema_diff["tables_added"]),
        "tables_removed": len(schema_diff["tables_removed"]),
        "columns_added": n_cols_added,
        "columns_removed": n_cols_removed,
        "columns_modified": n_cols_modified,
        "fk_added": n_fk_added,
        "fk_removed": n_fk_removed,
        "rows_added": n_rows_added,
        "rows_removed": n_rows_removed,
        "rows_modified": n_rows_modified,
    }


# ---------------------------------------------------------------------------
# 7. Markdown report generation
# ---------------------------------------------------------------------------
def generate_report(schema_diff, dump_diff, old_label, new_label) -> str:
    lines = []
    lines.append(f"# Comparison `{old_label}` -> `{new_label}`\n")

    def section(title):
        lines.append(f"\n## {title}\n")

    # --- Tables ---
    section("Tables added")
    if schema_diff["tables_added"]:
        for t in schema_diff["tables_added"]:
            lines.append(f"- `+ {t}`")
    else:
        lines.append("None")

    section("Tables removed")
    if schema_diff["tables_removed"]:
        for t in schema_diff["tables_removed"]:
            lines.append(f"- `- {t}`")
    else:
        lines.append("None")

    # --- Columns added ---
    section("Columns added")
    if schema_diff["columns_added"]:
        for tname, cols in schema_diff["columns_added"].items():
            lines.append(f"\n**Table: `{tname}`**")
            for c in cols:
                attrs = [c.type]
                if c.notnull: attrs.append("NOT NULL")
                if c.default is not None: attrs.append(f"DEFAULT {c.default}")
                if c.pk > 0: attrs.append(f"PK({c.pk})")
                attr_str = ", ".join(attrs)
                lines.append(f"- `+ {c.name} ({attr_str})`")
    else:
        lines.append("None")

    # --- Columns removed ---
    section("Columns removed")
    if schema_diff["columns_removed"]:
        for tname, cols in schema_diff["columns_removed"].items():
            lines.append(f"\n**Table: `{tname}`**")
            for c in cols:
                attrs = [c.type]
                if c.notnull: attrs.append("NOT NULL")
                if c.default is not None: attrs.append(f"DEFAULT {c.default}")
                if c.pk > 0: attrs.append(f"PK({c.pk})")
                attr_str = ", ".join(attrs)
                lines.append(f"- `- {c.name} ({attr_str})`")
    else:
        lines.append("None")

    # --- Columns modified ---
    section("Columns modified")
    if schema_diff["columns_modified"]:
        for tname, mods in schema_diff["columns_modified"].items():
            lines.append(f"\n**Table: `{tname}`**")
            for cname, changes in mods:
                lines.append(f"- Column `{cname}`:")
                for prop, (ov, nv) in changes.items():
                    lines.append(f"  - {prop}: `{ov}` -> `{nv}`")
    else:
        lines.append("None")

    # --- Relations (FK) ---
    section("Relations added (foreign keys)")
    if schema_diff["fk_added"]:
        for tname, fks in schema_diff["fk_added"].items():
            for fk in fks:
                lines.append(f"- `{tname}`: `+ {fk}`")
    else:
        lines.append("None")

    section("Relations removed (foreign keys)")
    if schema_diff["fk_removed"]:
        for tname, fks in schema_diff["fk_removed"].items():
            for fk in fks:
                lines.append(f"- `{tname}`: `- {fk}`")
    else:
        lines.append("None")

    # --- Indexes / triggers / views ---
    for label, added_key, removed_key in [
        ("Indexes", "indexes_added", "indexes_removed"),
        ("Triggers", "triggers_added", "triggers_removed"),
        ("Views", "views_added", "views_removed"),
    ]:
        section(f"{label} added")
        if schema_diff[added_key]:
            for n in schema_diff[added_key]:
                lines.append(f"- `+ {n}`")
        else:
            lines.append("None")

        section(f"{label} removed")
        if schema_diff[removed_key]:
            for n in schema_diff[removed_key]:
                lines.append(f"- `- {n}`")
        else:
            lines.append("None")

    # --- Data ---
    section("Data (dump)")
    if not dump_diff:
        lines.append("No data difference detected.")
    else:
        for tname, d in dump_diff.items():
            lines.append(f"\n**Table: `{tname}`**")
            if d["added"]:
                lines.append(f"\n_{len(d['added'])} row(s) added_")
                for row in d["added"]:
                    lines.append(f"- `+ {row}`")
            if d["removed"]:
                lines.append(f"\n_{len(d['removed'])} row(s) removed_")
                for row in d["removed"]:
                    lines.append(f"- `- {row}`")
            if d["modified"]:
                lines.append(f"\n_{len(d['modified'])} row(s) modified_")
                for key, changes in d["modified"]:
                    pk_label = d["pk"] if d["pk"] else "key"
                    lines.append(f"- Row `{pk_label}={key}`:")
                    for col, (ov, nv) in changes.items():
                        lines.append(f"  - `{col}`: `{ov}` -> `{nv}`")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 8. Batch mode: compare an entire series of tests at once
# ---------------------------------------------------------------------------
def discover_test_files(directory: str) -> dict:
    """
    Scans a directory -- and ALL its subdirectories recursively -- and
    associates each test number with the pair of files (schema, dump)
    found, based on the names 'schema_testXX.sql' / 'dump_testXX.sql'
    (case-insensitive).

    The search is recursive (Path.rglob) because each test may be in its
    own subdirectory (e.g. Test0/dump_test00.sql, Test1/dump_test01.sql,
    ...), which is the convention used in this project -- a simple
    first-level listing (iterdir) would find no files.

    Returns { test_number: {"schema": path, "dump": path} }, only for
    numbers where BOTH files exist (a test missing the schema or dump is
    ignored with a warning).
    """
    schema_pat = re.compile(r"schema_test0*(\d+)\.sql$", re.IGNORECASE)
    dump_pat = re.compile(r"dump_test0*(\d+)\.sql$", re.IGNORECASE)

    schemas, dumps = {}, {}
    for path in Path(directory).rglob("*.sql"):
        if not path.is_file():
            continue
        m = schema_pat.match(path.name)
        if m:
            n = int(m.group(1))
            if n in schemas:
                print(f"[warning] multiple schema_test{n} found "
                      f"({schemas[n]} and {path}) -- keeping the last one",
                      file=sys.stderr)
            schemas[n] = str(path)
            continue
        m = dump_pat.match(path.name)
        if m:
            n = int(m.group(1))
            if n in dumps:
                print(f"[warning] multiple dump_test{n} found "
                      f"({dumps[n]} and {path}) -- keeping the last one",
                      file=sys.stderr)
            dumps[n] = str(path)

    tests = {}
    all_numbers = sorted(set(schemas) | set(dumps))
    for n in all_numbers:
        if n in schemas and n in dumps:
            tests[n] = {"schema": schemas[n], "dump": dumps[n]}
        else:
            missing = "dump" if n in schemas else "schema"
            print(f"[warning] Test {n} ignored: {missing} missing",
                  file=sys.stderr)

    return tests


def run_batch(directory: str, out_dir: str):
    """
    Automatically compares each test with the previous available test
    (in ascending order of found numbers -- not necessarily N vs N+1 if
    some numbers are absent, e.g. Tests 13/14/15 intentionally excluded
    from the project). Generates one report per transition + a global
    summary report 'report_summary.md'.
    """
    tests = discover_test_files(directory)
    numbers = sorted(tests)
    if len(numbers) < 2:
        print("[error] At least 2 complete tests (schema+dump) are needed "
              "to compare.", file=sys.stderr)
        sys.exit(1)

    Path(out_dir).mkdir(parents=True, exist_ok=True)

    summary_rows = []
    for old_n, new_n in zip(numbers, numbers[1:]):
        old_files, new_files = tests[old_n], tests[new_n]
        old_label, new_label = f"test{old_n}", f"test{new_n}"

        print(f"[info] comparing {old_label} -> {new_label}")
        old_schema = load_schema(old_files["schema"])
        new_schema = load_schema(new_files["schema"])
        old_dump = load_dump(old_files["dump"], fallback_schema_path=old_files["schema"])
        new_dump = load_dump(new_files["dump"], fallback_schema_path=new_files["schema"])

        schema_diff = compare_schemas(old_schema, new_schema)
        dump_diff = compare_dumps(old_dump, new_dump)

        report = generate_report(schema_diff, dump_diff, old_label, new_label)
        report_name = f"report_{old_label}_vs_{new_label}.md"
        report_path = Path(out_dir) / report_name
        report_path.write_text(report, encoding="utf-8")

        counts = summarize_diff(schema_diff, dump_diff)
        counts.update({"transition": f"{old_label} -> {new_label}",
                       "report": report_name})
        summary_rows.append(counts)

    # --- Global summary report ---
    lines = ["# Global test summary\n",
             "| Transition | Tables +/- | Columns +/-/~ | FK +/- | "
             "Rows +/-/~ | Report |",
             "|---|---|---|---|---|---|"]
    for r in summary_rows:
        lines.append(
            f"| {r['transition']} "
            f"| +{r['tables_added']} / -{r['tables_removed']} "
            f"| +{r['columns_added']} / -{r['columns_removed']} / "
            f"~{r['columns_modified']} "
            f"| +{r['fk_added']} / -{r['fk_removed']} "
            f"| +{r['rows_added']} / -{r['rows_removed']} / "
            f"~{r['rows_modified']} "
            f"| [{r['report']}]({r['report']}) |"
        )
    summary_path = Path(out_dir) / "report_summary.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[ok] {len(summary_rows)} transition(s) compared")
    print(f"[ok] individual reports in: {out_dir}/")
    print(f"[ok] global summary: {summary_path}")


# ---------------------------------------------------------------------------
# 9. CLI entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Test 19 - Automated comparison of SQLite exports "
                    "(schema + dump) from an Autodesk Data Model. "
                    "Pair mode (default): compares 2 specific tests. "
                    "Batch mode (--batch-dir): compares an entire series.")
    parser.add_argument("schema_old", nargs="?", help="schema_testN.sql (old)")
    parser.add_argument("schema_new", nargs="?", help="schema_testN+1.sql (new)")
    parser.add_argument("dump_old", nargs="?", help="dump_testN.sql (old)")
    parser.add_argument("dump_new", nargs="?", help="dump_testN+1.sql (new)")
    parser.add_argument("-o", "--output", default=None,
                        help="Output markdown file (pair mode) "
                             "(default: report_<old>_vs_<new>.md)")
    parser.add_argument("--batch-dir", default=None,
                        help="Directory containing all schema_testXX.sql / "
                             "dump_testXX.sql to compare automatically in "
                             "series (activates batch mode).")
    parser.add_argument("--out-dir", default="reports",
                        help="Output directory for batch mode "
                             "(default: ./reports)")
    args = parser.parse_args()

    if args.batch_dir:
        run_batch(args.batch_dir, args.out_dir)
        return

    if not all([args.schema_old, args.schema_new, args.dump_old, args.dump_new]):
        parser.error("In pair mode, all 4 positional files are required "
                     "(or use --batch-dir).")

    old_label = Path(args.schema_old).stem
    new_label = Path(args.schema_new).stem

    print(f"[info] loading schema: {args.schema_old}")
    old_schema = load_schema(args.schema_old)
    print(f"[info] loading schema: {args.schema_new}")
    new_schema = load_schema(args.schema_new)

    print(f"[info] loading dump: {args.dump_old}")
    old_dump = load_dump(args.dump_old, fallback_schema_path=args.schema_old)
    print(f"[info] loading dump: {args.dump_new}")
    new_dump = load_dump(args.dump_new, fallback_schema_path=args.schema_new)

    schema_diff = compare_schemas(old_schema, new_schema)
    dump_diff = compare_dumps(old_dump, new_dump)

    report = generate_report(schema_diff, dump_diff, old_label, new_label)

    out_path = args.output or f"report_{old_label}_vs_{new_label}.md"
    Path(out_path).write_text(report, encoding="utf-8")
    print(f"[ok] report generated: {out_path}")


if __name__ == "__main__":
    main()