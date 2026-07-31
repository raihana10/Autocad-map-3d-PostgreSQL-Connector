# Phase 5 — Architecture Cible & Solution Alternative

> **Phase 5 du projet** — Définition et justification de la solution alternative pour la conversion et l'exploitation du Data Model Autodesk sous PostgreSQL/PostGIS.

---

## 1. Objectif de la phase

L'objectif de la Phase 5 est de définir l'architecture technique permettant d'exploiter un **Data Model Autodesk Infrastructure Administrator** avec une base de données **PostgreSQL / PostGIS**, sans dépendre d'Oracle, SQL Server ni du connecteur propriétaire payant TKI PGP.

La solution doit répondre à deux exigences :
1. **Génération du schéma DDL** : Traduire fidèlement la structure du Data Model SQLite (classes, attributs, domaines, relations, héritage) vers PostgreSQL/PostGIS.
2. **Exploitation temps réel** : Permettre à AutoCAD Map 3D d'interagir (lecture et écriture) avec la base PostgreSQL avec un niveau de fonctionnalité équivalent à TKI PGP.

---

## 2. Synthèse des architectures étudiées

| Approche | Description | Statut | Justification |
|---|---|---|---|
| **A. Génération de scripts SQL (Python)** | Lecture du Data Model SQLite et génération automatique du DDL PostGIS. | **Retenue (Étape 1)** | Génère de façon exacte et contrôlée la structure relationnelle, spatiale et les contraintes. |
| **B. Synchronisation périodique ETL** | Script de synchronisation par lots à intervalles réguliers. | **Éliminée** | Ne permet pas l'édition en temps réel exigée lors de la saisie cartographique. |
| **C. Plugin C# / .NET (API Map 3D)** | Développement d'une extension cliente native dans Map 3D. | **Éliminée** | Complexité et courbe d'apprentissage trop élevées pour le périmètre temporel d'un PFA. |
| **D. Plugin Java** | Application cliente en Java. | **Éliminée** | L'écosystème Autodesk est orienté .NET ; aucune API Java officielle n'existe pour Map 3D. |
| **E. Connecteur FDO PostgreSQL Natif** | Utilisation du provider FDO PostgreSQL natif d'AutoCAD Map 3D. | **Retenue (Étape 2)** | Réutilise le moteur d'accès natif et officiel d'Autodesk pour l'édition temps réel. |

---

## 3. Architecture retenue : Combinaison A + E (Génération + Connexion FDO + Triggers)

La solution retenue combine l'**Approche A** et l'**Approche E** complétée par l'intelligence métier sous PostgreSQL :

```
┌─────────────────────────────────────────────────────────┐
│              1. Data Model Source (SQLite)              │
└────────────────────────────┬────────────────────────────┘
                             │
                             │ [Approche A]
                             │ Script Python spécialisé
                             │ (Lecture des 6 catalogues de métadonnées)
                             ▼
┌─────────────────────────────────────────────────────────┐
│        2. Base PostgreSQL / PostGIS (Schéma DDL)        │
│    - Tables Métiers & Géométries PostGIS                │
│    - Tables & Clés Étrangères de Domaines (_TBD)        │
│    - Relations Parent-Enfant (TB_RELATIONS)             │
│    - Triggers PL/pgSQL (Calculs & Contrôles Métiers)    │
└────────────────────────────▲────────────────────────────┘
                             │
                             │ [Approche E]
                             │ Connecteur FDO Natif PostgreSQL
                             │ (Édition & Lecture temps réel)
                             ▼
┌─────────────────────────────────────────────────────────┐
│               3. Application AutoCAD Map 3D             │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Spécificité du moteur de conversion (Approche A)

### Les 6 catalogues maîtres identifiés en Phase 3

Le fichier SQLite d'origine contient environ 170 tables, dont plus de 150 sont des tables d'interface utilisateur ou de configuration système d'AutoCAD (`TB_GN_*`, `TB_SETTINGS`, `TB_SEQUENCE_EMULATION`).

Pour couvrir l'intégralité des fonctionnalités d'un Industry Model et égaler TKI PGP, notre script Python cible les **6 catalogues maîtres de métadonnées** validés lors des tests de la Phase 3 :

1. **`TB_DICTIONARY`** : Liste les entités métier (`F_CLASS_NAME`), leur type d'objet (`F_CLASS_TYPE` : Point, LineString, Polygon, Table) et gère l'héritage de classes (`MODEL_F_CLASS_ID`, validé au Test 12).
2. **`TB_ATTRIBUTE`** : Isole les attributs métier définis pour chaque classe (validé aux Tests 2, 3, 4, 5).
3. **`fdo_columns`** : Restitue le **typage logique FDO réel** (`fdo_data_type` : Varchar, Number, Double, Boolean) et sa précision (`fdo_data_length`).
4. **`geometry_columns`** : Fournit la colonne spatiale (`GEOM`) et le type de géométrie OGC standard (validé aux Tests 7, 8).
5. **`TB_DOMAIN` + Tables `<DOMAIN>_TBD`** : Stocke les listes de valeurs autorisées / énumérations (ex: matériau, statut) (validé aux Tests 10.1, 11).
6. **`TB_RELATIONS`** : Stocke l'ensemble des liaisons inter-classes et le rattachement des attributs aux tables de domaines (validé aux Tests 9, 10.2).

### 4. Clés Étrangères Dynamiques (FID vs ID)
* **Mécanisme Autodesk** : Liaison entre classes métiers (référençant `FID`) et liaisons vers les tables de domaines `_TBD` (référençant `ID`).
* **Traduction PostgreSQL** : Introspection dynamique de la clé primaire (`PK`) de la table parente avant de générer la contrainte `FOREIGN KEY` (`"FID"` pour classes, `"ID"` pour domaines).

---

## 6. Moteur de Recherche et Synchronisation Arrière-Plan (`watch_and_sync.py`)

Pour garantir un fonctionnement 100% transparent et zéro-intervention pour les utilisateurs :

1. **Recherche Générale et Dynamique des Fichiers SQLite** :
   - Exploitation de `tempfile.gettempdir()` (%TEMP% Windows) pour éviter les chemins en dur.
   - Validation dynamique de l'Industry Model via la présence de la table `TB_DICTIONARY`.
   - Filtrage et sélection automatique du fichier le plus récent basé sur l'horodatage (`st_mtime`).
2. **Synchronisation Non Destructive** :
   - Utilisation systématique de `CREATE TABLE IF NOT EXISTS`, `INSERT ON CONFLICT DO NOTHING` et `ALTER TABLE ADD COLUMN IF NOT EXISTS`.
   - Maintien intégral des données géométriques et attributaires existantes saisies par les cartographes sous PostGIS lors des mises à jour du Data Model.

---

## 7. Protocole de validation et étapes de test

1. **Étape 1 — Écriture du script Python (`convert_autodesk_to_postgis.py`)** :
   Développer le script lisant les catalogues maîtres (`TB_DICTIONARY`, `TB_ATTRIBUTE`, `fdo_columns`, `geometry_columns`, `TB_DOMAIN`, `TB_RELATIONS`) avec détection dynamique de colonnes.

2. **Étape 2 — Validation du Service de Surveillance (`watch_and_sync.py`)** :
   Tester la détection automatique dans `%TEMP%`, la génération DDL et la résilience face à la fermeture/réouverture d'Infrastructure Administrator.

3. **Étape 3 — Raccordement temps réel dans AutoCAD Map 3D** :
   Établir la connexion FDO natif PostgreSQL dans Map 3D (`_MAPCONNECT`), charger les couches et valider l'édition temps réel.

4. **Étape 4 — Transition vers la Phase 6** :
   Développement de l'interface graphique (GUI Admin) et packaging sous forme de Service Windows d'arrière-plan.
