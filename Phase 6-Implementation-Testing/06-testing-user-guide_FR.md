# 📘 Guide de Test & Feuille de Route A à Z (Version Française)
**Projet :** AutoCAD Map 3D - Connecteur PostgreSQL / PostGIS  
**Phase :** Phase 6 — Implémentation & Tests de Synchronisation Multi-Modèles  
**Destinataire :** Encadrante de Projet  

---

##  Objectif du Guide

Ce document constitue un **guide de test complet de A à Z** permettant d'exécuter et de vérifier l'ensemble du connecteur automatique entre **Autodesk Infrastructure Administrator / AutoCAD Map 3D** et **PostgreSQL / PostGIS**.

> **Note Importante :** Le script principal `watch_and_sync.py` est le service maître d'automation. Il appelle **automatiquement** le script `convert_autodesk_to_postgis.py` en arrière-plan. L'exécution d'une seule commande `watch_and_sync.py` suffit pour tester l'intégralité du pipeline (conversion DDL, création de base de données, synchronisation des structures, suppressions physiques et synchronisation des données).

---

##  1. Prérequis & Installation de l'Environnement

### 1.1 Composants Logiciels Requis
- **Python :** Version 3.9 ou supérieure.
- **PostgreSQL / PostGIS :** PostgreSQL 13+ avec l'extension PostGIS installée.
- **Autodesk Infrastructure Administrator / AutoCAD Map 3D :** (ou tout fichier SQLite de Modèle d'Industrie Autodesk `.sqlite`).

### 1.2 Installation des Dépendances Python
Ouvrez une invite de commande (`cmd` ou `PowerShell`) dans le répertoire `Phase 6-Implementation-Testing` et exécutez :

```powershell
pip install -r requirements-dev.txt
```

---

##  2. Feuille de Route de Test de A à Z (Roadmap Simplifiée)

```
[Étape 1] Ouverture/Création du Modèle dans Autodesk Infrastructure Administrator
   │
   ▼
[Étape 2] Lancement du Service Maître (watch_and_sync.py)
   │ ├── Détection automatique du SQLite dans %TEMP% / Embedded
   │ ├── Appel automatique de convert_autodesk_to_postgis.py
   │ ├── Création automatique de la base PostgreSQL & Extension PostGIS
   │ └── Application des Tables, Clés Étrangères, Index GiST & Triggers
   ▼
[Étape 3] Test des Modifications Dynamiques (Ajout de classes & d'attributs)
   │
   ▼
[Étape 4] Test de la Suppression Physique (DROP TABLE CASCADE & DROP COLUMN)
   │
   ▼
[Étape 5] Connexion FDO Native & Visualisation dans AutoCAD Map 3D
```

---

##  Étape 1 : Préparation du Modèle d'Industrie Autodesk

1. Ouvrez **Autodesk Infrastructure Administrator**.
2. Créez ou ouvrez un Modèle d'Industrie SQLite.
3. Lors de l'ouverture du modèle, Autodesk génère un fichier SQLite temporaire actif situé par défaut dans le répertoire système `%TEMP%` (Exemple : `C:\Users\PC\AppData\Local\Temp\Embedded`).

---

##  Étape 2 : Lancement de la Synchronisation Globale (`watch_and_sync.py`)

Cette **unique commande** exécute la conversion DDL, crée la base de données PostgreSQL, configure PostGIS, applique les structures, gère les ajouts/modifications/suppressions et synchronise les données.

### Commande à exécuter :
```powershell
python "C:\Path\To\Your_script_watch_and_sync_depending_on_ur_actual_path_to_the_script.py(Phase 6-Implementation-Testing\scripts\watch_and_sync.py)" --pg-user NOM_UTILISATEUR --pg-pass VOTRE_MOT_DE_PASSE --initial-sync
```

### Options de commande :
- `--initial-sync` : Exécute une synchronisation initiale immédiate dès le démarrage.
- `--srid` : Définir le système de coordonnées PostGIS (par défaut `2154` - Lambert-93).
- `--dir` : (Optionnel) Spécifier un dossier de recherche personnalisé si le fichier SQLite n'est pas dans `%TEMP%`.

### Résultat attendu dans la console :
1. Détection automatique du modèle d'industrie Autodesk.
2. Appel transparent de `convert_autodesk_to_postgis.py`.
3. Création automatique de la base de données PostgreSQL.
4. Activation automatique de l'extension PostGIS (`CREATE EXTENSION IF NOT EXISTS postgis`).
5. Application du schéma SQL et démarrage du mode de surveillance **Watchdog**.

---

## 🚀 Étape 3 : Test des Modifications Dynamiques

Pendant que le script `watch_and_sync.py` tourne en arrière-plan dans la console :

### Test A : Ajout d'une nouvelle Classe (Table Feature/Geo)
1. Dans **Autodesk Infrastructure Administrator**, ajoutez une nouvelle classe (ex: `VANNE` ou `BATIMENT`).
2. Enregistrez le Modèle d'Industrie.
3. **Observation :** Dans la console Python, `watch_and_sync.py` détecte immédiatement la modification, compile le schéma et crée la nouvelle table dans PostgreSQL avec ses index spatiaux.

### Test B : Ajout d'un nouvel attribut (Colonne)
1. Dans Infrastructure Administrator, ajoutez un nouvel attribut à une classe existante.
2. Enregistrez.
3. **Observation :** Le service exécute automatiquement `ALTER TABLE "table" ADD COLUMN "nom_colonne" Type`.

> 💡 **Note sur le renommage des classes (Nom SQL vs Libellé/Caption) :**  
> Dans Autodesk Infrastructure Administrator, modifier le titre d'une classe dans l'arborescence met à jour la propriété `CAPTION` (libellé d'affichage pour l'utilisateur) mais **conserve le nom physique de la table SQL** (`NAME`). Le connecteur PostgreSQL utilise le nom de table SQL physique pour créer la table (`CREATE TABLE "NOM_PHYSIQUE"`) tout en consignant le libellé d'affichage dans les commentaires du DDL.

---

## 🚀 Étape 4 : Test de Suppression Physique (Physical Deletion)

Lorsque vous supprimez un élément dans le Data Model d'Autodesk (après confirmation dans l'interface d'Infrastructure Administrator) :

1. Dans **Autodesk Infrastructure Administrator**, supprimez un attribut ou une classe d'objets entière.
2. Confirmez la suppression dans la boîte de dialogue d'Autodesk.
3. Enregistrez.
4. **Observation dans PostgreSQL :**
   - La table est immédiatement supprimée via `DROP TABLE "table" CASCADE`.
   - La colonne est immédiatement supprimée via `ALTER TABLE "table" DROP COLUMN IF EXISTS "colonne"`.
   - Un rapport d'audit au format JSON nommé `schema_diff_YYYYMMDD_HHMMSS.json` est automatiquement généré à la racine du projet.

---

## 🚀 Étape 5 : Connexion FDO Native dans AutoCAD Map 3D

Pour consommer et visualiser les données synchronisées directement dans AutoCAD Map 3D :

1. Dans AutoCAD Map 3D, ouvrez la palette **Volet Tâches** (`MAPWSPACE` -> Activé).
2. Cliquez sur **Données** -> **Connexion aux données** (FDO).
3. Sélectionnez le fournisseur **Ajouter la connexion PostgreSQL / PostGIS**.
4. Saisissez les paramètres de connexion PostgreSQL(nom de la base de données est le même que celui du industry model).
5. Cliquez sur **Connecter** et **Ajouter à la carte**.

---

## 📊 Fichiers du Projet

| Fichier | Rôle |
| :--- | :--- |
| `scripts/watch_and_sync.py` | **Script Maître :** Service de surveillance temps réel, création de DB, synchronisation & suppression physique |
| `scripts/convert_autodesk_to_postgis.py` | Moteur de conversion DDL (appelé automatiquement par `watch_and_sync.py`) |
| `requirements-dev.txt` | Liste des dépendances Python requises |
| `06-testing-user-guide_EN.md` | Guide de test complet en Anglais |
