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
analyse les tables de métadonnées spécifiques d'Autodesk identifiées lors de la Phase 3
(TB_DICTIONARY, TB_ATTRIBUTE, fdo_columns, geometry_columns, TB_RELATIONS), et génère
un script SQL DDL PostgreSQL/PostGIS prêt à être exécuté.

POURQUOI INTERROGER UNIQUEMENT CES TABLES ET PAS LES 170 TABLES SQLITE ?
-------------------------------------------------------------------------------
Le fichier SQLite d'Autodesk contient ~170 tables. 150+ de ces tables sont de pures
tables d'interface graphique Windows / AutoCAD Map 3D (ex: TB_GN_FLYIN_USER, TB_SETTINGS)
ou d'émulation de séquences (TB_SEQUENCE_EMULATION).

Seules 5 tables de métadonnées constituent le "cerveau" du Data Model :
1. TB_DICTIONARY    : Catalogue des classes métiers (ex: VANNE, CANALISATION, REGARD).
2. TB_ATTRIBUTE     : Registre des attributs créés par l'utilisateur pour chaque classe.
3. fdo_columns      : Typage logique formel FDO (Texte, Nombre, Date, Booléen, Longueur).
4. geometry_columns : Encodage spatial OGC (Point, LineString, Polygon, SRID).
5. TB_RELATIONS     : Définition des associations (Clés étrangères classe ↔ classe ou classe ↔ domaine).

===============================================================================
"""

import sqlite3
import sys
import argparse
from pathlib import Path

# =============================================================================
# 1. TABLEAU DE CORRESPONDANCE DES TYPES (FDO -> POSTGRESQL)
# =============================================================================
# Dans Phase 3, nous avons découvert que fdo_columns stocke un code numérique (fdo_data_type)
# qui définit l'intention logique métier d'Autodesk, au-delà du simple type SQLite brut.
FDO_TO_POSTGRES_TYPES = {
    1: "boolean",           # FDO Boolean
    2: "smallint",          # FDO Byte
    3: "double precision",  # FDO Double (ex: LENGTH, ORIENTATION)
    4: "numeric",           # FDO Decimal
    5: "smallint",          # FDO Int16
    6: "integer",           # FDO Int32
    7: "integer",           # FDO Int64 / Number (ex: TEST_ATTRIBUT_02)
    9: "varchar",           # FDO String / Text (ex: TEST_ATTRIBUT_01)
    10: "timestamp",        # FDO DateTime
    11: "date",             # FDO Date
    13: "bytea"             # FDO BLOB
}

# Code géométrique OGC standard (geometry_columns) -> Type PostGIS
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

def get_autodesk_classes(conn: sqlite3.Connection):
    """
    Interroge TB_DICTIONARY (Catalogue maître des classes).
    Permet d'extraire uniquement les tables métier créées par l'utilisateur,
    en ignorant les 150+ tables système/interface.
    
    Retourne : Dictionnaire { F_CLASS_ID : { name, type, caption } }
    """
    cursor = conn.cursor()
    
    # Vérification que la table TB_DICTIONARY existe bien dans le SQLite
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='TB_DICTIONARY';")
    if not cursor.fetchone():
        raise ValueError("Erreur : La table système 'TB_DICTIONARY' est introuvable. Ce fichier SQLite n'est pas un Data Model Autodesk valide.")

    query = """
        SELECT F_CLASS_ID, F_CLASS_NAME, F_CLASS_TYPE, CAPTION
        FROM TB_DICTIONARY
        WHERE F_CLASS_NAME IS NOT NULL AND F_CLASS_NAME != '';
    """
    cursor.execute(query)
    classes = {}
    for class_id, class_name, class_type, caption in cursor.fetchall():
        classes[class_id] = {
            "name": class_name.strip(),
            "type": class_type.strip() if class_type else "N", # 'P'=Point, 'L'=Ligne, 'S'=Polygone, 'N'=Non géométrique
            "caption": caption.strip() if caption else class_name
        }
    return classes


def get_fdo_column_metadata(conn: sqlite3.Connection):
    """
    Interroge fdo_columns (Dictionnaire FDO).
    Récupère le vrai type logique FDO, la longueur maximale (fdo_data_length)
    et la précision (fdo_data_precision).
    
    Retourne : Dictionnaire { (table_name, column_name) : { data_type, length, precision } }
    """
    cursor = conn.cursor()
    fdo_meta = {}
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fdo_columns';")
    if cursor.fetchone():
        query = """
            SELECT fdo_feature_class_name, fdo_column_name, fdo_data_type, fdo_data_length, fdo_data_precision
            FROM fdo_columns;
        """
        cursor.execute(query)
        for tbl, col, dtype, dlen, dprec in cursor.fetchall():
            if tbl and col:
                fdo_meta[(tbl.strip().upper(), col.strip().upper())] = {
                    "data_type": dtype,
                    "length": dlen,
                    "precision": dprec
                }
    return fdo_meta


def get_spatial_metadata(conn: sqlite3.Connection):
    """
    Interroge geometry_columns (Catalogue spatial OGC).
    Identifie la colonne géométrique (souvent 'GEOM') et son type spatial (Point, LineString...).
    
    Retourne : Dictionnaire { table_name : { geom_col, geom_type_name, srid } }
    """
    cursor = conn.cursor()
    spatial_meta = {}
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='geometry_columns';")
    if cursor.fetchone():
        query = """
            SELECT f_table_name, f_geometry_column, geometry_type, srid
            FROM geometry_columns;
        """
        cursor.execute(query)
        for tbl, gcol, gtype, srid in cursor.fetchall():
            if tbl:
                spatial_meta[tbl.strip().upper()] = {
                    "geom_col": gcol.strip() if gcol else "GEOM",
                    "geom_type": GEOM_TYPE_MAP.get(gtype, "Geometry"),
                    "srid": srid if (srid and srid > 0) else 2154 # Par défaut Lambert-93 / SRID projet
                }
    return spatial_meta


def get_physical_column_info(conn: sqlite3.Connection, table_name: str):
    """
    Interroge PRAGMA table_info(table) de SQLite pour capturer les contraintes DDL physiques
    (NOT NULL, DEFAULT) identifiées lors des Tests 4 et 5 de la Phase 3.
    """
    cursor = conn.cursor()
    cursor.execute(f'PRAGMA table_info("{table_name}");')
    # Structure PRAGMA : (cid, name, type, notnull, dflt_value, pk)
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
    Interroge TB_RELATIONS (Catalogue des liens classe-classe et classe-domaine).
    Identifié lors du Test 9 et du Test 10.2 en Phase 3.
    
    Retourne : Liste de dictionnaires d'associations FK
    """
    cursor = conn.cursor()
    relations = []
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='TB_RELATIONS';")
    if cursor.fetchone():
        query = """
            SELECT PARENT_TABLE_NAME, CHILD_TABLE_NAME, FK_COLUMN_NAME
            FROM TB_RELATIONS
            WHERE PARENT_TABLE_NAME IS NOT NULL AND CHILD_TABLE_NAME IS NOT NULL;
        """
        cursor.execute(query)
        for parent, child, fk_col in cursor.fetchall():
            relations.append({
                "parent": parent.strip(),
                "child": child.strip(),
                "fk_col": fk_col.strip() if fk_col else f"{parent.strip()}_ID"
            })
    return relations


# =============================================================================
# 3. MOTEUR DE GÉNÉRATION DU DDL POSTGRESQL / POSTGIS
# =============================================================================

def generate_postgis_ddl(sqlite_path: str, default_srid: int = 2154) -> str:
    """
    Fonction principale de conversion.
    Lit le SQLite Autodesk et construit le script DDL SQL final.
    """
    conn = sqlite3.connect(sqlite_path)
    
    # 1. Extraction des métadonnées Autodesk
    classes = get_autodesk_classes(conn)
    fdo_meta = get_fdo_column_metadata(conn)
    spatial_meta = get_spatial_metadata(conn)
    relations = get_autodesk_relations(conn)
    
    ddl_lines = []
    ddl_lines.append("-- ============================================================")
    ddl_lines.append("-- DDL GENERATED AUTOMATICALLY BY Autocad-map-3d-PostgreSQL-Connector")
    ddl_lines.append(f"-- Source File : {Path(sqlite_path).name}")
    ddl_lines.append(f"-- Target Database : PostgreSQL / PostGIS (SRID {default_srid})")
    ddl_lines.append("-- ============================================================\n")
    ddl_lines.append("CREATE EXTENSION IF NOT EXISTS postgis;\n")
    
    # 2. Boucle sur chaque classe métier trouvée dans TB_DICTIONARY
    for class_id, class_info in classes.items():
        tbl_name = class_info["name"]
        class_type = class_info["type"]
        caption = class_info["caption"]
        
        # Vérifier que la table existe physiquement dans SQLite
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tbl_name}';")
        if not cursor.fetchone():
            continue # Table présente dans le catalogue mais pas encore créée physiquement
        
        phys_cols = get_physical_column_info(conn, tbl_name)
        tbl_spatial = spatial_meta.get(tbl_name.upper(), {})
        
        ddl_lines.append(f"-- ------------------------------------------------------------")
        ddl_lines.append(f"-- Feature Class : {tbl_name} ({caption}) [Type FDO: {class_type}]")
        ddl_lines.append(f"-- ------------------------------------------------------------")
        ddl_lines.append(f'CREATE TABLE IF NOT EXISTS "{tbl_name}" (')
        
        column_defs = []
        pk_columns = []
        spatial_columns_to_index = []
        
        for col_upper, pinfo in phys_cols.items():
            col_name = pinfo["name"]
            
            # Règle spéciale : Clé primaire FID (découverte Test 1)
            if pinfo["pk"] or col_upper == "FID":
                pk_columns.append(f'"{col_name}"')
                column_defs.append(f'    "{col_name}" integer NOT NULL')
                continue
            
            # Règle spéciale : Champ Géométrie PostGIS (découverte Test 7 & 8)
            if col_upper == tbl_spatial.get("geom_col", "GEOM").upper() or (class_type in ['P', 'L', 'S'] and col_upper == "GEOM"):
                gtype = tbl_spatial.get("geom_type")
                if not gtype or gtype == "Geometry":
                    # Fallback sur F_CLASS_TYPE de TB_DICTIONARY
                    if class_type == 'P': gtype = "Point"
                    elif class_type == 'L': gtype = "LineString"
                    elif class_type == 'S': gtype = "Polygon"
                    else: gtype = "Geometry"
                
                srid = tbl_spatial.get("srid", default_srid)
                column_defs.append(f'    "{col_name}" geometry({gtype}, {srid})')
                spatial_columns_to_index.append((col_name, tbl_name))
                continue
            
            # Traduction du type de donnée via fdo_columns ou fallback SQLite
            fmeta = fdo_meta.get((tbl_name.upper(), col_upper), {})
            fdo_dtype = fmeta.get("data_type")
            
            if fdo_dtype in FDO_TO_POSTGRES_TYPES:
                pg_type = FDO_TO_POSTGRES_TYPES[fdo_dtype]
                if pg_type == "varchar" and fmeta.get("length"):
                    pg_type = f"varchar({fmeta['length']})"
            else:
                # Fallback sur type physique SQLite si absente de fdo_columns
                raw = pinfo["raw_type"].upper()
                if "INT" in raw: pg_type = "integer"
                elif "CHAR" in raw or "TEXT" in raw: pg_type = "text"
                elif "REAL" in raw or "DOUBLE" in raw or "FLOAT" in raw: pg_type = "double precision"
                else: pg_type = "text"
            
            col_str = f'    "{col_name}" {pg_type}'
            
            # Ajout des contraintes NOT NULL (Test 5) et DEFAULT (Test 4)
            if pinfo["notnull"]:
                col_str += " NOT NULL"
            if pinfo["default"] is not None:
                col_str += f" DEFAULT {pinfo['default']}"
                
            column_defs.append(col_str)
        
        # Ajout de la contrainte PRIMARY KEY
        if pk_columns:
            column_defs.append(f'    PRIMARY KEY ({", ".join(pk_columns)})')
            
        ddl_lines.append(",\n".join(column_defs))
        ddl_lines.append(");\n")
        
        # 3. Création des Index Spatiaux GIST (PostGIS)
        for gcol, tname in spatial_columns_to_index:
            idx_name = f"idx_{tname}_{gcol}_gist"
            ddl_lines.append(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{tname}" USING GIST ("{gcol}");\n')
            
    # 4. Création des Clés Étrangères (Test 9 & Test 10.2)
    if relations:
        ddl_lines.append("-- ------------------------------------------------------------")
        ddl_lines.append("-- Foreign Keys & Relationships (TB_RELATIONS)")
        ddl_lines.append("-- ------------------------------------------------------------")
        for rel in relations:
            parent = rel["parent"]
            child = rel["child"]
            fk_col = rel["fk_col"]
            fk_constraint_name = f"fk_{child}_{fk_col}_{parent}"
            
            # Sécurité : vérifier que parent et child existent dans le dictionnaire
            ddl_lines.append(
                f'ALTER TABLE "{child}" ADD CONSTRAINT "{fk_constraint_name}" '
                f'FOREIGN KEY ("{fk_col}") REFERENCES "{parent}" ("FID") ON DELETE SET NULL;'
            )
        ddl_lines.append("")
        
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
