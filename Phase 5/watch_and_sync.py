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
3. Il applique automatiquement le DDL mis à jour dans la base PostgreSQL (via psycopg2).

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

# Intervalle de vérification en secondes
CHECK_INTERVAL_SECONDS = 2


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


def run_conversion_and_apply(sqlite_path: str, output_sql: str, pg_conn_string: str = None, srid: int = 2154):
    """
    Exécute le script de conversion et applique éventuellement le DDL sur PostgreSQL.
    """
    print(f"\n[⚡ AUTO-SYNC] Détection d'une modification dans {Path(sqlite_path).name} !")
    print(f"[⚙] Lancement automatique du convertisseur Python...")
    
    script_dir = Path(__file__).parent
    converter_script = script_dir / "convert_autodesk_to_postgis.py"
    
    cmd = [
        sys.executable,
        str(converter_script),
        "--db", sqlite_path,
        "--out", output_sql,
        "--srid", str(srid)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"[✔] Conversion DDL réussie -> {output_sql}")
        
        if pg_conn_string:
            try:
                import psycopg2
                print("[⚙] Application automatique du DDL sur le serveur PostgreSQL...")
                conn = psycopg2.connect(pg_conn_string)
                cursor = conn.cursor()
                sql_content = Path(output_sql).read_text(encoding="utf-8")
                
                # Exécution des instructions
                for stmt in sql_content.split(";"):
                    stmt_clean = stmt.strip()
                    if stmt_clean and not stmt_clean.startswith("--"):
                        try:
                            cursor.execute(stmt_clean + ";")
                            conn.commit()
                        except Exception as ex:
                            conn.rollback()
                            
                cursor.close()
                conn.close()
                print("[✔] Schéma PostgreSQL mis à jour avec succès en temps réel !")
            except ImportError:
                print("[ℹ] Module 'psycopg2' non installé. Le fichier SQL a été généré mais non exécuté en base.")
            except Exception as e:
                print(f"[❌] Erreur lors de l'application sur PostgreSQL : {e}")
    else:
        print(f"[❌] Erreur lors de la conversion DDL : {result.stderr}")


def watch_file(sqlite_path: str, output_sql: str, pg_conn_string: str = None, srid: int = 2154, run_initial_sync: bool = False):
    """
    Boucle de surveillance d'un fichier SQLite Autodesk avec support de redétection dynamique.
    """
    target_file = Path(sqlite_path)
    
    print("===================================================================")
    print(" 🚀 SERVICE DE SURVEILLANCE AUTOMATIQUE DU DATA MODEL AUTODESK")
    print("===================================================================")
    print(f"[👀] Surveillance active sur : {target_file.resolve()}")
    print(f"[⏱] Fréquence de contrôle : Toutes les {CHECK_INTERVAL_SECONDS} secondes.")
    if pg_conn_string:
        print("[🗄] Mode : Génération DDL + Application automatique PostgreSQL")
    else:
        print("[📄] Mode : Génération du fichier DDL uniquement")
    print("[Presser CTRL+C pour arrêter le service]\n")
    
    last_mtime = target_file.stat().st_mtime if target_file.exists() else 0

    if run_initial_sync and target_file.exists():
        run_conversion_and_apply(str(target_file), output_sql, pg_conn_string, srid)
    
    try:
        while True:
            time.sleep(CHECK_INTERVAL_SECONDS)
            if target_file.exists():
                current_mtime = target_file.stat().st_mtime
                if current_mtime != last_mtime:
                    last_mtime = current_mtime
                    run_conversion_and_apply(str(target_file), output_sql, pg_conn_string, srid)
            else:
                # Si le fichier s'est déplacé/a changé de GUID dans Temp, effectuer une nouvelle détection
                found = find_autodesk_sqlite()
                if found:
                    print(f"[🔄] Nouveau fichier détecté : {found}")
                    target_file = Path(found)
                    last_mtime = target_file.stat().st_mtime
                    run_conversion_and_apply(str(target_file), output_sql, pg_conn_string, srid)
    except KeyboardInterrupt:
        print("\n[⏹] Arrêt du service de surveillance automatique.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Surveille un Data Model Autodesk et applique automatiquement le DDL dans PostgreSQL."
    )
    parser.add_argument("--db", dest="sqlite_file", default=None, help="Chemin explicite vers le fichier Data Model SQLite (optionnel)")
    parser.add_argument("--dir", dest="search_dir", default=None, help="Dossier racine pour la recherche générale (def: %%TEMP%%)")
    parser.add_argument("--name", dest="model_name", default=None, help="Nom de l'Industry Model à rechercher")
    parser.add_argument("--out", dest="output_sql", default="schema_postgis_autosync.sql", help="Fichier SQL généré")
    parser.add_argument("--pg-conn", dest="pg_conn_string", default=os.getenv("PG_CONN_STRING"),
                        help="Chaîne de connexion PostgreSQL (ex: host=localhost dbname=my_db user=postgres password=secret)")
    parser.add_argument("--srid", type=int, default=2154, help="Code EPSG / SRID spatial PostGIS (def: 2154)")
    parser.add_argument("--initial-sync", action="store_true",
                        help="Exécute une synchronisation immédiate au démarrage.")

    args = parser.parse_args()

    sqlite_target = args.sqlite_file
    
    # Recherche générale si aucun chemin direct n'est fourni ou si le fichier fourni n'existe pas
    if not sqlite_target or not os.path.exists(sqlite_target):
        print("[ℹ] Aucun chemin fixe valide fourni. Lancement de la recherche générale...")
        sqlite_target = find_autodesk_sqlite(search_dir=args.search_dir, model_name=args.model_name)
        
    if not sqlite_target:
        print("[❌] Aucun fichier Data Model Autodesk valide trouvé dans le système.", file=sys.stderr)
        sys.exit(1)

    print(f"[✔] Data Model identifié : {sqlite_target}")

    watch_file(
        sqlite_target,
        args.output_sql,
        pg_conn_string=args.pg_conn_string,
        srid=args.srid,
        run_initial_sync=args.initial_sync
    )
