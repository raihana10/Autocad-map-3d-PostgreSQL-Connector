#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
PROJET : Autocad-map-3d-PostgreSQL-Connector
MODULE  : Convertisseur de Data Model Autodesk (SQLite) -> PostgreSQL / PostGIS
PHASE   : Phase 5 — Architecture Cible (Approche A)
===============================================================================

DESCRIPTION :
Ce script lit un fichier SQLite exporté depuis Autodesk Infrastructure Administrator,
analyse les 6 catalogues de métadonnées spécifiques d'Autodesk identifiés lors de la Phase 3
(TB_DICTIONARY, TB_ATTRIBUTE, fdo_columns, geometry_columns, TB_DOMAIN, TB_RELATIONS),
et génère un script SQL DDL PostgreSQL/PostGIS complet avec :
- Tables métiers & types FDO exacts
- Géométries PostGIS (Point, LineString, Polygon) & Index Spatiaux GiST
- Tables de domaines (_TBD) et peuplement automatique des valeurs
- Clés Étrangères (FOREIGN KEY) entre classes et vers les domaines
- Triggers PL/pgSQL pour calculs automatiques (ex: ST_Length)

===============================================================================
"""

import sqlite3
import sys
import argparse
from pathlib import Path

# =============================================================================
# 1. TABLEAU DE CORRESPONDANCE DES TYPES (FDO -> POSTGRESQL)
# =============================================================================
FDO_TO_POSTGRES_TYPES = {
    1: "boolean",           # FDO Boolean
    2: "smallint",          # FDO Byte
    3: "double precision",  # FDO Double (ex: LENGTH, ORIENTATION)
    4: "numeric",           # FDO Decimal
    5: "smallint",          # FDO Int16
    6: "integer",           # FDO Int32
    7: "integer",           # FDO Int64 / Number
    9: "varchar",           # FDO String / Text
    10: "timestamp",        # FDO DateTime
    11: "date",             # FDO Date
    13: "bytea"             # FDO BLOB
}

GEOM_TYPE_MAP = {
    1: "Point",
    2: "LineString",
    3: "Polygon",
    4: "MultiPoint",
    5: "MultiLineString",
    6: "MultiPolygon"
}


# =============================================================================
# 2. FONCTIONS DE LECTURE DU DATA MODEL AUTODESK (PHASE 3)
# =============================================================================

def find_col_name(cursor, table_name: str, candidates: list):
    """
    Inspecte dynamiquement les colonnes d'une table SQLite pour trouver le nom exact d'une colonne parmi une liste de candidats.
    """
    try:
        cursor.execute(f'PRAGMA table_info("{table_name}");')
        cols = [row[1] for row in cursor.fetchall()]
        cols_lower = [c.lower() for c in cols]
        for cand in candidates:
            if cand.lower() in cols_lower:
                idx = cols_lower.index(cand.lower())
                return cols[idx]
    except Exception:
        pass
    return None


def get_autodesk_classes(conn: sqlite3.Connection):
    """
    Interroge TB_DICTIONARY (Catalogue maître des classes).
    Détecte dynamiquement les noms de colonnes.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='TB_DICTIONARY';")
    if not cursor.fetchone():
        raise ValueError("Erreur : La table système 'TB_DICTIONARY' est introuvable. Ce fichier SQLite n'est pas un Data Model Autodesk valide.")

    id_col = find_col_name(cursor, "TB_DICTIONARY", ["f_class_id", "class_id", "id"])
    name_col = find_col_name(cursor, "TB_DICTIONARY", ["f_class_name", "class_name", "name", "table_name"])
    type_col = find_col_name(cursor, "TB_DICTIONARY", ["f_class_type", "class_type", "type"])
    caption_col = find_col_name(cursor, "TB_DICTIONARY", ["caption", "label", "description", "title"])
    
    if not name_col:
        raise ValueError("Erreur : Impossible d'identifier la colonne du nom de classe dans 'TB_DICTIONARY'.")
        
    id_str = f'"{id_col}"' if id_col else "rowid"
    type_str = f'"{type_col}"' if type_col else "'N'"
    cap_str = f'"{caption_col}"' if caption_col else f'"{name_col}"'
    
    query = f'SELECT {id_str}, "{name_col}", {type_str}, {cap_str} FROM "TB_DICTIONARY" WHERE "{name_col}" IS NOT NULL AND "{name_col}" != \'\';'
    cursor.execute(query)
    classes = {}
    for class_id, class_name, class_type, caption in cursor.fetchall():
        classes[class_id] = {
            "name": str(class_name).strip(),
            "type": str(class_type).strip() if class_type else "N",
            "caption": str(caption).strip() if caption else str(class_name)
        }
    return classes


def get_fdo_column_metadata(conn: sqlite3.Connection):
    """
    Interroge fdo_columns (Dictionnaire FDO).
    Détecte dynamiquement les noms de colonnes pour éviter tout échec.
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


def get_spatial_metadata(conn: sqlite3.Connection):
    """
    Interroge geometry_columns (Catalogue spatial OGC).
    Détecte dynamiquement les noms de colonnes.
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


def get_physical_column_info(conn: sqlite3.Connection, table_name: str):
    """
    Interroge PRAGMA table_info(table) de SQLite.
    """
    cursor = conn.cursor()
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


def get_autodesk_relations(conn: sqlite3.Connection):
    """
    Interroge TB_RELATIONS (Catalogue des liaisons inter-classes et classe-domaine).
    Détecte dynamiquement les noms de colonnes.
    """
    cursor = conn.cursor()
    relations = []
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='TB_RELATIONS';")
    if cursor.fetchone():
        p_col = find_col_name(cursor, "TB_RELATIONS", ["parent_table_name", "parent_table", "parent_class_name", "parent_name", "table_name_parent"])
        c_col = find_col_name(cursor, "TB_RELATIONS", ["child_table_name", "child_table", "child_class_name", "child_name", "table_name_child"])
        fk_col = find_col_name(cursor, "TB_RELATIONS", ["fk_column_name", "fk_column", "foreign_key", "fk_name", "column_name", "fk_field"])
        
        if p_col and c_col:
            fk_str = f'"{fk_col}"' if fk_col else "NULL"
            query = f'SELECT "{p_col}", "{c_col}", {fk_str} FROM "TB_RELATIONS" WHERE "{p_col}" IS NOT NULL AND "{c_col}" IS NOT NULL;'
            try:
                cursor.execute(query)
                for parent, child, fk in cursor.fetchall():
                    if parent and child:
                        relations.append({
                            "parent": str(parent).strip(),
                            "child": str(child).strip(),
                            "fk_col": str(fk).strip() if fk else f"{str(parent).strip()}_ID"
                        })
            except Exception:
                pass
    return relations


def get_pk_column_name(conn: sqlite3.Connection, table_name: str) -> str:
    """
    Retourne le nom réel de la clé primaire d'une table SQLite.
    Cherche d'abord FID, puis ID, puis la première colonne PK PRAGMA.
    """
    cursor = conn.cursor()
    cursor.execute(f'PRAGMA table_info("{table_name}");')
    pk_cols = [(row[1], row[5]) for row in cursor.fetchall() if row[5] > 0]  # row[5] = pk flag
    if pk_cols:
        pk_name = pk_cols[0][0]
        return pk_name
    return "FID"  # Fallback


def get_domain_tables(conn: sqlite3.Connection):
    """
    Identifie toutes les tables de domaine (ex: tables finissant par _TBD ou présentes dans TB_DOMAIN).
    Récupère leurs colonnes et leurs enregistrements (valeurs du domaine).
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
        except Exception:
            pass
    return domain_tables


# =============================================================================
# 3. MOTEUR DE GÉNÉRATION DU DDL POSTGRESQL / POSTGIS
# =============================================================================

def generate_postgis_ddl(sqlite_path: str, default_srid: int = 2154) -> str:
    """
    Fonction principale de conversion.
    Lit le SQLite Autodesk et construit le script DDL SQL final.
    """
    conn = sqlite3.connect(sqlite_path)
    
    classes = get_autodesk_classes(conn)
    fdo_meta = get_fdo_column_metadata(conn)
    spatial_meta = get_spatial_metadata(conn)
    relations = get_autodesk_relations(conn)
    domain_tables = get_domain_tables(conn)
    
    ddl_lines = []
    ddl_lines.append("-- ============================================================")
    ddl_lines.append("-- DDL GENERATED AUTOMATICALLY BY Autocad-map-3d-PostgreSQL-Connector")
    ddl_lines.append(f"-- Source File : {Path(sqlite_path).name}")
    ddl_lines.append(f"-- Target Database : PostgreSQL / PostGIS (SRID {default_srid})")
    ddl_lines.append("-- ============================================================\n")
    ddl_lines.append("CREATE EXTENSION IF NOT EXISTS postgis;\n")
    
    # -------------------------------------------------------------------------
    # A. Génération des Tables de Domaines (_TBD) & Insertion des Valeurs (Tests 10.1, 11)
    # -------------------------------------------------------------------------
    if domain_tables:
        ddl_lines.append("-- ============================================================")
        ddl_lines.append("-- 1. TABLES DE DOMAINES DE VALEURS (_TBD) & VALEURS ENUMERÉES")
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
    # B. Génération des Tables Métiers (Classes)
    # -------------------------------------------------------------------------
    ddl_lines.append("-- ============================================================")
    ddl_lines.append("-- 2. FEATURE CLASSES (TABLES METIERS ET GEOMETRIES POSTGIS)")
    ddl_lines.append("-- ============================================================\n")
    
    triggers_to_generate = []
    
    for class_id, class_info in classes.items():
        tbl_name = class_info["name"]
        class_type = class_info["type"]
        caption = class_info["caption"]
        
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tbl_name}';")
        if not cursor.fetchone():
            continue
        
        phys_cols = get_physical_column_info(conn, tbl_name)
        tbl_spatial = spatial_meta.get(tbl_name.upper(), {})
        
        ddl_lines.append(f"-- ------------------------------------------------------------")
        ddl_lines.append(f"-- Feature Class : {tbl_name} ({caption}) [Type FDO: {class_type}]")
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
                column_defs.append(f'    "{col_name}" integer NOT NULL')
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
        
        for gcol, tname in spatial_columns_to_index:
            idx_name = f"idx_{tname}_{gcol}_gist"
            ddl_lines.append(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{tname}" USING GIST ("{gcol}");\n')
            
        if class_type == 'L' and has_length_col:
            triggers_to_generate.append((tbl_name, geom_col_name))

    # -------------------------------------------------------------------------
    # C. Création des Clés Étrangères (Relations inter-classes & Domaines) (Tests 9, 10.2)
    # -------------------------------------------------------------------------
    if relations:
        ddl_lines.append("-- ============================================================")
        ddl_lines.append("-- 3. FOREIGN KEYS & RELATIONS (TB_RELATIONS)")
        ddl_lines.append("-- ============================================================\n")
        for rel in relations:
            parent = rel["parent"]
            child = rel["child"]
            fk_col = rel["fk_col"]
            fk_constraint_name = f"fk_{child}_{fk_col}_{parent}"
            # Détecte dynamiquement la PK de la table parente (FID pour classes, ID pour domaines)
            parent_pk = get_pk_column_name(conn, parent)
            ddl_lines.append(
                f'ALTER TABLE "{child}" ADD CONSTRAINT "{fk_constraint_name}" '
                f'FOREIGN KEY ("{fk_col}") REFERENCES "{parent}" ("{parent_pk}") ON DELETE SET NULL;'
            )
        ddl_lines.append("")

    # -------------------------------------------------------------------------
    # D. Génération des Triggers PL/pgSQL (Calculs automatiques ST_Length)
    # -------------------------------------------------------------------------
    if triggers_to_generate:
        ddl_lines.append("-- ============================================================")
        ddl_lines.append("-- 4. TRIGGERS PL/PGSQL POUR CALCULS AUTOMATIQUES (EX: ST_LENGTH)")
        ddl_lines.append("-- ============================================================\n")
        
        ddl_lines.append("""
CREATE OR REPLACE FUNCTION fn_calc_autodesk_length()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.geom IS NOT NULL THEN
        NEW.length := ST_Length(NEW.geom);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
""")
        
        for tname, gcol in triggers_to_generate:
            trigger_name = f"trg_calc_length_{tname}"
            ddl_lines.append(f'DROP TRIGGER IF EXISTS "{trigger_name}" ON "{tname}";')
            ddl_lines.append(
                f'CREATE TRIGGER "{trigger_name}" '
                f'BEFORE INSERT OR UPDATE OF "{gcol}" ON "{tname}" '
                f'FOR EACH ROW EXECUTE FUNCTION fn_calc_autodesk_length();\n'
            )

    conn.close()
    return "\n".join(ddl_lines)


# =============================================================================
# 4. POINT D'ENTRÉE CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Convertisseur Data Model Autodesk SQLite -> Script DDL PostgreSQL/PostGIS"
    )
    parser.add_argument("--db", required=True, help="Chemin vers le fichier Data Model SQLite (*.sqlite)")
    parser.add_argument("--out", default="schema_postgis.sql", help="Nom du fichier SQL généré (def: schema_postgis.sql)")
    parser.add_argument("--srid", type=int, default=2154, help="Code EPSG / SRID spatial PostGIS (def: 2154 / Lambert-93)")
    
    args = parser.parse_args()
    
    db_file = Path(args.db)
    if not db_file.exists():
        print(f"Erreur : Fichier introuvable : {args.db}", file=sys.stderr)
        sys.exit(1)
        
    print(f"[+] Analyse du Data Model Autodesk : {db_file.name}")
    try:
        ddl_result = generate_postgis_ddl(str(db_file), default_srid=args.srid)
        out_file = Path(args.out)
        out_file.write_text(ddl_result, encoding="utf-8")
        print(f"[✔] Génération réussie ! Fichier DDL créé : {out_file.resolve()}")
    except Exception as e:
        print(f"[❌] Erreur lors de la conversion : {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
