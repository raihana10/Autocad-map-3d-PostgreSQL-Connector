# Phase 5 — Architecture Cible & Solution Alternative

> **Phase 5 du projet** — Définition et justification de la solution alternative pour la conversion et l'exploitation du Data Model Autodesk sous PostgreSQL/PostGIS.

---

## 1. Objectif de la phase

L'objectif de la Phase 5 est de définir l'architecture technique permettant d'exploiter un **Data Model Autodesk Infrastructure Administrator** avec une base de données **PostgreSQL / PostGIS**, sans dépendre d'Oracle, SQL Server ni du connecteur propriétaire payant TKI PGP.

La solution doit répondre à deux exigences :
1. **Génération du schéma DDL** : Traduire fidèlement la structure du Data Model SQLite vers PostgreSQL/PostGIS.
2. **Exploitation temps réel** : Permettre à AutoCAD Map 3D d'interagir (lecture et écriture) avec la base PostgreSQL.

---

## 2. Synthèse des architectures étudiées

| Approche | Description | Statut | Justification |
|---|---|---|---|
| **A. Génération de scripts SQL (Python)** | Lecture du Data Model SQLite et génération automatique du DDL PostGIS. | **Retenue (Étape 1)** | Génère de façon exacte et contrôlée la structure relationnelle et spatiale. |
| **B. Synchronisation périodique ETL** | Script de synchronisation par lots à intervalles réguliers. | **Éliminée** | Ne permet pas l'édition en temps réel exigée lors de la saisie cartographique. |
| **C. Plugin C# / .NET (API Map 3D)** | Développement d'une extension cliente native dans Map 3D. | **Éliminée** | Complexité et courbe d'apprentissage trop élevées pour le périmètre temporel d'un PFA. |
| **D. Plugin Java** | Application cliente en Java. | **Éliminée** | L'écosystème Autodesk est orienté .NET ; aucune API Java officielle n'existe pour Map 3D. |
| **E. Connecteur FDO PostgreSQL Natif** | Utilisation du provider FDO PostgreSQL natif d'AutoCAD Map 3D. | **Retenue (Étape 2)** | Réutilise le moteur d'accès natif et officiel d'Autodesk pour l'édition temps réel. |

---

## 3. Architecture retenue : Combinaison A + E (Génération + Connexion FDO)

La solution retenue combine l'**Approche A** et l'**Approche E** pour offrir une chaîne complète, robuste et dynamique :

```
┌─────────────────────────────────────────────────────────┐
│              1. Data Model Source (SQLite)              │
└────────────────────────────┬────────────────────────────┘
                             │
                             │ [Approche A]
                             │ Script Python spécialisé
                             │ (Lecture des métadonnées)
                             ▼
┌─────────────────────────────────────────────────────────┐
│        2. Base PostgreSQL / PostGIS (Schéma DDL)        │
└────────────────────────────▲────────────────────────────┘
                             │
                             │ [Approche F]
                             │ Connecteur FDO Natif PostgreSQL
                             │ (Édition & Lecture temps réel)
                             ▼
┌─────────────────────────────────────────────────────────┐
│               3. Application AutoCAD Map 3D             │
└─────────────────────────────────────────────────────────┘
```

### Fonctionnement du duo A + E :
* **Approche A (Génération initiale)** : Un script Python lit la structure du Data Model SQLite et génère le fichier `schema_postgres.sql`. Cette étape prépare le réceptacle dans PostgreSQL (tables, types FDO, géométries PostGIS, contraintes et index spatiaux GIST).
* **Approche E (Exploitation dynamique)** : AutoCAD Map 3D se connecte à la base PostgreSQL via son connecteur **FDO PostgreSQL natif**. Chaque ajout, modification ou suppression effectué par le dessinateur dans Map 3D est répercuté **en temps réel (Live Read/Write)** dans PostgreSQL.

---

## 4. Spécificité du moteur de conversion (Approche A)

### Pourquoi filtrer sur 4 tables clés et ne pas tout convertir ?
Le fichier SQLite d'origine contient environ 170 tables, dont plus de 150 sont des tables d'interface utilisateur ou de configuration système d'AutoCAD (`TB_GN_*`, `TB_SETTINGS`, `TB_SEQUENCE_EMULATION`).

Le script Python de l'Approche A cible exclusivement les **4 catalogues maîtres de métadonnées** identifiés en Phase 3 :

1. **`TB_DICTIONARY`** : Liste uniquement les vraies entités métier (`F_CLASS_NAME`) et leur type d'objet (`F_CLASS_TYPE` : Point, LineString, Polygon, ou Table d'attributs).
2. **`TB_ATTRIBUTE`** : Isole les attributs métier définis par l'utilisateur pour chaque classe.
3. **`fdo_columns`** : Restitue le **typage logique FDO réel** (`fdo_data_type` : Varchar, Number, Double, Boolean) et sa précision (`fdo_data_length`), bien plus précis que le type générique SQLite.
4. **`geometry_columns`** : Fournit le nom de la colonne spatiale (`GEOM`) et le type de géométrie OGC standard.

---

## 5. Protocole de mise en œuvre étape par étape

1. **Étape 1 — Écriture du script Python (`convert_autodesk_to_postgis.py`)** :
   Développer le script lisant les tables `TB_DICTIONARY`, `TB_ATTRIBUTE`, `fdo_columns`, `geometry_columns` et `TB_RELATIONS` pour produire le code DDL PostgreSQL.

2. **Étape 2 — Validation DDL sous PostgreSQL / PostGIS** :
   Exécuter le script SQL dans PostgreSQL et vérifier la bonne création des tables métiers, des contraintes et des index GIST.

3. **Étape 3 — Raccordement temps réel dans AutoCAD Map 3D** :
   Établir la connexion FDO natif PostgreSQL dans Map 3D (`_MAPCONNECT`), charger les couches et tester la création/modification d'objets en direct.

4. **Étape 4 — Bilan et documentation finale** :
   Capturer les preuves d'interaction bidirectionnelle entre Map 3D et PostgreSQL pour valider définitivement la Phase 5.
