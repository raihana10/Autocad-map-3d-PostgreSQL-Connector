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
1. Le script détecte instantanément la modification de date/heure du fichier SQLite.
2. Il ré-exécute automatiquement le convertisseur Python `convert_autodesk_to_postgis.py`.
3. Il applique automatiquement le DDL mis à jour dans la base PostgreSQL distante (via psycopg2).

RÉSULTAT :
La synchronisation de la structure (DDL) devient 100% AUTOMATIQUE, sans aucune
intervention humaine !

===============================================================================
"""

import os
import sys
import time
import subprocess
import argparse
from pathlib import Path

# Intervalle de vérification en secondes (ex: vérifier toutes les 2 secondes)
CHECK_INTERVAL_SECONDS = 2

def run_conversion_and_apply(sqlite_path: str, output_sql: str, pg_conn_string: str = None, srid: int = 2154):
    """
    Exécute le script de conversion et applique éventuellement le DDL sur PostgreSQL.
    """
    print(f"\n[⚡ AUTO-SYNC] Détection d'une modification dans {Path(sqlite_path).name} !")
    print(f"[⚙] Lancement automatique du convertisseur Python...")
    
    # 1. Exécution du convertisseur convert_autodesk_to_postgis.py
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
        
        # 2. Si une chaîne de connexion PostgreSQL est fournie, appliquer directement les requêtes
        if pg_conn_string:
            try:
                import psycopg2
                print("[⚙] Application automatique du DDL sur le serveur PostgreSQL...")
                conn = psycopg2.connect(pg_conn_string)
                cursor = conn.cursor()
                sql_content = Path(output_sql).read_text(encoding="utf-8")
                cursor.execute(sql_content)
                conn.commit()
                cursor.close()
                conn.close()
                print("[✔] Schéma PostgreSQL mis à jour avec succès en temps réel !")
            except ImportError:
                print("[ℹ] Module 'psycopg2' non installé. Le fichier SQL a été généré mais non exécuté directement en base.")
            except Exception as e:
                print(f"[❌] Erreur lors de l'application sur PostgreSQL : {e}")
    else:
        print(f"[❌] Erreur lors de la conversion DDL : {result.stderr}")


def watch_file(sqlite_path: str, output_sql: str, pg_conn_string: str = None, srid: int = 2154, run_initial_sync: bool = False):
    """
    Boucle de surveillance du fichier SQLite.
    """
    target_file = Path(sqlite_path)
    if not target_file.exists():
        print(f"Erreur : Le fichier à surveiller n'existe pas : {sqlite_path}")
        sys.exit(1)
        
    print("===================================================================")
    print(" 🚀 SERVICE DE SURVEILLANCE AUTOMATIQUE DU DATA MODEL AUTODESK")
    print("===================================================================")
    print(f"[👀] Surveillance active sur : {target_file.resolve()}")
    print(f"[⏱] Fréquence de contrôle : Toutes les {CHECK_INTERVAL_SECONDS} secondes.")
    if pg_conn_string:
        print("[🗄] Mode : génération + application automatique dans PostgreSQL")
    else:
        print("[📄] Mode : génération du fichier DDL uniquement (pas d'application PostgreSQL)")
    print("[Presser CTRL+C pour arrêter le service]\n")
    
    last_mtime = target_file.stat().st_mtime

    if run_initial_sync:
        run_conversion_and_apply(sqlite_path, output_sql, pg_conn_string, srid)
    
    try:
        while True:
            time.sleep(CHECK_INTERVAL_SECONDS)
            if target_file.exists():
                current_mtime = target_file.stat().st_mtime
                if current_mtime != last_mtime:
                    last_mtime = current_mtime
                    run_conversion_and_apply(sqlite_path, output_sql, pg_conn_string, srid)
    except KeyboardInterrupt:
        print("\n[⏹] Arrêt du service de surveillance automatique.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Surveille un Data Model Autodesk et applique automatiquement le DDL dans PostgreSQL."
    )
    parser.add_argument("sqlite_file", help="Chemin vers le fichier Data Model SQLite")
    parser.add_argument("output_sql", nargs="?", default="schema_postgis_autosync.sql", help="Fichier SQL généré")
    parser.add_argument("--pg-conn", dest="pg_conn_string", default=os.getenv("PG_CONN_STRING"),
                        help="Chaîne de connexion PostgreSQL/psycopg2. Peut aussi venir de la variable d'environnement PG_CONN_STRING.")
    parser.add_argument("--srid", type=int, default=2154, help="Code EPSG / SRID spatial PostGIS (def: 2154)")
    parser.add_argument("--initial-sync", action="store_true",
                        help="Exécute une synchronisation immédiate au démarrage, sans attendre une première modification du fichier.")

    args = parser.parse_args()

    watch_file(
        args.sqlite_file,
        args.output_sql,
        pg_conn_string=args.pg_conn_string,
        srid=args.srid,
        run_initial_sync=args.initial_sync
    )
