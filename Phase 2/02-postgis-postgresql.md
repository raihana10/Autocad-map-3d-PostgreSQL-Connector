# 02 — PostgreSQL / PostGIS

> Phase 2 du plan de travail. Le volet Autodesk (Infrastructure Administrator, choix du modèle d'Industry Model, menu Enterprise) est déjà couvert dans le livrable **`01-autodesk-architecture.md`** et n'est pas répété ici.
>
> Légende : **[FAIT]** = réalisé et capturé · **[À FAIRE]** = prévu mais pas encore fait.

## 1. Installation et vérification

Base de test `map3d_test` créée sous PostgreSQL 18, extension PostGIS installée dessus.

<img src="./Screenshot 2026-07-10 135323.png" alt="Création de la base map3d_test" />
*Création de la base `map3d_test`.*

```sql
CREATE EXTENSION postgis;
```

<img src="./Screenshot 2026-07-10 135519.png" alt="Extension PostGIS installée" />

```sql
SELECT PostGIS_Version();
```

<img src="./Screenshot 2026-07-10 135533.png" alt="Résultat de PostGIS_Version" />
*Résultat : PostGIS 3.6, GEOS/PROJ actifs.*

**[FAIT]** : environnement PostgreSQL/PostGIS opérationnel.

## 2. Schéma dédié

Un schéma `fibre` a été créé pour isoler les tables du projet (cas d'usage réseau fibre optique / FTTx).

```sql
CREATE SCHEMA fibre;
```

<img src="./Screenshot 2026-07-10 135803.png" alt="Création du schéma fibre" />

Vérification :

```sql
SELECT schema_name FROM information_schema.schemata;
```

<img src="./Screenshot 2026-07-10 135838.png" alt="Liste des schémas" />

*Les schémas `public` et `fibre` sont bien présents.*

## 3. Script SQL de démonstration

Script autonome fourni à part : **[`demo_schema_fibre.sql`](demo_schema_fibre.sql)**.

Il crée, dans le schéma `fibre`, quatre tables spatiales (`chambre` en POINT, `poteau` en POINT, `cable` en LINESTRING avec clés étrangères vers `chambre`, `zone_desserte` en POLYGON), avec index GiST et quelques requêtes de test (longueur d'un câble, inclusion spatiale).

Objectif : pratiquer manuellement la modélisation spatiale (types de géométrie, PK/FK, index) avant de chercher, en Phase 3, à la générer automatiquement à partir d'un Data Model Autodesk.

## 4. Connecteur FDO PostgreSQL natif de Map 3D

**[FAIT]** — le connecteur natif « Bring in features from PostgreSQL/PostGIS » de Map 3D a été testé avec succès : connexion à la base `map3d_test`, affichage et édition des objets du schéma `fibre` confirmés fonctionnels en lecture et en écriture bidirectionnelle.

### 4.1 Connexion à la base

Connexion établie via **Data Connect → Add PostgreSQL Connection**, avec authentification sur la base `map3d_test` (service `localhost:5432`, utilisateur `postgres`).

<img src="./Screenshot 2026-07-13 150450.png" alt="Connexion PostgreSQL via Map 3D" />
*Fenêtre de connexion PostgreSQL — saisie des identifiants pour la base `map3d_test`.*

Sélection du datastore `map3d_test` dans la liste des bases disponibles sur l'instance.

<img src="./Screenshot 2026-07-13 150502.png" alt="Sélection du datastore PostgreSQL" />
*Choix du data store parmi les bases détectées (`map3d_test`, `postgis_36_sample`, `postgres`).*

### 4.2 Ajout des couches au dessin

Une fois connecté, l'arborescence du schéma `fibre` apparaît avec les tables spatiales créées en section 3 (`cable`, `chambre`, `commune`, `conduit`, `zone`), chacune reconnue avec son système de coordonnées (LL84).

<img src="./Screenshot 2026-07-13 150525.png" alt="Ajout des couches au dessin" />
*Panneau « Add Data to Map » — sélection des couches du schéma `fibre` à ajouter au dessin.*

La table `chambre` a été ajoutée au dessin (`Add to Map`), les deux enregistrements existants s'affichent correctement avec leurs attributs (`id`, `nom`, `type`) dans la table de données associée.

<img src="./Screenshot 2026-07-13 162158.png" alt="Affichage de chambre dans le dessin" />
*Objet `chambre` affiché dans le dessin, table de données Map 3D synchronisée (CH-001, CH-002).*

### 4.3 Test de modification (édition bidirectionnelle)

Le nom de l'enregistrement `id=2` a été modifié dans Map 3D (`CH-002` → confirmé, `CH-01` renommé côté source).

Vérification directe dans pgAdmin, requête `SELECT * FROM fibre.chambre;` : les modifications faites depuis Map 3D sont bien répercutées dans PostgreSQL, avec la géométrie (`geom`) intacte.

<img src="./Screenshot 2026-07-13 162636.png" alt="Vérification en base via pgAdmin" />
*Vérification en base via pgAdmin — les attributs modifiés dans Map 3D sont bien persistés dans `fibre.chambre`.*

Sélection de l'objet `CH-002` dans le dessin, confirmant la correspondance visuelle avec l'enregistrement en base.

<img src="./Screenshot 2026-07-13 162654.png" alt="Sélection de l’objet modifié" />
*Sélection de l'objet `CH-002` dans le dessin — correspondance confirmée avec la base.*

### 4.4 Constat

Le connecteur FDO natif fonctionne bien pour l'affichage et l'édition CRUD basique (lecture, modification, synchro immédiate avec PostgreSQL, sans étape de commit explicite visible).

**Reste à tester** pour trancher complètement la question ouverte (classes métier / règles) :
- Comportement face à une contrainte CHECK ou une clé étrangère violée
- Gestion des domaines de valeurs / listes déroulantes
- Représentation de relations ou d'héritage entre classes

## 5. Synthèse

| Prévu | Statut |
|---|---|
| Installer PostgreSQL + PostGIS | **[FAIT]** |
| Créer une base/schéma de test avec tables `geometry` | **[FAIT]** |
| Pratiquer POINT / LINESTRING / POLYGON | **[FAIT]** (MULTIPOLYGON non testé) |
| Schémas, PK/FK, index GiST | **[FAIT]** (vues non testées) |
| Tester le connecteur FDO PostgreSQL de Map 3D (affichage/édition) | **[FAIT]** |
## 6. Conclusion technique de la Phase 2

Cette phase avait pour objectif de déterminer si Autodesk AutoCAD Map 3D pouvait communiquer directement avec une base PostgreSQL/PostGIS sans utiliser le connecteur commercial TKI PGP.

Les essais réalisés montrent que cette connexion est effectivement possible grâce au fournisseur **OSGeo FDO Provider for PostgreSQL/PostGIS** intégré à AutoCAD Map 3D.

Les fonctionnalités suivantes ont été validées :

- connexion à une base PostgreSQL/PostGIS ;
- affichage des tables spatiales comme couches cartographiques ;
- lecture des géométries (POINT, LINESTRING, POLYGON) ;
- modification des attributs ;
- synchronisation immédiate des modifications avec PostgreSQL ;
- utilisation des tables spatiales sans conversion intermédiaire.

Ces résultats démontrent qu'AutoCAD Map 3D sait déjà travailler nativement avec PostgreSQL/PostGIS pour des données SIG classiques.

## Ce que fait réellement le connecteur FDO

Le fournisseur FDO joue uniquement le rôle de connecteur entre AutoCAD Map 3D et la base de données.

Son rôle consiste à :

- ouvrir une connexion vers PostgreSQL ;
- lire les tables contenant des géométries ;
- afficher ces objets dans le dessin ;
- permettre leur création, leur modification et leur suppression ;
- enregistrer automatiquement les modifications dans PostgreSQL.

Dans cette configuration, chaque table PostgreSQL est simplement interprétée comme une couche cartographique.

Par exemple :

```
Table PostgreSQL
----------------
fibre.chambre
```

est affichée dans AutoCAD Map 3D comme une couche contenant des objets de type POINT.

Le fournisseur FDO ne possède cependant aucune connaissance du métier représenté par ces objets.

Pour lui, la table `chambre` est simplement une table SQL possédant quelques attributs et une colonne `geometry`.

## Ce que FDO ne fournit pas

Les essais montrent également que le connecteur FDO ne transforme pas automatiquement une base PostgreSQL en véritable Industry Model.

Il ne fournit notamment pas :

- les classes métier d'une Fachschale ;
- les règles métier ;
- les formulaires spécialisés ;
- les relations métier entre les objets ;
- les métadonnées propres aux Industry Models Autodesk ;
- les comportements spécifiques utilisés dans Infrastructure Administrator.

Autrement dit, FDO permet uniquement l'accès aux données géographiques.

Il ne fournit pas la couche métier qui caractérise une Fachschale.

## Place de TKI PGP

À partir des expérimentations réalisées, il apparaît que TKI PGP ne sert pas uniquement à connecter PostgreSQL à AutoCAD Map 3D.

Cette connexion existe déjà grâce au fournisseur FDO.

La valeur ajoutée de TKI PGP se situe à un niveau supérieur.

Son rôle est de permettre l'utilisation d'un **Industry Model Autodesk** sur PostgreSQL en apportant les éléments qui dépassent la simple lecture des tables spatiales.

Sans disposer de sa documentation interne complète, on peut raisonnablement conclure que TKI PGP assure notamment la prise en charge des métadonnées nécessaires aux Industry Models et leur intégration avec PostgreSQL.

Cette hypothèse sera vérifiée lors de la Phase 3.

## Différence entre FDO et un Industry Model

```
                 FDO PostgreSQL
                 --------------

PostgreSQL
      │
      ▼
Lecture des tables
      │
      ▼
Affichage des couches
      │
      ▼
Modification des objets
      │
      ▼
Sauvegarde dans PostgreSQL


==============================


             Industry Model (Fachschale)

Définition du métier
      │
      ▼
Classes métier
      │
      ▼
Relations entre objets
      │
      ▼
Règles métier
      │
      ▼
Formulaires spécialisés
      │
      ▼
Data Model
      │
      ▼
PostgreSQL
      │
      ▼
AutoCAD Map 3D
```

## Conclusion

Les expérimentations réalisées durant cette phase permettent de conclure que PostgreSQL/PostGIS est parfaitement compatible avec AutoCAD Map 3D pour le stockage et l'édition de données spatiales grâce au fournisseur FDO natif.

En revanche, ces essais montrent également qu'une simple connexion FDO ne suffit pas à reproduire le comportement complet d'une Fachschale Autodesk.

La prochaine étape du projet consistera donc à comprendre comment un **Industry Model** est défini, comment il est transformé en **Data Model**, quelles métadonnées Autodesk génère, et quelles fonctionnalités supplémentaires TKI PGP apporte afin de permettre le fonctionnement complet d'une Fachschale sur PostgreSQL.

Cette analyse constituera le point de départ de la Phase 3 du projet.


## Annexe — captures fournies

- `Screenshot_2026-07-10_135323.png` — création de la base `map3d_test`
- `Screenshot_2026-07-10_135519.png` — `CREATE EXTENSION postgis;`
- `Screenshot_2026-07-10_135533.png` — `SELECT PostGIS_Version();`
- `Screenshot_2026-07-10_135803.png` — `CREATE SCHEMA fibre;`
- `Screenshot_2026-07-10_135838.png` — liste des schémas de `map3d_test`
- `Screenshot_2026-07-13_150450.png` — connexion PostgreSQL via Data Connect
- `Screenshot_2026-07-13_150502.png` — sélection du data store `map3d_test`
- `Screenshot_2026-07-13_150525.png` — ajout des couches du schéma `fibre` au dessin
- `Screenshot_2026-07-13_162158.png` — affichage de `chambre` dans le dessin
- `Screenshot_2026-07-13_162636.png` — vérification pgAdmin après modification
- `Screenshot_2026-07-13_162654.png` — sélection de l'objet modifié dans le dessin