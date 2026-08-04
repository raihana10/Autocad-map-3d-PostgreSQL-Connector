#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
PROJET : Autocad-map-3d-PostgreSQL-Connector
MODULE  : Service d'automatisation et de surveillance en arrière-plan (File Watcher)
PHASE   : Phase 5 — Automatisatisation de la relance (A + E)
===============================================================================

DESCRIPTION :
Ce script fonctionne comme un service/démon d'arrière-plan.
Il surveille en temps réel le fichier SQLite du Data Model (`datamodel.sqlite`).

Dès que l'administrateur modifie et sauvegarde le Data Model dans 
Autodesk Infrastructure Administrator :
1. Le script détecte instantanément la modification du fichier SQLite.
2. Il ré-exécute automatiquement le convertisseur Python `convert_autodesk_to_postgis.py`.
3. Il crée automatiquement la base PostgreSQL si elle n'existe pas.
4. Il applique automatiquement le DDL mis à jour dans la base PostgreSQL (via psycopg2).

RECHERCHE GÉNÉRALE AUTOMATIQUE :
Il effectue une recherche dynamique et générique dans le répertoire temporaire système (%TEMP%)
ou dans un dossier spécifié, sans dépendre d'un chemin fixe ou personnalisé.

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

# Force l'encodage UTF-8 pour la console Windows afin d'éviter les erreurs charmap
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Intervalle de vérification en secondes
CHECK_INTERVAL_SECONDS = 2


def split_sql_statements(sql_content: str):
    """
    Découpe un script SQL en instructions exécutables sans casser :
    - les commentaires SQL (`--` et `/* ... */`)
    - les chaînes simples / identifiants quotés
    - les blocs PL/pgSQL délimités par $$ ... $$ ou $tag$ ... $tag$
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


def is_autodesk_sqlite(file_path: str) -> bool:
    """
    Vérifie si un fichier SQLite est un Data Model Autodesk valide
    en contrôlant la présence de la table système 'TB_DICTIONARY'.
    """
    try:
        if not os.path.isfile(file_path):
            return False
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='TB_DICTIONARY';")
        has_tb_dict = cursor.fetchone() is not None
        conn.close()
        return has_tb_dict
    except Exception:
        return False


def find_autodesk_sqlite(search_dir: str = None, model_name: str = None) -> str:
    """
    Effectue une recherche générale et dynamique d'un fichier SQLite Autodesk.
    - search_dir : répertoire racine où chercher (par défaut: %TEMP% du système).
    - model_name : nom spécifique de l'Industry Model (optionnel).
    
    Retourne le chemin du fichier valide le plus récemment modifié.
    """
    base_dir = search_dir if search_dir else tempfile.gettempdir()
    print(f"[🔍] Recherche générale dans : {base_dir}")
    
    candidates = []
    
    # Parcours récursif des sous-dossiers
    for root, _, files in os.walk(base_dir):
        for f in files:
            # Filtrage optionnel par nom si spécifié
            if model_name and model_name.lower() not in f.lower() and model_name.lower() not in root.lower():
                continue
                
            full_path = os.path.join(root, f)
            
            # Vérification si c'est un SQLite Autodesk valide
            if is_autodesk_sqlite(full_path):
                mtime = os.path.getmtime(full_path)
                candidates.append((mtime, full_path))
                
    if not candidates:
        return None
        
    # Tri par date de modification (le plus récent en premier)
    candidates.sort(key=lambda x: x[0], reverse=True)
    latest_file = candidates[0][1]
    return latest_file


def clean_postgres_db_name(name: str) -> str:
    """
    Nettoie et formate une chaîne pour être un nom de base de données PostgreSQL valide.
    """
    if not name:
        return ""
    import re
    import unicodedata
    
    # Normalisation pour enlever les accents (ex: donné -> donne)
    nfkd_form = unicodedata.normalize('NFKD', name)
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('ASCII')
    
    # Passage en minuscules
    cleaned = only_ascii.lower()
    # Remplacer tout caractère non-alphanumérique par des tirets bas
    cleaned = re.sub(r'[^a-z0-9]+', '_', cleaned)
    # Supprimer les tirets bas multiples ou en extrémités
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    
    return cleaned


def get_industry_model_name(sqlite_path: str) -> str:
    """
    Lit le nom de l'Industry Model depuis la table système Autodesk 'TB_INFO'.
    Retourne None si la table ou la clé 'DOCUMENT_NAME' n'existe pas.
    """
    try:
        if not os.path.isfile(sqlite_path):
            return None
        conn = sqlite3.connect(sqlite_path, timeout=5.0)
        cursor = conn.cursor()
        # On vérifie d'abord si la table TB_INFO existe pour éviter d'élever une exception inutilement
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
        print(f"[⚠️] Note lors de la récupération du nom du modèle (TB_INFO) : {e}")
    return None


def ensure_pg_database_exists(host="localhost", port=5432, user="postgres", password="", dbname="autocad_test"):
    """
    Vérifie si la base de données PostgreSQL existe, et la crée automatiquement si nécessaire.
    """
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
        
        # 1. Connexion à la base par défaut 'postgres'
        conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname="postgres")
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # 2. Vérification de l'existence de la base cible
        cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s;", (dbname,))
        exists = cursor.fetchone()
        
        if not exists:
            print(f"[⚙] La base de données '{dbname}' n'existe pas encore. Création automatique...")
            cursor.execute(f'CREATE DATABASE "{dbname}";')
            print(f"[✔] Base de données '{dbname}' créée avec succès !")
            
            # Activer l'extension PostGIS sur la nouvelle base
            conn_new = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname)
            cursor_new = conn_new.cursor()
            cursor_new.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
            conn_new.commit()
            cursor_new.close()
            conn_new.close()
            print(f"[✔] Extension PostGIS activée sur '{dbname}'.")
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[⚠️] Note lors de la vérification de la BDD PostgreSQL : {e}")


def run_conversion_and_apply(sqlite_path: str, output_sql: str, pg_host="localhost", pg_port=5432, pg_user="postgres", pg_pass="", pg_db=None, srid: int = 2154):
    """
    Exécute le script de conversion et applique le DDL directement sur PostgreSQL.
    """
    print(f"\n[⚡ AUTO-SYNC] Détection d'une modification dans {Path(sqlite_path).name} !")
    print(f"[⚙] Lancement automatique du convertisseur Python...")
    
    # Si aucun nom de BDD n'est fourni, on tente de le récupérer depuis la table système Autodesk
    if not pg_db:
        model_name = get_industry_model_name(sqlite_path)
        if model_name:
            cleaned_db = clean_postgres_db_name(model_name)
            if cleaned_db:
                print(f"[⚙] Industry Model Autodesk détecté dans SQLite : '{model_name}' -> Base PostgreSQL cible : '{cleaned_db}'")
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
        print(f"[✔] Conversion DDL réussie -> {output_sql}")
        
        if pg_user and pg_pass:
            try:
                import psycopg2
                
                # S'assurer que la base existe
                ensure_pg_database_exists(host=pg_host, port=pg_port, user=pg_user, password=pg_pass, dbname=pg_db)
                
                print(f"[⚙] Application automatique du DDL sur la base '{pg_db}' ({pg_host}:{pg_port})...")
                conn = psycopg2.connect(host=pg_host, port=pg_port, user=pg_user, password=pg_pass, dbname=pg_db)
                conn.autocommit = True
                cursor = conn.cursor()
                sql_content = Path(output_sql).read_text(encoding="utf-8")
                
                # Exécution des instructions SQL avec journalisation détaillée
                success_count = 0
                created_tables = []
                created_domains = []
                created_indexes = []
                created_fks = 0
                created_triggers = []
                failed_statements = []
                
                print("\n[📊 DÉBUT D'APPLICATION DU SCHÉMA EN BASE POSTGRESQL]")
                
                for stmt_clean in split_sql_statements(sql_content):
                    stmt_upper = stmt_clean.upper()
                    try:
                        cursor.execute(stmt_clean + ";")
                        conn.commit()
                        success_count += 1

                        # Détection du type de requête pour affichage détaillé
                        if "CREATE TABLE IF NOT EXISTS" in stmt_upper or "CREATE TABLE" in stmt_upper:
                            parts = stmt_clean.split('"')
                            tname = parts[1] if len(parts) > 1 else "Table"
                            if tname.endswith("_TBD") or tname == "TB_DOMAIN":
                                if tname not in created_domains:
                                    created_domains.append(tname)
                                    print(f"    [📦 Table Domaine]  '{tname}' créée")
                            else:
                                if tname not in created_tables:
                                    created_tables.append(tname)
                                    print(f"    [✨ Feature Class]  '{tname}' créée")
                        elif "CREATE INDEX" in stmt_upper:
                            parts = stmt_clean.split('"')
                            idx_name = parts[1] if len(parts) > 1 else "Index"
                            if idx_name not in created_indexes:
                                created_indexes.append(idx_name)
                                print(f"    [🗺️ Index Spatial]  '{idx_name}' créé")
                        elif "FOREIGN KEY" in stmt_upper:
                            created_fks += 1
                        elif "CREATE TRIGGER" in stmt_upper:
                            parts = stmt_clean.split('"')
                            trg_name = parts[1] if len(parts) > 1 else "Trigger"
                            if trg_name not in created_triggers:
                                created_triggers.append(trg_name)
                                print(f"    [⚡ Trigger PL/pgSQL] '{trg_name}' activé")
                    except Exception as ex:
                        conn.rollback()
                        first_line = stmt_clean.splitlines()[0][:120]
                        failed_statements.append((first_line, str(ex)))
                        print(f"    [❌ SQL] {first_line}")
                        print(f"         -> {ex}")
                            
                cursor.close()
                conn.close()
                
                print("\n[📋 RÉCAPITULATIF DES TABLES ET ÉLÉMENTS CRÉÉS EN BASE]")
                print(f"    📌 Feature Classes (Métiers) : {len(created_tables)} table(s)")
                if created_tables:
                    print(f"       -> {', '.join(created_tables)}")
                print(f"    📌 Tables de Domaines (_TBD) : {len(created_domains)} table(s)")
                if created_domains:
                    print(f"       -> {', '.join(created_domains)}")
                print(f"    📌 Index Spatiaux GiST       : {len(created_indexes)} index")
                print(f"    📌 Clés Étrangères (FK)       : {created_fks} contrainte(s)")
                print(f"    📌 Triggers Spatiaux PL/pgSQL: {len(created_triggers)} trigger(s)")
                if failed_statements:
                    print(f"    📌 Requêtes en échec          : {len(failed_statements)}")
                    print(f"[⚠] Synchronisation partielle ({success_count} requêtes SQL exécutées, {len(failed_statements)} en échec).\n")
                else:
                    print(f"[✔] Synchronisation PostgreSQL 100% réussie ({success_count} requêtes SQL exécutées) !\n")
            except ImportError:
                print("[ℹ] Module 'psycopg2' non installé. Installez-le avec : pip install psycopg2-binary")
            except Exception as e:
                print(f"[❌] Erreur lors de l'application sur PostgreSQL : {e}")
        else:
            print("[ℹ] Aucun identifiant PostgreSQL fourni. Seul le fichier SQL a été généré.")
    else:
        print(f"[❌] Erreur lors de la conversion DDL : {result.stderr}")


def find_all_autodesk_sqlites(search_dir: str = None, model_name: str = None) -> list:
    """
    Parcourt le dossier temporaire (%TEMP% par défaut) et retourne TOUS les fichiers SQLite Autodesk valides.
    Chaque modèle est associé à son nom propre et son nom de base PostgreSQL nettoyé.
    """
    base_dir = search_dir if search_dir else tempfile.gettempdir()
    found_models = []
    seen_paths = set()
    
    for root, _, files in os.walk(base_dir):
        for f in files:
            if model_name and model_name.lower() not in f.lower() and model_name.lower() not in root.lower():
                continue
                
            full_path = os.path.join(root, f)
            if full_path in seen_paths:
                continue
                
            if is_autodesk_sqlite(full_path):
                seen_paths.add(full_path)
                raw_name = get_industry_model_name(full_path)
                if not raw_name:
                    raw_name = Path(full_path).stem
                    
                db_name = clean_postgres_db_name(raw_name)
                if not db_name:
                    db_name = clean_postgres_db_name(Path(full_path).stem)
                    
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
    Service de surveillance multi-modèles (Multi-Watcher) :
    Surveille simultanément TOUS les Industry Models Autodesk actifs dans %TEMP% (ou un modèle cible).
    Chaque modèle est synchronisé dans sa propre base PostgreSQL dédiée sans interférence.
    """
    print("===================================================================")
    print(" 🚀 SERVICE DE SURVEILLANCE AUTOMATIQUE MULTI-MODÈLES AUTODESK")
    print("===================================================================")
    print(f"[🔍] Zone de surveillance : {search_dir or tempfile.gettempdir()}")
    print(f"[⏱] Fréquence de contrôle : Toutes les {CHECK_INTERVAL_SECONDS} secondes.")
    if pg_user and pg_pass:
        print("[🗄] Mode : Génération DDL + Application auto sur PostgreSQL (Bases dédiées par modèle)")
    else:
        print("[📄] Mode : Génération des fichiers DDL uniquement")
    print("[Presser CTRL+C pour arrêter le service]\n")

    monitored = {}  # db_name -> { "path": ..., "mtime": ..., "output_sql": ... }
    
    # Premier passage de détection
    if sqlite_path and os.path.exists(sqlite_path):
        raw_name = get_industry_model_name(sqlite_path) or Path(sqlite_path).stem
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
        print("[⚠️] Aucun Industry Model Autodesk actif trouvé pour le moment.")
        print("[👀] Le service reste en attente de l'ouverture d'un Data Model...\n")

    for m in initial_list:
        db = m["db_name"]
        print(f"[📍 INDUSTRY MODEL DÉTECTÉ] '{m['model_name']}'")
        print(f"    ├─ SQLite source   : {m['path']}")
        print(f"    ├─ Base PostgreSQL : '{db}'")
        print(f"    └─ Fichier DDL     : '{m['output_sql']}'\n")
        
        monitored[db] = {
            "path": m["path"],
            "mtime": m["mtime"],
            "output_sql": m["output_sql"]
        }
        
        if run_initial_sync:
            run_conversion_and_apply(
                sqlite_path=m["path"],
                output_sql=m["output_sql"],
                pg_host=pg_host,
                pg_port=pg_port,
                pg_user=pg_user,
                pg_pass=pg_pass,
                pg_db=db,
                srid=srid
            )
            
    try:
        while True:
            time.sleep(CHECK_INTERVAL_SECONDS)
            
            if sqlite_path and os.path.exists(sqlite_path):
                raw_name = get_industry_model_name(sqlite_path) or Path(sqlite_path).stem
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
                
            for m in active_models:
                db = m["db_name"]
                fpath = m["path"]
                curr_mtime = m["mtime"]
                out_sql = m["output_sql"]
                
                # Nouveau modèle ouvert dans Autodesk pendant l'exécution
                if db not in monitored:
                    print(f"\n[🆕 NOUVEAU DATA MODEL DÉTECTÉ] '{m['model_name']}'")
                    print(f"    ├─ SQLite source   : {fpath}")
                    print(f"    ├─ Base PostgreSQL : '{db}'")
                    print(f"    └─ Fichier DDL     : '{out_sql}'")
                    
                    monitored[db] = {
                        "path": fpath,
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
                # Modèle existant qui a été modifié par l'utilisateur
                elif curr_mtime != monitored[db]["mtime"]:
                    monitored[db]["mtime"] = curr_mtime
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
    except KeyboardInterrupt:
        print("\n[⏹] Arrêt du service de surveillance automatique multi-modèles.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Surveille un ou plusieurs Data Models Autodesk et applique automatiquement le DDL dans PostgreSQL."
    )
    parser.add_argument("--db", dest="sqlite_file", default=None, help="Chemin explicite vers un fichier Data Model SQLite (optionnel)")
    parser.add_argument("--dir", dest="search_dir", default=None, help="Dossier racine pour la recherche générale (def: %%TEMP%%)")
    parser.add_argument("--name", dest="model_name", default=None, help="Nom de l'Industry Model spécifique à rechercher (optionnel)")
    parser.add_argument("--out", dest="output_sql", default=None, help="Fichier SQL généré (def: schema_<dbname>.sql)")
    
    # Paramètres PostgreSQL
    parser.add_argument("--pg-host", dest="pg_host", default="localhost", help="Hôte du serveur PostgreSQL (def: localhost)")
    parser.add_argument("--pg-port", dest="pg_port", type=int, default=5432, help="Port PostgreSQL (def: 5432)")
    parser.add_argument("--pg-user", dest="pg_user", default=os.getenv("PG_USER"), help="Nom d'utilisateur PostgreSQL (ex: postgres)")
    parser.add_argument("--pg-pass", dest="pg_pass", default=os.getenv("PG_PASSWORD"), help="Mot de passe PostgreSQL")
    parser.add_argument("--pg-db", dest="pg_db", default=None, help="Nom de la BDD PostgreSQL cible (optionnel)")
    
    parser.add_argument("--srid", type=int, default=2154, help="Code EPSG / SRID spatial PostGIS (def: 2154)")
    parser.add_argument("--initial-sync", action="store_true", help="Exécute une synchronisation immédiate au démarrage.")

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
