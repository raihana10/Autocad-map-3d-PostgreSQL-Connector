# Phase 5 — Architecture Cible & Solution Alternative

> **Phase 5 du projet** — Définition, implémentation et validation de la solution alternative pour la conversion et l'exploitation du Data Model Autodesk sous PostgreSQL/PostGIS.

---

## 1. Objectif de la phase

L'objectif de la Phase 5 est d'implémenter l'architecture technique permettant d'exporter et d'exploiter un **Data Model Autodesk Infrastructure Administrator** sous une base de données **PostgreSQL / PostGIS**, en se passant totalement d'Oracle, de SQL Server et du plugin payant tiers TKI PGP.

La solution répond à deux exigences fondamentales :
1. **Génération automatisée du schéma DDL (Approche A)** : Traduction exacte de la structure du Data Model SQLite (classes, attributs, domaines de valeurs, relations, clés étrangères, index spatiaux, triggers) vers PostgreSQL/PostGIS.
2. **Exploitation temps réel bidirectionnelle (Approche E)** : Utilisation du connecteur FDO PostgreSQL natif d'AutoCAD Map 3D (`_MAPCONNECT`) pour l'édition cartographique en direct.

---

## 2. Synthèse et justification des architectures étudiées

Pour identifier la meilleure solution alternative à TKI PGP, 5 approches techniques ont été évaluées :

| Approche | Description | Statut | Justification de la décision |
|---|---|---|---|
| **A. Générateur DDL Python** | Script d'introspection du SQLite Autodesk et génération automatique du script SQL PostGIS. | **Retenue (Étape 1)** | Offre un contrôle total et exact sur la structure relationnelle, le typage FDO, les clés étrangères, les index GiST et les triggers PL/pgSQL. |
| **B. Synchronisation par lots (ETL)** | Export/Import périodique des données entre SQLite et PostgreSQL à des intervalles réguliers. | **Éliminée** | Incompatible avec le travail collaboratif temps réel. Risque élevé de conflits d'édition et perte de réactivité lors de la saisie cartographique. |
| **C. Plugin C# / .NET (API Map 3D)** | Développement d'une extension cliente DLL intégrée directement dans AutoCAD Map 3D. | **Éliminée** | Complexité et courbe d'apprentissage trop élevées pour le calendrier du PFA. Nécessite une recompilation et un déploiement sur chaque poste client. |
| **D. Plugin Java (API)** | Développement d'une application ou extension en Java. | **Éliminée** | L'écosystème Autodesk est exclusivement orienté .NET / C++. Aucune API Java officielle n'existe pour AutoCAD Map 3D. |
| **E. Connecteur FDO PostgreSQL Natif** | Utilisation du provider FDO PostgreSQL natif intégré d'AutoCAD Map 3D (`_MAPCONNECT`). | **Retenue (Étape 2)** | Réutilise le moteur spatial natif et officiel d'Autodesk, garantissant une édition temps réel transparente sans aucun plugin tiers. |

---

## 3. Architecture Globale Retenue (Combinaison A + E)

```
┌────────────────────────────────────────────────────────────────────────┐
│                   1. Data Model Source (SQLite)                        │
│    Fichier extrait par Autodesk Infrastructure Administrator           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    │ [Approche A - Moteur Python]
                                    │ Introspection des 6 catalogues
                                    │ Détection dynamique %TEMP% & FK/PK
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│               2. Base PostgreSQL / PostGIS (Schéma DDL)                │
│    - Tables Métiers & Géométries PostGIS (Point, Line, Polygon)        │
│    - Tables de Domaines (_TBD) & Insertion des Valeurs Énumérées       │
│    - Clés Étrangères Dynamiques (FID pour classes, ID pour domaines)   │
│    - Index Spatiaux GiST sur colonnes géométriques                     │
│    - Triggers PL/pgSQL (Calculs automatiques ST_Length)                │
└───────────────────────────────────▲────────────────────────────────────┘
                                    │
                                    │ [Approche E - Connecteur Natif]
                                    │ FDO PostgreSQL Provider (Map 3D)
                                    │ (Lecture & Édition temps réel)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 3. Poste Client AutoCAD Map 3D                         │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Spécifications du Moteur de Conversion (`convert_autodesk_to_postgis.py`)

### 4.1 Introspection des 6 Catalogues de Métadonnées Maîtres
Le fichier SQLite Autodesk contient ~170 tables, dont la majorité gère la configuration UI. Notre moteur cible spécifiquement les 6 catalogues maîtres identifiés en Phase 3 :

1. **`TB_DICTIONARY`** : Repertoire principal des entités métiers (`F_CLASS_NAME`), typage FDO (`F_CLASS_TYPE` : Point, LineString, Polygon, Table) et gestion de l'héritage (`MODEL_F_CLASS_ID`).
2. **`TB_ATTRIBUTE`** : Liste des attributs configurés pour chaque classe métier.
3. **`fdo_columns`** : Restitution du typage FDO natif (`data_type` : Varchar, Number, Double, Boolean) et longueurs/précisions.
4. **`geometry_columns`** : Identification de la colonne spatiale (`GEOM`), du type OGC standard et du SRID (EPSG 2154 par défaut / Lambert-93).
5. **`TB_DOMAIN` + Tables `<DOMAIN>_TBD`** : Extraction des énumérations/domaines de valeurs et génération des ordres `INSERT` d'initialisation.
6. **`TB_RELATIONS`** : Cartographie des contraintes d'intégrité inter-classes et classe-domaine.

### 4.2 Dynamic Column Introspection & Résolution FK/PK
* **Tolérance aux variations de versions** : La fonction `find_col_name()` inspecte les colonnes réelles des tables SQLite système pour s'adapter dynamiquement aux variations de nommage d'Autodesk.
* **Gestion différenciée des Clés Étrangères** : La fonction `get_pk_column_name()` identifie dynamiquement la clé primaire de la table parente :
  - Clé `FID` pour les liaisons entre classes métiers.
  - Clé `ID` pour les liaisons vers les tables de domaines de valeurs (`_TBD`).

### 4.3 Intégration Spatial & Triggers PL/pgSQL
* **Index Spatiaux** : Génération automatique d'index `GIST` pour chaque colonne géométrique.
* **Calculs automatiques** : Déploiement d'un trigger PL/pgSQL (`fn_calc_autodesk_length`) recalculant la longueur des lignes (`ST_Length`) sur chaque `INSERT` ou `UPDATE`.

---

## 5. Moteur de Surveillance et Synchronisation Arrière-Plan (`watch_and_sync.py`)

### 5.1 Recherche Générale et Dynamique dans `%TEMP%`
Autodesk Infrastructure Administrator décompresse l'Industry Model dans des dossiers temporaires aux sous-dossiers GUID dynamiques (ex: `AppData\Local\Temp\Embedded\<GUID>\`).
* Le script utilise `tempfile.gettempdir()` (%TEMP% Windows).
* Il effectue une recherche récursive sans chemin en dur et valide la présence de la table `TB_DICTIONARY`.
* En cas de doublons, il filtre et sélectionne automatiquement l'instance la plus récente selon l'horodatage (`st_mtime`).

### 5.2 Synchronisation Non-Destructive
Pour préserver l'intégralité des données géométriques et attributaires saisies sous PostgreSQL par les géomaticiens :
* Utilisation exclusive des requêtes `CREATE TABLE IF NOT EXISTS`.
* Insertion sécurisée des domaines via `INSERT ON CONFLICT DO NOTHING`.
* Évolution de schéma via `ALTER TABLE ADD COLUMN IF NOT EXISTS`.

### 5.3 Nommage Automatique de la Base de Données
Nom de la BDD PostgreSQL = Nom de l'Industry Model SQLite (ex: `Industry model initial` → BDD `industry_model_initial`). Cette convention garantit que les employés connaissent toujours le nom exact de la base de données.

---

## 6. Plan de Déploiement et Industrialisation (Feuille de Route Phase 6)

Pour la mise en production en entreprise (zéro commande pour les cartographes) :

1. **Interface Graphique d'Administration (GUI Admin Panel)** :
   - Développée sous **CustomTkinter** (Python).
   - Permet à l'administrateur de renseigner les identifiants PostgreSQL et de choisir le mode de détection (Automatique via `%TEMP%` ou Sélection manuelle de fichier SQLite).
   - Sauvegarde chiffrée des identifiants une seule fois.
2. **Packaging & Service Windows d'Arrière-Plan** :
   - Compilation sous forme d'exécutable autonome (`.exe`) via **PyInstaller**.
   - Déploiement en tant que **Service Windows** (via **NSSM**) démarrant automatiquement au boot du serveur/poste.
   - Icône System Tray (barre des tâches) pour consulter le statut de synchro et les logs.
3. **Multi-Modèles Simultanés** :
   - Prise en charge de la surveillance simultanée de plusieurs Industry Models.
4. **Expérience Employé dans AutoCAD Map 3D** :
   - Fichiers de profil FDO partagés (`.fdo` / `.xml`) préparés par l'Admin.
   - Les cartographes cliquent sur la connexion enregistrée et travaillent directement sans aucune manipulation technique.

---

## 7. Bilan et Validation de la Phase 5

Le test complet a été exécuté avec succès sur le modèle `Industry model initial` :
- Génération d'un fichier DDL PostGIS propre (`test_schema.sql`).
- Validation des 261 lignes SQL créant les tables métiers, tables de domaines peuplées, contraintes FK adaptées (`ID`/`FID`), index GiST et triggers spatiaux PL/pgSQL.
