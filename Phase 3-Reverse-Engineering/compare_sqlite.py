#!/usr/bin/env python3
"""
compare_sqlite.py
==================

Test 19 - Outil d'analyse automatisee du Data Model Autodesk
--------------------------------------------------------------

Objectif
--------
Comparer deux exports SQLite successifs (schema_testXX.sql / dump_testXX.sql)
generes depuis Infrastructure Administrator, et produire un rapport structure
des changements STRUCTURELS et des changements de DONNEES.

Pourquoi cette architecture ?
-----------------------------
On ne fait PAS un diff textuel (difflib) des fichiers .sql : un simple
changement d'ordre des lignes, ou une reecriture equivalente d'un CREATE
TABLE, produirait de faux positifs. On ne comprendrait pas les objets SQL,
seulement leur representation textuelle.

A la place, on charge chaque fichier .sql dans une base SQLite temporaire
en memoire (":memory:"), et on delegue le parsing a SQLite lui-meme via :

    - sqlite_master              -> tables, index, triggers, vues (+ SQL brut)
    - PRAGMA table_info(table)   -> colonnes, types, NOT NULL, defaut, PK
    - PRAGMA foreign_key_list()  -> relations entre classes (Test 9)

Cela garantit qu'on compare la structure LOGIQUE et non la mise en forme.

Pour le dump (donnees), on charge le fichier dans sa propre base memoire
et on lit les lignes via SELECT * FROM table. Si une cle primaire existe,
la comparaison se fait PAR CLE (pas par simple appartenance a un ensemble),
ce qui permet de detecter des "valeurs modifiees" (UPDATE implicite) et pas
seulement des lignes ajoutees/supprimees.

Usage
-----
    python compare_sqlite.py schema_testN.sql schema_testN1.sql \\
                              dump_testN.sql   dump_testN1.sql \\
                              -o rapport_testN_vs_testN1.md

Les 4 fichiers sont positionnels et dans cet ordre. Le rapport est ecrit en
Markdown, directement integrable dans un memoire de PFE.
"""

import argparse
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# 1. Decoupage robuste d'un script SQL en instructions individuelles
# ---------------------------------------------------------------------------
_TRANSACTION_STARTERS = {"TRANSACTION", "DEFERRED", "IMMEDIATE", "EXCLUSIVE"}

# Detecte les tokens Inf / -Inf / +Inf / Infinity / NaN ecrits SANS
# guillemets dans un fichier .sql -- typique d'un export contenant des
# coordonnees de bounding box "non bornees" (courant en geomatique/FDO).
# En SQL standard, ce ne sont PAS des litteraux numeriques valides : sans
# guillemets, SQLite les interprete comme des noms de colonne, ce qui fait
# echouer l'INSERT entier avec "no such column: Inf" et PERD la ligne de
# donnee correspondante silencieusement (jusqu'a l'avertissement).
#
# (?<![\w'"]) / (?![\w'"]) : le token ne doit pas etre colle a une lettre,
# un underscore, ou un guillemet -- ce qui exclut a la fois les mots plus
# longs (ex. "Infrastructure") ET les occurrences DEJA correctement
# quotees (ex. 'Inf' comme vraie valeur texte), qui n'ont pas besoin
# d'etre corrigees.
_SPECIAL_FLOAT_RE = re.compile(
    r"(?<![\w'\"])([+-]?(?:Infinity|Inf|NaN))(?![\w'\"])", re.IGNORECASE)


def normalize_special_floats(sql_text: str) -> str:
    """
    Reecrit les tokens Inf/-Inf/+Inf/Infinity/NaN non quotes en litteraux
    texte valides ('Inf', '-Inf', ...), pour que l'instruction SQL reste
    executable et que la valeur reste comparable entre deux exports (on
    perd la semantique numerique exacte de l'infini, mais on gagne la
    capacite de detecter si la valeur a change -- suffisant pour un outil
    de comparaison, pas de calcul).
    """
    return _SPECIAL_FLOAT_RE.sub(lambda m: f"'{m.group(1)}'", sql_text)



def _next_word_after(text: str, i: int) -> str:
    """
    Retourne le prochain "mot" (suite de caracteres alphanumeriques) apres
    la position i, en sautant les espaces/retours a la ligne. Utilise
    pour distinguer BEGIN TRANSACTION (qui n'a PAS de END associe -- il se
    termine par COMMIT/ROLLBACK) du BEGIN qui ouvre le corps d'un trigger
    ou d'une vue (qui, lui, se termine par END).
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
    Verifie si un mot-cle SQL (BEGIN, CASE, END) commence exactement a la
    position i dans `text`, en respectant les frontieres de mot (le
    caractere avant et apres ne doit pas etre alphanumerique/underscore
    -- sinon on matcherait "END" a l'interieur de "APPEND" par exemple).

    Retourne le mot-cle trouve ("BEGIN", "CASE" ou "END") ou None.

    Cas particulier : "BEGIN TRANSACTION" (et ses variantes DEFERRED /
    IMMEDIATE / EXCLUSIVE) n'ouvre PAS un bloc au sens ou on l'entend ici
    -- ce BEGIN-la se termine par COMMIT/ROLLBACK, jamais par END. Le
    compter comme un bloc BEGIN...END casserait le comptage de profondeur
    pour tout le reste du fichier (le vrai BEGIN...END d'un trigger plus
    loin ne "fermerait" jamais ce faux bloc). On le detecte donc et on le
    traite comme un mot-cle neutre (ignore) plutot que comme une
    ouverture de bloc.
    """
    if i > 0 and (text[i - 1].isalnum() or text[i - 1] == "_"):
        return None
    for kw in ("BEGIN", "CASE", "END"):
        length = len(kw)
        if text[i:i + length].upper() == kw:
            nxt = text[i + length] if i + length < len(text) else ""
            if not (nxt.isalnum() or nxt == "_"):
                if kw == "BEGIN" and _next_word_after(text, i + length) in _TRANSACTION_STARTERS:
                    return "BEGIN_TRANSACTION"  # neutre : ni ouverture ni fermeture
                return kw
    return None


def split_sql_statements(sql_text: str):
    """
    Decoupe un texte SQL en instructions separees par ';', en respectant :

    1. Les chaines de caracteres ('...' et "...") pour ne pas couper un
       point-virgule qui serait a l'interieur d'une valeur (ex: un dump
       contenant du texte libre avec des ';').

    2. Les blocs BEGIN...END et CASE...END, qui contiennent eux-memes des
       ';' internes SANS que ceux-ci terminent l'instruction englobante.
       C'est le cas typique d'un CREATE TRIGGER :

           CREATE TRIGGER trg_check BEFORE INSERT ON tb_class
           BEGIN
               SELECT CASE WHEN NEW.FID IS NULL
                   THEN RAISE(ABORT, 'FID requis') END;
               UPDATE tb_class SET x = NEW.FID WHERE id = NEW.id;
           END;

       Sans ce suivi, le premier ';' interne (apres le CASE...END, ou
       apres le premier UPDATE) serait pris pour la fin du CREATE TRIGGER
       -- le fragment restant, execute hors contexte de trigger, provoque
       des erreurs en cascade ("RAISE() may only be used within a
       trigger-program", "no such column: new.FID", etc.) qui n'ont rien
       a voir avec un vrai probleme du fichier source.

       On maintient un compteur `block_depth`, incremente sur BEGIN et
       CASE (les deux s'achevent par un END), decremente sur END. Une
       coupure sur ';' n'est autorisee que si block_depth == 0 -- c'est-a-
       dire hors de tout bloc BEGIN...END ou CASE...END.

    On evite executescript() brut car un fichier .dump genere par Autodesk/
    sqlite3 peut contenir un CREATE TABLE deja present (rejoue plusieurs
    fois) ou une instruction non supportee : on veut pouvoir ignorer une
    instruction en erreur SANS perdre tout le reste du fichier.
    """
    statements = []  # ce qu'on va retourner a la fin
    buf = []  # instruction en cours de construction (liste de caracteres)
    in_single = False  # au depart, on n'est dans aucune chaine
    in_double = False
    block_depth = 0
    i = 0  # index de lecture dans le texte
    n = len(sql_text)  # longueur totale, pour savoir quand s'arreter
    # on utilise une boucle while pour qu'on puisse sauter des chars dans
    # quelques cas (echappement, ou mot-cle BEGIN/CASE/END multi-caracteres)
    while i < n:
        ch = sql_text[i]

        if not in_single and not in_double and ch.isalpha():
            kw = _match_keyword_at(sql_text, i)
            if kw:
                if kw in ("BEGIN", "CASE"):
                    block_depth += 1
                elif kw == "END":
                    block_depth = max(0, block_depth - 1)
                # "BEGIN_TRANSACTION" : mot-cle neutre, aucun effet sur
                # block_depth (voir _match_keyword_at)
                kw_len = 5 if kw == "BEGIN_TRANSACTION" else len(kw)
                buf.append(sql_text[i:i + kw_len])
                i += kw_len
                continue

        # chaque char lu (hors mot-cle BEGIN/CASE/END gere ci-dessus) est
        # ajoute au buffer
        buf.append(ch)
        # Condition : le caractere est une apostrophe, ET on n'est pas deja
        # dans une chaine "..." (le not in_double est important : si on
        # est entre "", une ' est juste un caractere normal du texte, ex.
        # "L'objet" : elle ne doit rien declencher).
        if ch == "'" and not in_double:
            # gere l'echappement '' (apostrophe litterale dans SQLite,
            # Ex: INSERT INTO tb_class VALUES(1, 'L''objet');)
            # in_single : on est bien deja dans une chaine (donc cette
            #   apostrophe pourrait etre une fin de chaine OU un echappement)
            # i + 1 < n : il reste au moins un caractere apres (securite
            #   pour ne pas sortir du texte)
            # sql_text[i + 1] == "'" : le caractere suivant est aussi une
            #   apostrophe
            if in_single and i + 1 < n and sql_text[i + 1] == "'":
                buf.append(sql_text[i + 1])
                i += 2  # avancer l'index de 2 car ''
                continue
            in_single = not in_single  # si on n'etait pas dans une chaine,
            # on y entre (False -> True) ; si on y etait, on en sort (True -> False)
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == ";" and not in_single and not in_double and block_depth == 0:
            # le caractere est un ';' ET on n'est dans aucune des deux
            # chaines ET hors de tout bloc BEGIN...END/CASE...END, donc
            # c'est la fin d'une instruction SQL complete
            stmt = "".join(buf).strip()
            if stmt and stmt != ";":
                statements.append(stmt)
            buf = []  # on reinitialise le buffer pour commencer a
            # accumuler la prochaine instruction
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements



def safe_executescript(conn: sqlite3.Connection, sql_text: str, label: str):
    """
    Execute un script SQL instruction par instruction, en ignorant les
    erreurs individuelles (table deja existante, syntaxe non supportee,
    etc.) mais en les journalisant sur stderr. On privilegie la recuperation
    du maximum d'information plutot qu'un arret brutal : le but est une
    comparaison, pas une restauration parfaite de la base.
    """
    cur = conn.cursor()
    errors = 0
    for stmt in split_sql_statements(sql_text):
        try:
            cur.execute(stmt)
        except sqlite3.Error as exc:
            errors += 1
            print(f"[avertissement] {label}: instruction ignoree ({exc})",
                  file=sys.stderr)
    conn.commit()
    return errors


# ---------------------------------------------------------------------------
# 2. Structures de donnees
# ---------------------------------------------------------------------------
# Nous avons besoin de ces structures pour stocker les informations extraites
# de SQLite dans un format Python exploitable, afin de pouvoir comparer les
# schemas et les dumps de maniere efficace et structuree.
# Elles transforment "du SQL qu'on doit reparser a chaque comparaison" en
# "des objets Python qu'on compare une fois pour toutes".
@dataclass
class ColumnInfo:
    name: str
    type: str
    notnull: bool
    default: object
    pk: int  # 0 = pas PK, sinon position dans la cle primaire composite


@dataclass
class TableSchema:
    name: str
    create_sql: str
    columns: dict = field(default_factory=dict)      # name -> ColumnInfo
    foreign_keys: list = field(default_factory=list)  # liste de tuples


@dataclass
class SchemaSnapshot:
    tables: dict = field(default_factory=dict)   # name -> TableSchema
    indexes: dict = field(default_factory=dict)  # name -> sql
    triggers: dict = field(default_factory=dict)  # name -> sql
    views: dict = field(default_factory=dict)    # name -> sql


# ---------------------------------------------------------------------------
# 3. Chargement du schema (schema_testXX.sql)
# ---------------------------------------------------------------------------
def load_schema(path: str) -> SchemaSnapshot:
    # isolation_level=None desactive la gestion de transaction IMPLICITE du
    # module sqlite3 (qui ouvre normalement une transaction automatique
    # avant tout INSERT/UPDATE/DELETE/CREATE). Sans ca, un "BEGIN
    # TRANSACTION;" ou un "COMMIT;" explicite present dans le fichier
    # source entre en conflit avec cette gestion automatique et echoue
    # avec "cannot commit - no transaction is active". En mode autocommit,
    # ce sont les instructions du fichier qui pilotent seules les
    # transactions, exactement comme le ferait le CLI sqlite3 officiel.
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
# 4. Chargement du dump (dump_testXX.sql)
# ---------------------------------------------------------------------------
def load_dump(path: str, fallback_schema_path: str = None) -> dict:
    """
    Retourne { table_name: {"columns": [...], "pk": [...], "rows": {key: row}} }

    Si le fichier dump ne contient QUE des INSERT (pas de CREATE TABLE),
    on cree d'abord les tables a partir d'un schema de secours
    (typiquement le schema_testXX.sql du meme test) pour pouvoir executer
    les INSERT.
    """
    conn = sqlite3.connect(":memory:")
    conn.isolation_level = None  # cf. commentaire dans load_schema()

    dump_sql = Path(path).read_text(encoding="utf-8", errors="replace")
    dump_sql = normalize_special_floats(dump_sql)
    dump_defines_tables = "CREATE TABLE" in dump_sql.upper()

    # On ne charge le schema de secours QUE si le dump ne contient pas deja
    # ses propres CREATE TABLE (cas d'un export contenant uniquement des
    # INSERT). Cela evite des avertissements "table already exists" inutiles
    # quand le dump est autosuffisant (sortie `.dump` classique de sqlite3).
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
            print(f"[avertissement] lecture table {name} impossible ({exc})",
                  file=sys.stderr)
            raw_rows = []

        rows = {}
        for r in raw_rows:
            row_dict = dict(zip(col_names, r))
            if pk_cols:
                key = tuple(row_dict[c] for c in pk_cols)
            else:
                # pas de PK connue -> la ligne entiere est sa propre cle
                key = tuple(r)
            rows[key] = row_dict

        dump[name] = {"columns": col_names, "pk": pk_cols, "rows": rows}

    conn.close()
    return dump


# ---------------------------------------------------------------------------
# 5. Comparaison des schemas
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

        # Relations (cles etrangeres) -- Test 9
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
# 6. Comparaison des dumps (donnees)
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
    Reduit un couple (schema_diff, dump_diff) a des compteurs simples.
    Sert a construire la ligne de synthese d'une transition dans le
    rapport consolide du mode batch (--batch-dir).
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
# 7. Generation du rapport Markdown
# ---------------------------------------------------------------------------
def generate_report(schema_diff, dump_diff, old_label, new_label) -> str:
    lines = []
    lines.append(f"# Comparaison `{old_label}` -> `{new_label}`\n")

    def section(title):
        lines.append(f"\n## {title}\n")

    # --- Tables ---
    section("Tables ajoutees")
    if schema_diff["tables_added"]:
        for t in schema_diff["tables_added"]:
            lines.append(f"- `+ {t}`")
    else:
        lines.append("Aucune")

    section("Tables supprimees")
    if schema_diff["tables_removed"]:
        for t in schema_diff["tables_removed"]:
            lines.append(f"- `- {t}`")
    else:
        lines.append("Aucune")

    # --- Colonnes ajoutees ---
    section("Colonnes ajoutees")
    if schema_diff["columns_added"]:
        for tname, cols in schema_diff["columns_added"].items():
            lines.append(f"\n**Table : `{tname}`**")
            for c in cols:
                lines.append(f"- `+ {c.name} ({c.type})`")
    else:
        lines.append("Aucune")

    # --- Colonnes supprimees ---
    section("Colonnes supprimees")
    if schema_diff["columns_removed"]:
        for tname, cols in schema_diff["columns_removed"].items():
            lines.append(f"\n**Table : `{tname}`**")
            for c in cols:
                lines.append(f"- `- {c.name} ({c.type})`")
    else:
        lines.append("Aucune")

    # --- Colonnes modifiees ---
    section("Colonnes modifiees")
    if schema_diff["columns_modified"]:
        for tname, mods in schema_diff["columns_modified"].items():
            lines.append(f"\n**Table : `{tname}`**")
            for cname, changes in mods:
                lines.append(f"- Colonne `{cname}` :")
                for prop, (ov, nv) in changes.items():
                    lines.append(f"  - {prop} : `{ov}` -> `{nv}`")
    else:
        lines.append("Aucune")

    # --- Relations (FK) ---
    section("Relations ajoutees (cles etrangeres)")
    if schema_diff["fk_added"]:
        for tname, fks in schema_diff["fk_added"].items():
            for fk in fks:
                lines.append(f"- `{tname}` : `+ {fk}`")
    else:
        lines.append("Aucune")

    section("Relations supprimees (cles etrangeres)")
    if schema_diff["fk_removed"]:
        for tname, fks in schema_diff["fk_removed"].items():
            for fk in fks:
                lines.append(f"- `{tname}` : `- {fk}`")
    else:
        lines.append("Aucune")

    # --- Index / triggers / vues ---
    for label, added_key, removed_key in [
        ("Index", "indexes_added", "indexes_removed"),
        ("Triggers", "triggers_added", "triggers_removed"),
        ("Vues", "views_added", "views_removed"),
    ]:
        section(f"{label} ajoutes")
        if schema_diff[added_key]:
            for n in schema_diff[added_key]:
                lines.append(f"- `+ {n}`")
        else:
            lines.append("Aucun")

        section(f"{label} supprimes")
        if schema_diff[removed_key]:
            for n in schema_diff[removed_key]:
                lines.append(f"- `- {n}`")
        else:
            lines.append("Aucun")

    # --- Donnees ---
    section("Donnees (dump)")
    if not dump_diff:
        lines.append("Aucune difference de donnees detectee.")
    else:
        for tname, d in dump_diff.items():
            lines.append(f"\n**Table : `{tname}`**")
            if d["added"]:
                lines.append(f"\n_{len(d['added'])} ligne(s) ajoutee(s)_")
                for row in d["added"]:
                    lines.append(f"- `+ {row}`")
            if d["removed"]:
                lines.append(f"\n_{len(d['removed'])} ligne(s) supprimee(s)_")
                for row in d["removed"]:
                    lines.append(f"- `- {row}`")
            if d["modified"]:
                lines.append(f"\n_{len(d['modified'])} ligne(s) modifiee(s)_")
                for key, changes in d["modified"]:
                    pk_label = d["pk"] if d["pk"] else "cle"
                    lines.append(f"- Ligne `{pk_label}={key}` :")
                    for col, (ov, nv) in changes.items():
                        lines.append(f"  - `{col}` : `{ov}` -> `{nv}`")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 8. Mode batch : comparer toute une serie de tests en une fois
# ---------------------------------------------------------------------------
def discover_test_files(directory: str) -> dict:
    """
    Scanne un dossier -- et TOUS ses sous-dossiers, recursivement -- et
    associe a chaque numero de test le couple de fichiers (schema, dump)
    trouve, en se basant sur les noms 'schema_testXX.sql' /
    'dump_testXX.sql' (insensible a la casse).

    La recherche est recursive (Path.rglob) car chaque test peut se
    trouver dans son propre sous-dossier (ex. Test0/dump_test00.sql,
    Test1/dump_test01.sql, ...), ce qui est la convention utilisee dans ce
    projet -- un simple listage du premier niveau (iterdir) ne trouverait
    aucun fichier.

    Retourne { numero_test: {"schema": path, "dump": path} }, uniquement
    pour les numeros ou LES DEUX fichiers existent (un test dont il manque
    le schema ou le dump est ignore avec un avertissement).
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
                print(f"[avertissement] plusieurs schema_test{n} trouves "
                      f"({schemas[n]} et {path}) -- le dernier trouve est "
                      f"conserve", file=sys.stderr)
            schemas[n] = str(path)
            continue
        m = dump_pat.match(path.name)
        if m:
            n = int(m.group(1))
            if n in dumps:
                print(f"[avertissement] plusieurs dump_test{n} trouves "
                      f"({dumps[n]} et {path}) -- le dernier trouve est "
                      f"conserve", file=sys.stderr)
            dumps[n] = str(path)

    tests = {}
    all_numbers = sorted(set(schemas) | set(dumps))
    for n in all_numbers:
        if n in schemas and n in dumps:
            tests[n] = {"schema": schemas[n], "dump": dumps[n]}
        else:
            missing = "dump" if n in schemas else "schema"
            print(f"[avertissement] Test {n} ignore : {missing} manquant",
                  file=sys.stderr)

    return tests


def run_batch(directory: str, out_dir: str):
    """
    Compare automatiquement chaque test avec le test disponible precedent
    (dans l'ordre croissant des numeros trouves -- pas forcement N vs N+1
    si des numeros sont absents, ex. Tests 13/14/15 volontairement exclus
    du projet). Genere un rapport par transition + un rapport de synthese
    global 'rapport_synthese.md'.
    """
    tests = discover_test_files(directory)
    numbers = sorted(tests)
    if len(numbers) < 2:
        print("[erreur] Il faut au moins 2 tests complets (schema+dump) "
              "pour comparer.", file=sys.stderr)
        sys.exit(1)

    Path(out_dir).mkdir(parents=True, exist_ok=True)

    summary_rows = []
    for old_n, new_n in zip(numbers, numbers[1:]):
        old_files, new_files = tests[old_n], tests[new_n]
        old_label, new_label = f"test{old_n}", f"test{new_n}"

        print(f"[info] comparaison {old_label} -> {new_label}")
        old_schema = load_schema(old_files["schema"])
        new_schema = load_schema(new_files["schema"])
        old_dump = load_dump(old_files["dump"], fallback_schema_path=old_files["schema"])
        new_dump = load_dump(new_files["dump"], fallback_schema_path=new_files["schema"])

        schema_diff = compare_schemas(old_schema, new_schema)
        dump_diff = compare_dumps(old_dump, new_dump)

        report = generate_report(schema_diff, dump_diff, old_label, new_label)
        report_name = f"rapport_{old_label}_vs_{new_label}.md"
        report_path = Path(out_dir) / report_name
        report_path.write_text(report, encoding="utf-8")

        counts = summarize_diff(schema_diff, dump_diff)
        counts.update({"transition": f"{old_label} -> {new_label}",
                       "report": report_name})
        summary_rows.append(counts)

    # --- Rapport de synthese global ---
    lines = ["# Synthese globale des tests\n",
             "| Transition | Tables +/- | Colonnes +/-/~ | FK +/- | "
             "Lignes +/-/~ | Rapport |",
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
    summary_path = Path(out_dir) / "rapport_synthese.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[ok] {len(summary_rows)} transition(s) comparee(s)")
    print(f"[ok] rapports individuels dans : {out_dir}/")
    print(f"[ok] synthese globale : {summary_path}")


# ---------------------------------------------------------------------------
# 9. Point d'entree CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Test 19 - Comparaison automatisee d'exports SQLite "
                    "(schema + dump) d'un Data Model Autodesk. "
                    "Mode paire (defaut) : compare 2 tests precis. "
                    "Mode batch (--batch-dir) : compare toute une serie.")
    parser.add_argument("schema_old", nargs="?", help="schema_testN.sql (ancien)")
    parser.add_argument("schema_new", nargs="?", help="schema_testN+1.sql (nouveau)")
    parser.add_argument("dump_old", nargs="?", help="dump_testN.sql (ancien)")
    parser.add_argument("dump_new", nargs="?", help="dump_testN+1.sql (nouveau)")
    parser.add_argument("-o", "--output", default=None,
                        help="Fichier markdown de sortie (mode paire) "
                             "(defaut: rapport_<old>_vs_<new>.md)")
    parser.add_argument("--batch-dir", default=None,
                        help="Dossier contenant tous les schema_testXX.sql "
                             "/ dump_testXX.sql a comparer automatiquement "
                             "en serie (active le mode batch).")
    parser.add_argument("--out-dir", default="rapports",
                        help="Dossier de sortie pour le mode batch "
                             "(defaut: ./rapports)")
    args = parser.parse_args()

    if args.batch_dir:
        run_batch(args.batch_dir, args.out_dir)
        return

    if not all([args.schema_old, args.schema_new, args.dump_old, args.dump_new]):
        parser.error("En mode paire, les 4 fichiers positionnels sont "
                     "requis (ou utilisez --batch-dir).")

    old_label = Path(args.schema_old).stem
    new_label = Path(args.schema_new).stem

    print(f"[info] chargement du schema : {args.schema_old}")
    old_schema = load_schema(args.schema_old)
    print(f"[info] chargement du schema : {args.schema_new}")
    new_schema = load_schema(args.schema_new)

    print(f"[info] chargement du dump : {args.dump_old}")
    old_dump = load_dump(args.dump_old, fallback_schema_path=args.schema_old)
    print(f"[info] chargement du dump : {args.dump_new}")
    new_dump = load_dump(args.dump_new, fallback_schema_path=args.schema_new)

    schema_diff = compare_schemas(old_schema, new_schema)
    dump_diff = compare_dumps(old_dump, new_dump)

    report = generate_report(schema_diff, dump_diff, old_label, new_label)

    out_path = args.output or f"rapport_{old_label}_vs_{new_label}.md"
    Path(out_path).write_text(report, encoding="utf-8")
    print(f"[ok] rapport genere : {out_path}")


if __name__ == "__main__":
    main()