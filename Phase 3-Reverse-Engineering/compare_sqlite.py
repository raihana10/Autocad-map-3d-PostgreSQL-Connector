#!/usr/bin/env python3
"""
compare_sqlite.py
============================

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
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path


# =============================================================================
# FONCTION 1/12 : split_sql_statements(sql_text)
# =============================================================================
# ROLE
#   Decouper un texte SQL brut en une liste d'instructions individuelles
#   (chacune se terminant par ';').
#
# POURQUOI PAS sql_text.split(";") ?
#   Un point-virgule peut apparaitre A L'INTERIEUR d'une chaine de
#   caracteres -- par exemple une valeur texte dans un INSERT :
#       INSERT INTO tb_adresse VALUES(1, 'Rue Victor Hugo; batiment B');
#   Un split() naif couperait cette instruction en deux, et la seconde
#   moitie serait du SQL invalide qui ferait planter l'execution.
#
# COMMENT CA MARCHE
#   On parcourt le texte caractere par caractere en maintenant deux
#   booleens d'etat, in_single et in_double, qui indiquent si on est
#   actuellement A L'INTERIEUR d'une chaine '...' ou "...". Un ';' ne
#   declenche une coupure QUE si on n'est dans aucune des deux.
#   On gere aussi le cas de l'apostrophe echappee en SQL : '' a l'interieur
#   d'une chaine '...' represente une apostrophe litterale (pas une fin de
#   chaine) -- sans ce cas particulier, un nom comme O'Brien casserait le
#   decoupage au milieu du mot.
#La fonction lit le texte caractère par caractère (pas mot par mot, pas ligne par ligne) et maintient en permanence deux "drapeaux" qui représentent où on se trouve
# in_single : True si on est actuellement à l'intérieur d'une chaîne délimitée par des apostrophes '...'
# in_double : True si on est actuellement à l'intérieur d'une chaîne délimitée par des guillemets "..."
# buf (buffer) accumule les caractères de l'instruction en cours de construction. 
# statements est la liste finale des instructions complètes.=============================================================================
def split_sql_statements(sql_text: str):
    statements = [] # ce qu'on va retourner à la fin
    buf = [] # instruction en cours de construction (liste de caractères)
    in_single = False # au départ, on n'est dans aucune chaîne
    in_double = False 
    i = 0 # index de lecture dans le texte
    n = len(sql_text) # longueur totale, pour savoir quand s'arrêter
    # on utilise une boucle while pour qu'on puisse sauter des chars dans quelques cas (échappement)
    while i < n:
        # chaque chars lu est ajouté au buffer
        ch = sql_text[i]
        buf.append(ch)
        # Condition : le caractère est une apostrophe, ET on n'est pas déjà dans une chaîne "..." (le not in_double est important : si on est entre "", une ' est juste un caractère normal du texte, ex. "L'objet" : elle ne doit rien déclencher).
        if ch == "'" and not in_double:
            # gere l'echappement '' (apostrophe litterale dans SQLite , Ex: INSERT INTO tb_class VALUES(1, 'L''objet');)
            # in_single : on est bien déjà dans une chaîne (donc cette apostrophe pourrait être une fin de chaîne OU un échappement)
            # i + 1 < n : il reste au moins un caractère après (sécurité pour ne pas sortir du texte)
            # sql_text[i + 1] == "'" : le caractère suivant est aussi une apostrophe
            if in_single and i + 1 < n and sql_text[i + 1] == "'":
                buf.append(sql_text[i + 1])
                i += 2 # avancer l'index de 2 car '' 
                continue
            in_single = not in_single # si on n'était pas dans une chaîne, on y entre (False → True) ; si on y était, on en sort (True → False)
        elif ch == '"' and not in_single:
            in_double = not in_double
            #le caractère est un ; ET on n'est dans aucune des deux chaînes , donc c'est la fin d'une instruction SQL complète
        elif ch == ";" and not in_single and not in_double:
            stmt = "".join(buf).strip()
            if stmt and stmt != ";":
                statements.append(stmt)
            buf = [] # on réinitialise le buffer pour commencer à accumuler la prochaine instruction
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


# =============================================================================
# FONCTION 2/12 : safe_executescript(conn, sql_text, label)
# =============================================================================
# ROLE
#   Executer, une par une, toutes les instructions produites par
#   split_sql_statements(), sur une connexion SQLite donnee.
#
# POURQUOI PAS conn.executescript(sql_text) (la methode native Python) ?
#   executescript() s'arrete a la PREMIERE erreur rencontree. Si un fichier
#   dump_testXX.sql contient un CREATE TABLE en double, ou une instruction
#   que SQLite ne supporte pas, TOUT LE RESTE du fichier serait perdu.
#   Ici, chaque instruction est dans son propre try/except : une erreur est
#   journalisee sur stderr mais n'interrompt pas le traitement des
#   instructions suivantes.
#
#   C'est un choix de ROBUSTESSE deliberement asymetrique : on prefere
#   recuperer 95% de l'information (et signaler les 5% manquants) plutot
#   que 0% par arret brutal. Pour un outil de comparaison (et non de
#   restauration exacte), ce compromis est le bon.
# =============================================================================
def safe_executescript(conn: sqlite3.Connection, sql_text: str, label: str):
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


# =============================================================================
# STRUCTURES DE DONNEES : ColumnInfo, TableSchema, SchemaSnapshot
# =============================================================================
# Ce ne sont pas des fonctions mais de simples CONTENEURS DE DONNEES TYPES
# (l'equivalent d'un struct en C). Le decorateur @dataclass genere
# automatiquement le constructeur (__init__), sans qu'on ait a l'ecrire.
#   ColumnInfo     -> une colonne : nom, type, NOT NULL, valeur par defaut,position dans la cle primaire (0 si pas PK).
#   TableSchema    -> une table = son SQL de creation brut (utile pour les contraintes CHECK que PRAGMA ne capture pas) + un dictionnaire {nom_colonne: ColumnInfo} + la liste de ses cles etrangeres.
#   SchemaSnapshot -> l'etat COMPLET d'un fichier schema_testXX.sql a un instant donne : toutes ses tables, index, triggers,vues.
# Ce sont ces structures que produit load_schema() et que consomme compare_schemas(). Elles servent de "pont" entre le monde SQLite et le monde Python pur.
# Nous avons besoin de ces structures pour stocker les informations extraites de SQLite dans un format Python exploitable, afin de pouvoir comparer les schémas et les dumps de manière efficace et structurée.
# Elles transforment "du SQL qu'on doit reparser à chaque comparaison" en "des objets Python qu'on compare une fois pour toutes
# =============================================================================
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


# =============================================================================
# FONCTION 3/12 : load_schema(path) -> SchemaSnapshot
# =============================================================================
# ROLE
#   Transformer un fichier schema_testXX.sql en objets Python exploitables.
#   C'est ICI que se joue le choix d'architecture central du script.
#
# ETAPES
#   1. Ouvre une connexion SQLite EN MEMOIRE (:memory:) -- une base
#      temporaire qui vit en RAM et disparait a la fermeture, sans jamais
#      toucher le disque.
#   2. Charge le contenu du fichier et l'execute via safe_executescript()
#      -- c'est SQLITE LUI-MEME qui parse et valide le SQL a ce moment-la,
#      pas une regex ecrite a la main. Si le SQL est syntaxiquement
#      invalide, SQLite le rejette avec une vraie erreur de parsing.
#   3. Interroge sqlite_master (une table systeme maintenue automatiquement
#      par SQLite) pour lister TOUS les objets crees : type, nom, et SQL
#      brut exact ayant servi a les creer.
#   4. Pour chaque TABLE trouvee :
#        - PRAGMA table_info(nom)        -> remplit un ColumnInfo par
#          colonne (PRAGMA = extension SQLite pour interroger ses propres
#          metadonnees internes, generees a la volee, pas une vraie table)
#        - PRAGMA foreign_key_list(nom)  -> remplit la liste des cles
#          etrangeres (donc les RELATIONS entre classes, cf Test 9)
#   5. Pour les INDEX / TRIGGER / VIEW : simplement stockes par
#      nom -> SQL brut (pas besoin d'une structure plus fine, on les
#      compare tels quels par nom et par texte).
#
# A la fin, conn.close() detruit la base en memoire -- mais les donnees ont
# deja ete extraites vers des objets Python purs, donc rien n'est perdu.
# =============================================================================
def load_schema(path: str) -> SchemaSnapshot:
    conn = sqlite3.connect(":memory:")
    sql_text = Path(path).read_text(encoding="utf-8", errors="replace")
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


# =============================================================================
# FONCTION 4/12 : load_dump(path, fallback_schema_path=None) -> dict
# =============================================================================
# ROLE
#   Meme logique que load_schema(), mais pour extraire les DONNEES plutot
#   que la structure.
#
# POINTS PARTICULIERS
#   - dump_defines_tables : verifie si le fichier contient deja ses propres
#     CREATE TABLE (cas d'un export ".dump" classique de sqlite3, qui
#     inclut schema + donnees dans le meme fichier). Si NON (fichier avec
#     seulement des INSERT), on charge d'abord fallback_schema_path pour
#     creer les tables AVANT de pouvoir inserer dedans -- sinon
#     "INSERT INTO tb_class" echouerait avec "no such table".
#   - Pour chaque table : recupere les noms de colonnes ET la liste des
#     colonnes de cle primaire (pk_cols) via PRAGMA table_info.
#   - Pour chaque ligne (raw_rows) : construit un dict {colonne: valeur},
#     puis calcule une CLE :
#         * s'il y a une PK  -> la cle est le tuple des valeurs de PK
#           (ex. (1,) pour id=1)
#         * sinon            -> la ligne entiere sert de cle (repli, moins
#           precis mais fonctionnel : deux lignes strictement identiques
#           seraient alors indiscernables)
#   - Retourne {table: {"columns": [...], "pk": [...], "rows": {cle: ligne}}}
#
# POURQUOI UN DICTIONNAIRE INDEXE PAR CLE (et pas juste une liste de
# lignes) ?
#   C'est ce choix qui permet ensuite a compare_dumps() de faire des
#   comparaisons LIGNE-A-LIGNE precises (par cle primaire) plutot qu'un
#   simple diff d'ensembles qui ne saurait pas distinguer "ligne modifiee"
#   de "ligne supprimee + ligne ajoutee".
# =============================================================================
def load_dump(path: str, fallback_schema_path: str = None) -> dict:
    conn = sqlite3.connect(":memory:")

    dump_sql = Path(path).read_text(encoding="utf-8", errors="replace")
    dump_defines_tables = "CREATE TABLE" in dump_sql.upper()

    # On ne charge le schema de secours QUE si le dump ne contient pas deja
    # ses propres CREATE TABLE. Cela evite des avertissements "table
    # already exists" inutiles quand le dump est autosuffisant.
    if fallback_schema_path and not dump_defines_tables:
        schema_sql = Path(fallback_schema_path).read_text(
            encoding="utf-8", errors="replace")
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


# =============================================================================
# FONCTION 5/12 : compare_schemas(old, new) -> dict
# =============================================================================
# ROLE
#   Le COEUR de la comparaison structurelle. Recoit deux SchemaSnapshot et
#   retourne un dictionnaire de diff avec des cles fixes (tables_added,
#   columns_modified, fk_added, etc.).
#
# LOGIQUE, DANS L'ORDRE
#   1. Tables : difference d'ensembles (set - set) entre les noms de
#      tables des deux snapshots -> tables_added / tables_removed.
#   2. Pour chaque table presente DANS LES DEUX versions :
#        a. Colonnes ajoutees/supprimees : difference d'ensembles sur les
#           noms de colonnes.
#        b. Colonnes modifiees : pour chaque colonne commune, compare
#           type, notnull, default, pk UN PAR UN ; si au moins une
#           propriete differe, on enregistre un dict `changes` ne
#           contenant QUE les proprietes qui ont change (pas de bruit
#           inutile dans le rapport -- si seul le type change, on
#           n'affiche pas "notnull: False -> False").
#        c. Cles etrangeres : difference d'ensembles sur les tuples de FK
#           (conversion en set(tuple(...)) car les listes brutes ne sont
#           pas hashables et ne peuvent donc pas entrer dans un set).
#   3. Index / triggers / vues : la sous-fonction interne
#      diff_named_objects() FACTORISE la meme logique (difference
#      d'ensembles de noms) pour les trois categories, evitant de repeter
#      3 fois un code identique.
# =============================================================================
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


# =============================================================================
# FONCTION 6/12 : compare_dumps(old_dump, new_dump) -> dict
# =============================================================================
# ROLE
#   Comparaison des DONNEES, table par table.
#
# LOGIQUE
#   Pour chaque table presente dans l'un ou l'autre dump :
#     - added_keys / removed_keys : difference d'ensembles sur les CLES
#       (PK) des lignes.
#     - common_keys : cles presentes dans les deux -> pour chacune,
#       compare COLONNE PAR COLONNE l'ancienne et la nouvelle ligne ; si
#       une valeur differe, elle est ajoutee a changed_cols.
#       C'EST CE MECANISME QUI PRODUIT "GeometryType: NULL -> POINT" au
#       lieu d'un simple couple (ligne supprimee, ligne ajoutee) qui
#       masquerait le lien de cause a effet entre les deux etats.
#     - Une table n'apparait dans le resultat final que si elle a AU MOINS
#       UN changement (if added or removed or modified) -- pas de bruit
#       pour les tables inchangees dans le rapport final.
# =============================================================================
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


# =============================================================================
# FONCTION 7/12 : summarize_diff(schema_diff, dump_diff) -> dict
# =============================================================================
# ROLE
#   Une fonction PUREMENT COMPTABLE : prend les deux dictionnaires de diff
#   detailles et les reduit a de simples compteurs (nombre de tables
#   ajoutees, colonnes modifiees, lignes ajoutees, etc.) via des
#   sum(len(...) for ...).
#
# A QUOI CA SERT
#   Uniquement au MODE BATCH, pour construire la ligne de synthese d'une
#   transition dans le tableau recapitulatif global. Sans cette fonction,
#   il faudrait re-parcourir tout le detail (potentiellement des centaines
#   de lignes) a chaque fois qu'on veut juste un chiffre pour le tableau
#   de synthese.
# =============================================================================
def summarize_diff(schema_diff: dict, dump_diff: dict) -> dict:
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


# =============================================================================
# FONCTION 8/12 : generate_report(schema_diff, dump_diff, old_label, new_label)
#                 -> str
# =============================================================================
# ROLE
#   Transforme les deux dictionnaires de diff en TEXTE MARKDOWN lisible,
#   directement integrable dans le memoire.
#
# STRUCTURE
#   Une fonction interne section(title) ajoute un titre "## ..." -- evite
#   de repeter lines.append(...) a chaque section.
#   Le corps est une suite de blocs suivant TOUS le meme schema : si la
#   categorie a des entrees, les lister ; sinon, ecrire "Aucune".
#
# POURQUOI CE CODE EST VOLONTAIREMENT REPETITIF (et pas factorise a
# l'extreme via une boucle generique sur toutes les categories) ?
#   Chaque section a un format d'affichage LEGEREMENT DIFFERENT : une
#   colonne modifiee affiche plusieurs proprietes indentees (type,
#   notnull, default...), une table ajoutee est une simple puce, une ligne
#   de donnee modifiee affiche une cle + des sous-lignes par colonne.
#   Factoriser a outrance aurait rendu le code plus compact mais BEAUCOUP
#   plus difficile a suivre et a modifier section par section -- un choix
#   de lisibilite assume, important a justifier a l'oral si on vous
#   demande "pourquoi ne pas avoir fait une boucle unique ?".
# =============================================================================
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


import re  # noqa: E402


# =============================================================================
# FONCTION 9/12 : discover_test_files(directory) -> dict
# =============================================================================
# ROLE
#   Scanne un dossier avec deux expressions regulieres
#   (schema_test0*(\d+)\.sql$ et l'equivalent pour dump) pour reperer tous
#   les fichiers suivant la convention de nommage du projet, quel que soit
#   le nombre de zeros de padding (test06 ou test6 matchent pareil grace
#   au "0*" dans le pattern).
#
# LOGIQUE
#   Construit deux dictionnaires temporaires schemas et dumps
#   (numero -> chemin), puis ne garde dans le resultat final QUE les
#   numeros presents DANS LES DEUX -- avec un avertissement explicite sur
#   stderr pour chaque numero incomplet, plutot que de le faire echouer
#   silencieusement (pire cas : un test ignore sans que l'utilisateur s'en
#   rende compte) ou de planter tout le programme (pire cas : un seul
#   fichier manquant bloque l'analyse des 17 autres tests).
# =============================================================================
def discover_test_files(directory: str) -> dict:
    schema_pat = re.compile(r"schema_test0*(\d+)\.sql$", re.IGNORECASE)
    dump_pat = re.compile(r"dump_test0*(\d+)\.sql$", re.IGNORECASE)

    schemas, dumps = {}, {}
    for path in Path(directory).iterdir():
        if not path.is_file():
            continue
        m = schema_pat.match(path.name)
        if m:
            schemas[int(m.group(1))] = str(path)
            continue
        m = dump_pat.match(path.name)
        if m:
            dumps[int(m.group(1))] = str(path)

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


# =============================================================================
# FONCTION 10/12 : run_batch(directory, out_dir)
# =============================================================================
# ROLE
#   Orchestre tout le MODE BATCH (comparer une serie entiere de tests en
#   une seule commande).
#
# ETAPES
#   1. Appelle discover_test_files(), trie les numeros trouves.
#   2. zip(numbers, numbers[1:]) -- une astuce Python classique pour
#      generer les PAIRES CONSECUTIVES d'une liste :
#          [6, 7, 9]  ->  (6,7) puis (7,9)
#      Cela gere NATURELLEMENT les numeros manquants (comme les Tests
#      13-15 exclus du projet) sans avoir a ecrire de code special pour
#      "sauter" un trou -- c'est juste une consequence de la structure de
#      la liste triee.
#   3. Pour chaque paire : reutilise EXACTEMENT les memes fonctions que le
#      mode simple (load_schema, load_dump, compare_schemas,
#      compare_dumps, generate_report) -- AUCUNE duplication de logique,
#      juste une boucle autour. C'est le principe DRY (Don't Repeat
#      Yourself) applique concretement.
#   4. Accumule les compteurs de summarize_diff() dans summary_rows.
#   5. A la fin, construit un tableau Markdown recapitulatif
#      (rapport_synthese.md) avec une ligne par transition et un lien vers
#      le rapport detaille correspondant.
# =============================================================================
def run_batch(directory: str, out_dir: str):
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


# =============================================================================
# FONCTION 11/12 (structurellement le meme role que 12, voir plus bas)
# FONCTION 12/12 : main()
# =============================================================================
# ROLE
#   Le point d'entree CLI (Command Line Interface).
#
# ARGUMENTS (via argparse)
#   - 4 arguments positionnels MAIS OPTIONNELS (nargs="?") : c'est
#     necessaire pour permettre le mode batch, ou on ne les fournit pas du
#     tout. Sans nargs="?", argparse exigerait toujours ces 4 fichiers,
#     meme en mode batch.
#   - --batch-dir et --out-dir : specifiques au mode batch.
#
# LOGIQUE DE BRANCHEMENT
#       if args.batch_dir:
#           run_batch(...)   # mode batch, s'arrete ici (return immediat)
#           return
#
#       if not all([...]):   # sinon, verifie que les 4 fichiers sont
#           parser.error(...) # bien fournis pour le mode paire
#
#   Puis, en MODE PAIRE, la suite est lineaire et sequentielle : charger
#   les 2 schemas, charger les 2 dumps, comparer, generer le rapport,
#   l'ecrire sur disque. Aucune branche conditionnelle supplementaire --
#   c'est le chemin "simple" du script, celui qu'on utilise pour un test
#   isole.
# =============================================================================
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
