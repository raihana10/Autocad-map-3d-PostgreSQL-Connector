# README — Alternative libre à TKI PGP pour l'utilisation de PostgreSQL/PostGIS avec AutoCAD Map 3D

> Document de spécification technique rédigé pour servir de guide pendant toute la durée du stage.
> Légende utilisée dans tout le document :
> - **[DOCUMENTÉ]** = information confirmée par une source officielle Autodesk ou TKI, ou par la documentation produit.
> - **[HYPOTHÈSE]** = déduction raisonnable, non confirmée par une source officielle, à valider par l'expérimentation.
> - **[À VÉRIFIER]** = information manquante, non documentée publiquement, ou nécessitant un test/une confirmation auprès de l'encadrante ou du support Autodesk.

---

## 0. Résumé exécutif

Autodesk **Infrastructure Administrator** (module livré avec AutoCAD Map 3D) permet de créer des **Industry Models** (en allemand *Fachschale*) — des schémas de données métier pour la gestion d'infrastructures (réseaux électriques, eau, gaz, télécom, etc.). Officiellement, un Industry Model « base de données » (par opposition à un Industry Model « fichier ») ne peut être créé que sur **Oracle** ou **Microsoft SQL Server** **[DOCUMENTÉ]**. PostgreSQL/PostGIS n'est **pas** une option native proposée par Infrastructure Administrator **[DOCUMENTÉ]**.

La société allemande **TKI** (TKI Chemnitz / TKI Software, éditrice des solutions **TKI NET** et **TKI PGP**) commercialise un connecteur, le **PostgreSQL Provider (PGP)**, décrit comme *« the effective connector between Autodesk AutoCAD Map3D standard industry models and PostgreSQL »* **[DOCUMENTÉ]**. Ce connecteur permet d'utiliser un Industry Model avec une base PostgreSQL/PostGIS au lieu d'Oracle ou SQL Server, avec une intégration dans Infrastructure Administrator et la prise en charge des imports/exports (dumps PostgreSQL) et de la feuille SQL **[DOCUMENTÉ]**.

Le sujet du stage consiste à **comprendre et reproduire, sans code commercial**, l'essentiel de ce que fait TKI PGP : permettre à Infrastructure Administrator et à AutoCAD Map 3D de considérer une base PostgreSQL/PostGIS comme le stockage d'un Industry Model, avec un niveau de fonctionnalité équivalent (création du schéma, lecture, création, modification, suppression d'objets, synchronisation).

---

## 1. Présentation du projet

### 1.1 Contexte du stage

Le stage est réalisé par deux étudiantes en génie informatique, en binôme, sur la base d'un sujet fourni par une encadrante. L'environnement logiciel de référence est la suite Autodesk orientée infrastructure :

- **AutoCAD Map 3D** : logiciel SIG/CAO d'Autodesk, extension d'AutoCAD orientée données géospatiales.
- **Autodesk Infrastructure Administrator** : module d'administration livré avec AutoCAD Map 3D, permettant de créer et gérer des Industry Models (Fachschalen), des utilisateurs, des formulaires, des règles métier, etc. **[DOCUMENTÉ]**

### 1.2 Le problème à résoudre

Autodesk ne propose **nativement** que deux moteurs de base de données pour les Industry Models « base de données » (« database-based industry model ») : **Oracle** et **Microsoft SQL Server**. Un troisième mode existe, dit « fichier » (« file-based »), qui stocke les données dans un fichier **SQLite embarqué dans un DWG** **[DOCUMENTÉ, source : documentation Autodesk Infrastructure Map Server 2016]**.

PostgreSQL, bien que largement utilisé et gratuit (contrairement à Oracle/SQL Server, souvent payants en environnement professionnel), n'apparaît dans aucune de ces options officielles. Ceci est confirmé par un fil de discussion du forum développeur Autodesk (2014), où un utilisateur demande explicitement s'il est possible d'étendre l'Enterprise Industry Model à PostgreSQL/PostGIS ; la réponse d'un « Autodesk Expert Elite » est sans ambiguïté : *« Industry Models (on AutoCAD MAP 2015) are only supported with Oracle, SQLite and MS SQL-Server »* **[DOCUMENTÉ]**.

### 1.3 Pourquoi TKI PGP est normalement utilisé

Pour combler ce manque, TKI a développé **PGP (PostgreSQL Provider)**, un connecteur/fournisseur logiciel commercial qui :

- s'intègre à Infrastructure Administrator pour en reprendre les fonctionnalités (« *PGP supports the functionality of the Infrastructure Administrator* ») **[DOCUMENTÉ]** ;
- permet d'utiliser une base PostgreSQL (avec l'extension spatiale libre **PostGIS**) comme moteur de stockage d'un Industry Model **[DOCUMENTÉ]** ;
- fournit des fonctions d'import/export de dumps PostgreSQL et un support de la feuille SQL (SQL sheet) d'AutoCAD Map 3D **[DOCUMENTÉ]**.

L'intérêt principal mis en avant par TKI est économique : éviter les coûts de licence et d'administration d'Oracle/SQL Server en s'appuyant sur PostgreSQL, logiciel libre, couplé à PostGIS, extension spatiale également libre **[DOCUMENTÉ]**.

Remarque terminologique : TKI PGP (« PostgreSQL Provider ») est un produit **distinct** de TKI NET. **TKI NET** est une solution métier complète de gestion de réseaux FTTx/télécoms construite au-dessus d'AutoCAD Map 3D **[DOCUMENTÉ, aperçu général]**, alors que **TKI PGP** est la brique technique bas niveau qui permet à un Industry Model quelconque (pas seulement celui de TKI NET) de fonctionner avec PostgreSQL. Le sujet de stage précise explicitement de **ne pas prendre en compte TKI NET** ; nous nous concentrons donc uniquement sur l'équivalent fonctionnel de **TKI PGP**.

### 1.4 Pourquoi nous devons développer une solution alternative

TKI PGP est un produit commercial sous licence (l'installation nécessite une activation de licence sur un serveur de licences réseau) **[DOCUMENTÉ]**. Le stage vise à explorer une voie **non commerciale / open-source**, développée en interne, pour obtenir une intégration PostgreSQL/PostGIS équivalente, sans dépendre de ce connecteur payant.

### 1.5 Objectif final du projet

Concevoir et implémenter une solution logicielle permettant :

1. de créer un Industry Model (Fachschale) via Infrastructure Administrator ;
2. de faire correspondre ce modèle de données à un schéma PostgreSQL/PostGIS (création automatique des tables spatiales, contraintes, relations) ;
3. de permettre à AutoCAD Map 3D de lire, créer, modifier et supprimer les objets de cet Industry Model directement dans PostgreSQL, avec une expérience utilisateur équivalente à celle obtenue avec TKI PGP.

---

## 2. Architecture générale

### 2.1 Rôle de chaque composant

| Composant | Rôle | Statut |
|---|---|---|
| **Infrastructure Administrator** | Outil de conception/administration : créer et modifier un Industry Model, gérer utilisateurs/groupes, formulaires, règles métier, projets. **[DOCUMENTÉ]** | Officiel Autodesk |
| **Industry Model (Fachschale)** | Le modèle de données métier complet : classes d'objets, attributs, géométries, règles, formulaires — instancié soit en base (Oracle/SQL Server) soit en fichier (SQLite/DWG). **[DOCUMENTÉ]** | Officiel Autodesk |
| **Data Model** | La définition structurelle (schéma) des classes d'objets et attributs d'un Industry Model, éditable via le « Data Model Administrator », un des outils internes d'Infrastructure Administrator. **[DOCUMENTÉ, existence de l'outil confirmée]** ; format de stockage exact **[À VÉRIFIER]** | Officiel Autodesk |
| **PostgreSQL** | Système de gestion de base de données relationnelle open source, cible de substitution à Oracle/SQL Server. | Standard ouvert |
| **PostGIS** | Extension spatiale de PostgreSQL, apportant les types géométriques (`geometry`, `geography`), fonctions spatiales et index spatiaux (GiST). | Standard ouvert |
| **AutoCAD Map 3D** | Client CAO/SIG utilisé pour visualiser, créer, éditer les objets d'un Industry Model connecté à sa base. **[DOCUMENTÉ]** | Officiel Autodesk |
| **TKI PGP** | Connecteur commercial tiers reliant Infrastructure Administrator / AutoCAD Map 3D à PostgreSQL/PostGIS, en lieu et place d'Oracle/SQL Server. **[DOCUMENTÉ]** | Commercial (TKI) |

### 2.2 Schéma — Architecture officielle Autodesk (Oracle / SQL Server)

```
 ┌───────────────────────────┐
 │  Infrastructure            │
 │  Administrator             │   (conception / administration du modèle)
 └──────────────┬──────────────┘
                │  crée / met à jour
                ▼
 ┌───────────────────────────┐
 │      Data Model             │   (schéma : classes d'objets, attributs)
 └──────────────┬──────────────┘
                │  matérialisé dans
                ▼
 ┌───────────────────────────┐
 │   Industry Model             │
 │  (Fachschale)                 │
 └──────────────┬──────────────┘
                │  stocké dans
      ┌─────────┴─────────┐
      ▼                   ▼
 ┌──────────┐        ┌──────────────┐
 │ Oracle    │        │ SQL Server    │
 │ (DB-based)│        │ (DB-based)    │
 └──────────┘        └──────────────┘
                │
                │  ou bien, mode fichier :
                ▼
        ┌─────────────────────┐
        │ SQLite dans un DWG   │
        │ (file-based)         │
        └─────────────────────┘

 ┌───────────────────────────┐
 │  AutoCAD Map 3D             │  <── lit/écrit via le driver Oracle/SQL Server natif
 └───────────────────────────┘
```

### 2.3 Schéma — Architecture avec TKI PGP (référence commerciale)

```
 ┌───────────────────────────┐
 │  Infrastructure             │
 │  Administrator                │
 └──────────────┬──────────────┘
                │  fonctionnalités reprises/étendues par
                ▼
 ┌───────────────────────────┐
 │        TKI PGP                │  <── connecteur (driver + intégration IA)
 │  (PostgreSQL Provider)        │
 └──────────────┬──────────────┘
                │  traduit / expose le Data Model vers
                ▼
 ┌───────────────────────────┐
 │   PostgreSQL + PostGIS         │
 │   (tables spatiales, schéma)   │
 └──────────────┬──────────────┘
                ▲
                │  lecture/écriture via TKI PGP
 ┌───────────────────────────┐
 │  AutoCAD Map 3D                │
 └───────────────────────────┘
```

Le mécanisme interne exact de traduction (quel composant génère les tables SQL, quel driver est utilisé au niveau AutoCAD — FDO, ODBC, ADO.NET) n'est **pas documenté publiquement** **[À VÉRIFIER]**. C'est précisément l'objet de la Phase 4 (section 5).

### 2.4 Schéma — Architecture cible du projet (solution alternative, à concevoir)

```
 ┌───────────────────────────┐
 │  Infrastructure Administrator │
 │  (création de la Fachschale,  │
 │   Data Model, formulaires)    │
 └──────────────┬──────────────┘
                │
                ▼
 ┌───────────────────────────┐
 │   Data Model exporté /        │
 │   extrait (format à            │
 │   déterminer : XML / SQLite /  │
 │   autre)                       │
 └──────────────┬──────────────┘
                │  [COMPOSANT À DÉVELOPPER]
                │  traduction Data Model → schéma SQL
                ▼
 ┌───────────────────────────┐
 │   Générateur de schéma          │
 │   PostgreSQL/PostGIS            │
 │   (scripts SQL, DDL)            │
 └──────────────┬──────────────┘
                ▼
 ┌───────────────────────────┐
 │   PostgreSQL + PostGIS           │
 └──────────────┬──────────────┘
                │  [COMPOSANT À DÉVELOPPER]
                │  couche d'accès / driver / passerelle
                ▼
 ┌───────────────────────────┐
 │  AutoCAD Map 3D                  │
 └───────────────────────────┘
```

Les deux blocs « [COMPOSANT À DÉVELOPPER] » représentent le cœur du travail de conception (Phase 5) puis de développement (Phase 6). Aucun code n'est encore écrit à ce stade — ce README a pour but de préparer cette conception.

---

## 3. Explication détaillée des concepts

Cette section vulgarise chaque notion avec un exemple concret. Les définitions générales (PostgreSQL, PostGIS, SQL) sont des faits techniques standards **[DOCUMENTÉ]**. Les définitions liées au vocabulaire Autodesk sont **[DOCUMENTÉ]** quand une source officielle a été trouvée, sinon signalées.

### 3.1 Fachschale (= Industry Model)

« Fachschale » est le terme allemand utilisé dans l'interface et la documentation germanophone d'Autodesk pour désigner un **Industry Model** **[DOCUMENTÉ]**. C'est un modèle de données métier complet et autonome : classes d'objets (ex. « Poteau électrique », « Vanne », « Câble »), attributs, géométries, règles, formulaires, workflows, adapté à un secteur (eau, gaz, électricité, télécoms...) **[DOCUMENTÉ]**.

Exemple concret : une Fachschale « Électricité » contient des classes comme `Transformateur`, `LigneHauteTension`, `Poteau`, chacune avec ses attributs (puissance, tension, matériau) et sa géométrie (point, ligne).

### 3.2 Industry Model — les deux modes de stockage

- **Database-based Industry Model** : stocké dans une vraie base de données serveur (Oracle ou SQL Server) **[DOCUMENTÉ]**. Adapté au travail multi-utilisateur (« Enterprise »).
- **File-based Industry Model** : stocké dans une base **SQLite** intégrée à un fichier **DWG** **[DOCUMENTÉ]**. Adapté à un usage local/mono-utilisateur.

### 3.3 Data Model

Le **Data Model** est la définition structurelle (le schéma) d'un Industry Model : la liste des classes d'objets, leurs attributs, leurs types, leurs relations, leurs domaines de valeurs. Il est créé et modifié via l'outil **Data Model Administrator**, l'un des modules internes d'Infrastructure Administrator, qui permet de : créer/éditer des classes d'objets, ajouter des attributs, activer la gestion de tâches (« Job-enable »), gérer des tables de domaines, gérer des labels, créer des topologies, définir des règles d'objets **[DOCUMENTÉ]**.

Un Data Model peut être créé et **enregistré sous forme de fichier SQLite**, qui peut ensuite être chargé dans un modèle de Fachschale (« Fachschalenvorlage ») **[DOCUMENTÉ, source : aide AutoCAD Map 3D 2025 sur la création de modèles de Fachschale]**. Ceci est une information importante et directement exploitable : cela confirme que le Data Model existe, à un stade intermédiaire, sous une forme portable de type SQLite. Le format exact de son contenu interne (nom des tables système, schéma des métadonnées) reste **[À VÉRIFIER]**.

### 3.4 Feature Class (classe d'objets)

Une « classe d'objets » regroupe des entités du même type, chacune ayant les mêmes attributs et le même type de géométrie. Exemple : la classe `Vanne` regroupe tous les objets « vanne » du réseau, chacun étant un point géoréférencé avec des attributs (diamètre, état, date d'installation).

### 3.5 Objet métier

Une instance concrète d'une classe d'objets : par exemple, « la vanne située à telle coordonnée, installée en 2019, de diamètre 100 mm » est un objet métier de la classe `Vanne`.

### 3.6 Attribut

Une propriété non géométrique d'un objet métier (nombre, texte, date, valeur d'une liste de domaine). Exemple : `diametre_mm = 100`.

### 3.7 Géométrie

La représentation spatiale d'un objet : point (`POINT`), ligne (`LINESTRING`), polygone (`POLYGON`), ou variantes multi- (`MULTIPOINT`, etc.). En PostGIS, ces géométries sont stockées dans une colonne de type `geometry` (ou `geography`), avec un système de référence spatiale (SRID) associé.

### 3.8 Métadonnées

Informations décrivant la structure elle-même plutôt que les données : nom des classes, types d'attributs, contraintes, relations, système de coordonnées du modèle. Dans une architecture PostgreSQL classique, on les retrouverait dans le catalogue système (`information_schema`, `pg_catalog`) et/ou dans des tables de métadonnées propres à l'application (c'est typiquement ce que ferait un connecteur comme TKI PGP ou notre future solution).

### 3.9 Schéma de base de données

L'organisation logique des tables, colonnes, contraintes et relations dans une base. En PostgreSQL, un « schema » est aussi un espace de noms (`CREATE SCHEMA ...`) permettant de regrouper des tables (par exemple, un schéma par Industry Model).

### 3.10 Table spatiale

Une table SQL contenant une colonne géométrique PostGIS. Exemple :

```sql
CREATE TABLE vanne (
    id SERIAL PRIMARY KEY,
    diametre_mm INTEGER,
    etat VARCHAR(20),
    geom GEOMETRY(POINT, 4326)
);
```

### 3.11 Relations entre objets

Deux objets métier peuvent être liés (ex. un `Poteau` porte plusieurs `Câbles`). Dans un Data Model Autodesk, ces relations sont définies explicitement dans le Data Model Administrator **[DOCUMENTÉ, l'outil gère des « relations » — le détail de leur implémentation SQL reste à vérifier]**. En base relationnelle, cela se traduit typiquement par une clé étrangère ou une table d'association, mais la correspondance exacte utilisée par Autodesk en interne (Oracle/SQL Server) n'est pas documentée publiquement **[À VÉRIFIER]**.

---

## 4. Workflow complet (architecture officielle Oracle/SQL Server)

| Étape | Logiciel | Entrée | Sortie | Résultat attendu |
|---|---|---|---|---|
| 1. Création du Data Model | Infrastructure Administrator → Data Model Administrator | Besoins métier (classes, attributs) | Data Model (éventuellement exporté en SQLite) **[DOCUMENTÉ pour l'export SQLite]** | Schéma structurel défini |
| 2. Création de la Fachschale | Infrastructure Administrator | Data Model, choix du module prédéfini, choix de la base (Oracle/SQL Server) | Industry Model instancié en base | Base de données prête à recevoir des objets |
| 3. Configuration des utilisateurs/projets | Infrastructure Administrator | Industry Model | Utilisateurs, groupes, projets, droits | Accès multi-utilisateur configuré **[DOCUMENTÉ]** |
| 4. Connexion depuis AutoCAD Map 3D | AutoCAD Map 3D | Identifiants de connexion à la Fachschale | Connexion active | Les classes d'objets sont visibles dans l'explorateur Map 3D |
| 5. Consultation des objets | AutoCAD Map 3D | Requête / navigation | Affichage cartographique des objets | Visualisation correcte des géométries et attributs |
| 6. Création/modification d'objets | AutoCAD Map 3D | Saisie utilisateur (dessin, formulaire) | Écriture en base | Objet inséré/modifié dans la Fachschale, avec règles métier appliquées |
| 7. Suppression d'objets | AutoCAD Map 3D | Sélection + suppression | Suppression en base | Cohérence relationnelle maintenue |
| 8. Synchronisation multi-utilisateur | AutoCAD Map 3D / Infrastructure Administrator | Modifications concurrentes | Résolution des conflits, verrouillage | Intégrité des données en environnement partagé **[À VÉRIFIER : mécanisme exact de verrouillage/versionning]** |

Ce même workflow, transposé à PostgreSQL, est assuré aujourd'hui par TKI PGP aux étapes 2 à 8 (remplacement d'Oracle/SQL Server par PostgreSQL comme moteur de stockage, et fourniture du mécanisme de connexion pour AutoCAD Map 3D). C'est cette substitution que le projet doit reproduire.

---

## 5. Analyse détaillée du plan de travail

### Phase 1 — Comprendre Autodesk

**Pourquoi c'est important** : sans une compréhension solide de l'écosystème Autodesk (Infrastructure Administrator, Industry Model, Data Model), toute tentative de conception d'une alternative à TKI PGP reposera sur des suppositions fragiles. C'est la fondation de tout le stage.

**Sous-étapes** :
1. Installer AutoCAD Map 3D + Infrastructure Administrator (version d'évaluation ou licence éducation).
2. Explorer l'interface d'Infrastructure Administrator : Data Model Administrator, Formulaire-Designer, Sécurité-Administrator, outils de migration.
3. Créer un Industry Model de test **en mode fichier (SQLite/DWG)**, qui ne nécessite ni Oracle ni SQL Server, afin d'observer concrètement la structure produite sans dépendance à un serveur de base de données lourd.
4. Créer un Data Model minimal (une ou deux classes d'objets simples) et l'exporter en SQLite pour l'examiner avec un outil comme DB Browser for SQLite.
5. Documenter, avec captures d'écran, chaque étape et chaque menu.

**Connaissances nécessaires** : notions de SIG, vocabulaire CAO (DWG, DWT), notions de base de données relationnelles.

**Méthodes de travail proposées** : tenir un journal de bord daté ; systématiquement noter, pour chaque manipulation, ce qui est observé factuellement (capture d'écran, fichier produit) versus ce qui est supposé.

**Livrable** : document `01-autodesk-architecture.md` décrivant l'architecture observée, complété par des captures d'écran et, si possible, un export du Data Model SQLite de test.

**Outils utiles** : AutoCAD Map 3D (version étudiante/trial), DB Browser for SQLite, un éditeur hexadécimal si besoin d'inspecter un format inconnu.

**Difficultés possibles** : accès à une licence AutoCAD Map 3D (les licences éducation Autodesk sont généralement gratuites pour les étudiants — **[À VÉRIFIER]** selon l'établissement) ; complexité de l'interface pour des débutantes.

**Conseils** : commencer impérativement par le mode fichier (SQLite) avant Oracle/SQL Server, car il ne nécessite pas d'installer un SGBD lourd et donne déjà accès à la structure interne d'un Data Model exporté.

---

### Phase 2 — Comprendre PostgreSQL/PostGIS

**Pourquoi c'est important** : PostgreSQL/PostGIS sera la cible technique du projet. Il faut maîtriser la modélisation spatiale relationnelle avant de pouvoir y transposer un Data Model Autodesk.

**Sous-étapes** :
1. Installer PostgreSQL + PostGIS localement (ou via Docker).
2. Créer une base de test, créer des tables avec colonnes `geometry`.
3. Pratiquer les types géométriques : `POINT`, `LINESTRING`, `POLYGON`, `MULTIPOLYGON`.
4. Étudier schémas (`CREATE SCHEMA`), clés primaires/étrangères, index (B-Tree et GiST spatial), vues.
5. Étudier comment AutoCAD Map 3D peut nativement lire/écrire du PostgreSQL/PostGIS **en dehors** de tout Industry Model, via le connecteur **FDO PostgreSQL** intégré à AutoCAD Map 3D (fonctionnalité « Bring in features from PostgreSQL/PostGIS », confirmée par la documentation Autodesk officielle) **[DOCUMENTÉ]**. C'est un point clé : AutoCAD Map 3D sait déjà parler à PostgreSQL au niveau « données SIG génériques » (FDO), mais **pas** au niveau « Industry Model » (Fachschale) sans TKI PGP. Bien distinguer ces deux niveaux d'intégration est essentiel pour la suite du projet.

**Connaissances nécessaires** : SQL, notions de SIG (systèmes de coordonnées, SRID), bases de PostGIS.

**Méthodes de travail proposées** : reproduire un mini-schéma « réseau électrique » à la main en PostgreSQL/PostGIS, puis l'ouvrir dans AutoCAD Map 3D via le connecteur FDO PostgreSQL pour vérifier concrètement ce que Map 3D sait déjà faire nativement.

**Livrable** : document `02-postgis-postgresql.md` + un script SQL de démonstration + captures d'écran de la connexion FDO PostgreSQL dans Map 3D.

**Outils utiles** : PostgreSQL, PostGIS, pgAdmin ou DBeaver, Docker (optionnel pour isoler l'environnement).

**Difficultés possibles** : configuration des SRID et des projections, compatibilité de version PostGIS/PostgreSQL.

**Conseils** : bien noter la différence entre « FDO PostgreSQL provider » (déjà natif Autodesk, simple lecture/écriture de couches SIG) et « Industry Model provider » (ce que fait TKI PGP, avec en plus toute la couche métier : classes, règles, formulaires, workflow).

---

### Phase 3 — Étudier le Data Model (phase la plus critique)

**Pourquoi c'est important** : c'est le nœud technique du projet. Toute solution alternative devra être capable de lire (et si possible écrire) la définition du Data Model pour la transformer en schéma PostgreSQL.

**Questions à traiter, avec l'état actuel des connaissances** :

- *Où est stocké le Data Model ?* → Pour un Industry Model **fichier**, il est intégré dans une base SQLite elle-même stockée dans le DWG **[DOCUMENTÉ]**. Pour un Industry Model **base de données**, il est stocké dans des tables système/de métadonnées à l'intérieur d'Oracle ou SQL Server **[HYPOTHÈSE raisonnable, cohérente avec l'architecture décrite, mais le détail du schéma de métadonnées Oracle/SQL Server n'est pas documenté publiquement — À VÉRIFIER]**.
- *Est-il en XML ?* → Aucune source consultée ne confirme un stockage central en XML. Il est possible que certains exports/imports (modèles de formulaires, configurations) utilisent du XML de façon ponctuelle, mais ce n'est pas confirmé pour le Data Model lui-même **[À VÉRIFIER]**.
- *Est-il dans une base SQLite ?* → **Oui, au moins pour les Data Models exportés/créés en vue d'une Fachschalenvorlage** (confirmé par la documentation officielle : *« Wenn Sie ein Datenmodell erstellt und als SQLite-Datei gespeichert haben, können Sie es für diese Fachschalenvorlage laden »*) **[DOCUMENTÉ]**. Pour un Industry Model de production sur Oracle/SQL Server, le Data Model est répliqué/matérialisé dans les tables systèmes de ce SGBD **[HYPOTHÈSE]**.
- *Est-il généré automatiquement ?* → La création d'une Fachschale à partir d'un Data Model et d'un module prédéfini semble déclencher une génération automatique des tables et objets correspondants **[HYPOTHÈSE forte, à confirmer par test pratique en Phase 1]**.
- *Peut-il être exporté ?* → Oui, au moins vers un fichier SQLite pour créer un modèle de Fachschale (« Fachschalenvorlage », extension `.DWT`) **[DOCUMENTÉ]**.
- *Comment Autodesk le lit-il ?* → Mécanisme interne non documenté publiquement **[À VÉRIFIER]**.
- *Peut-on le modifier ?* → Oui, via le Data Model Administrator (interface graphique) **[DOCUMENTÉ]**. Modification directe du fichier SQLite en dehors de l'outil : non recommandé, non documenté, risque de corruption **[À VÉRIFIER / à éviter sauf en environnement de test jetable]**.
- *Comment est-il transformé en structure exploitable (tables SQL) ?* → Mécanisme interne non documenté publiquement **[À VÉRIFIER]** — c'est précisément la transformation que notre solution alternative devra réaliser elle-même pour PostgreSQL.

**Sous-étapes recommandées** :
1. Créer plusieurs Data Models de test (fichier SQLite) avec des classes d'objets variées (attributs simples, géométries, relations, domaines de valeurs).
2. Ouvrir chaque fichier SQLite produit avec DB Browser for SQLite, cataloguer toutes les tables et colonnes trouvées.
3. Faire varier un seul paramètre à la fois (ajouter un attribut, ajouter une relation, changer un type de géométrie) et observer les différences dans le SQLite résultant, afin de déduire empiriquement la logique de correspondance Data Model → structure de stockage.
4. Consigner systématiquement les observations dans un tableau (paramètre modifié / effet observé).

**Livrable** : document `03-data-model-analyse.md`, incluant un ou plusieurs fichiers SQLite d'exemple et leur schéma documenté (dump `sqlite3 .schema`).

**Outils utiles** : DB Browser for SQLite, `sqlite3` CLI, diff de fichiers/schémas.

**Difficultés possibles** : les tables internes peuvent être peu lisibles (noms techniques, GUID) ; il peut être nécessaire de croiser avec la documentation Autodesk (Data Model Administrator help) pour interpréter certains champs.

**Conseils** : c'est la phase la plus longue et la plus déterminante — ne pas se précipiter vers le développement avant d'avoir un modèle mental clair et vérifié empiriquement de la structure du Data Model.

---

### Phase 4 — Comprendre le rôle exact de TKI PGP

**Pourquoi c'est important** : TKI PGP est la référence fonctionnelle du projet. Comprendre précisément son périmètre permet de définir un cahier des charges réaliste pour la solution alternative.

**Ce qui est confirmé (documenté)** :
- PGP est décrit comme le connecteur entre les Industry Models standards AutoCAD Map3D et PostgreSQL **[DOCUMENTÉ]**.
- PGP « reprend/supporte les fonctionnalités de l'Infrastructure Administrator » **[DOCUMENTÉ]** — cela suggère qu'il s'intègre profondément dans les mêmes flux de travail (création de Fachschale, gestion utilisateurs, etc.) plutôt que d'être un simple driver de connexion passif.
- PGP fournit des fonctions d'import/export de dumps PostgreSQL et prend en charge la feuille SQL (SQL sheet) de Map 3D **[DOCUMENTÉ]**.
- PGP nécessite une licence activée sur un serveur de licences réseau, et une compatibilité de version stricte avec la version d'AutoCAD Map 3D installée (une note de version TKI de 2025 déconseille par exemple explicitement l'usage de Map 3D 2025 avec NET/PGP tant que la version compatible n'est pas finalisée) **[DOCUMENTÉ]**.

**Ce qui reste à vérifier** :
- Est-ce que PGP **crée lui-même** les tables PostgreSQL à partir du Data Model, ou s'appuie-t-il sur un mécanisme Autodesk existant qu'il redirige vers PostgreSQL ? **[À VÉRIFIER]**
- Est-ce que PGP **convertit** un Data Model Oracle/SQL Server existant, ou bien fonctionne-t-il en parallèle, indépendamment, en générant sa propre structure PostgreSQL équivalente ? **[À VÉRIFIER]**
- Fournit-il un driver bas niveau (au sens FDO, ODBC ou ADO.NET) auquel AutoCAD Map 3D se connecte comme s'il s'agissait d'un fournisseur natif Oracle/SQL Server ? C'est l'hypothèse la plus probable techniquement (Autodesk documente une architecture de « providers » pour ses connexions base de données), mais elle n'est confirmée par aucune source publique consultée **[HYPOTHÈSE]**.
- Crée-t-il les métadonnées (classes, attributs, règles) dans des tables dédiées au sein même de PostgreSQL, en parallèle des tables de données ? **[HYPOTHÈSE probable, à vérifier]**
- Configure-t-il automatiquement AutoCAD Map 3D (profil de connexion, pilote) lors de l'installation ? **[À VÉRIFIER]**

**Sous-étapes recommandées** :
1. Rechercher et lire toute documentation publique disponible sur le portail d'aide TKI (`help.tki-chemnitz.de`), notamment la section « PostgreSQL provider » et « Working with AutoCAD Map 3D ».
2. Si un environnement de test avec licence d'évaluation PGP est accessible (à demander à l'encadrante), observer concrètement les tables créées dans PostgreSQL après création d'une Fachschale via PGP.
3. Comparer la structure SQL obtenue avec celle du Data Model SQLite analysé en Phase 3, pour objectiver la logique de correspondance.
4. Contacter, si possible et pertinent pour le stage, le support TKI ou consulter les forums Autodesk pour des retours d'utilisateurs.

**Livrable** : document `04-role-tki-pgp.md`, clairement structuré en trois colonnes : Documenté / Hypothèse / À vérifier, pour chaque fonction potentielle de PGP.

**Difficultés possibles** : absence probable d'accès à une licence PGP d'évaluation ; documentation TKI possiblement incomplète sur les mécanismes internes (produit commercial, logique interne non publiée pour des raisons de propriété intellectuelle).

**Conseils** : ne pas chercher à obtenir ou décompiler le code de TKI PGP (question de propriété intellectuelle et de licence) ; se concentrer sur une **ré-implémentation fonctionnelle indépendante**, à partir du comportement observable et de la documentation publique.

---

### Phase 5 — Concevoir une solution alternative

**Pourquoi c'est important** : c'est la phase de synthèse. Elle transforme la compréhension acquise en un choix d'architecture concret, justifié et réaliste pour un projet de fin d'études.

**Architectures possibles à comparer** :

| Approche | Description | Avantages | Inconvénients |
|---|---|---|---|
| **A. Génération de scripts SQL** | Un script (Python, par ex.) lit le Data Model exporté en SQLite et génère un script DDL PostgreSQL/PostGIS (CREATE TABLE, contraintes, index spatiaux). | Simple à mettre en œuvre, contrôle total, pas de dépendance à l'API Autodesk. | Statique : ne gère pas nativement la synchronisation temps réel avec AutoCAD Map 3D ; nécessite une couche supplémentaire pour la lecture/écriture depuis Map 3D. |
| **B. Conversion XML → PostgreSQL** | Suppose que le Data Model (ou une partie de sa configuration) soit exportable en XML, à convertir en schéma SQL. | Portable, lisible, facilement versionnable (Git). | Dépend de la confirmation, en Phase 3, qu'un export XML complet existe réellement **[À VÉRIFIER]** — risque de reposer sur une hypothèse fausse. |
| **C. Scripts Python (ETL / synchronisation)** | Couche Python assurant la synchronisation entre le Data Model et PostgreSQL, éventuellement avec une interface (CLI ou GUI) pour déclencher la génération et la synchronisation. | Rapide à prototyper, écosystème riche (psycopg2, GeoAlchemy2, SQLAlchemy), bonne adéquation avec un projet étudiant. | Ne résout pas seule le problème de la connexion **AutoCAD Map 3D ↔ PostgreSQL** en tant qu'Industry Model natif ; peut nécessiter de coupler avec le connecteur FDO PostgreSQL déjà natif à Map 3D (cf. Phase 2). |
| **D. Application dédiée en C# / .NET** | Utilise l'API .NET d'AutoCAD Map 3D (ObjectARX / AutoCAD .NET API, Autodesk Map 3D API) pour développer un plugin qui interface directement Map 3D avec PostgreSQL. | Intégration la plus proche de ce que fait probablement TKI PGP en interne (langage natif de l'écosystème Autodesk). | Complexité et courbe d'apprentissage élevées (API Autodesk, C#, ObjectARX) ; disponibilité de la documentation API à vérifier **[À VÉRIFIER]**. |
| **E. Application Java** | Équivalent à D mais en Java, si une API Java existe pour Map 3D/Infrastructure Administrator. | — | Existence et maturité d'une API Java pour Map 3D **[À VÉRIFIER — l'écosystème Autodesk Map 3D est historiquement plutôt orienté .NET/ObjectARX]**. |
| **F. Utilisation du connecteur FDO PostgreSQL natif + couche métier maison** | S'appuyer sur le fait qu'AutoCAD Map 3D sait déjà lire/écrire du PostgreSQL/PostGIS nativement via FDO (Phase 2), et construire par-dessus une couche applicative (scripts + schéma généré en Phase 5-A) qui simule le comportement « Industry Model » (règles, formulaires) au niveau applicatif plutôt qu'au niveau driver bas niveau. | Réutilise un mécanisme déjà officiellement supporté par Autodesk, réduit la partie « boîte noire » du projet. | Moins « fidèle » à un véritable Industry Model (pas de règles/formulaires nativement liés) ; à évaluer si le niveau de fonctionnalité est suffisant pour les objectifs du stage. |

**Recommandation méthodologique** : ne pas choisir prématurément. Réaliser un petit prototype (« spike ») pour au moins deux approches (par exemple A + F) avant de trancher, et documenter les résultats dans un tableau de décision.

**Sous-étapes** :
1. Lister les critères de décision (complexité, délai du stage, compétences déjà maîtrisées, robustesse attendue).
2. Réaliser un prototype minimal pour 1 ou 2 approches.
3. Comparer objectivement (tableau avantages/inconvénients rempli avec des données réelles issues des prototypes).
4. Faire valider le choix final par l'encadrante avant de lancer la Phase 6.

**Livrable** : document `05-architecture-cible.md` avec le comparatif rempli et la décision argumentée.

**Difficultés possibles** : tentation de se précipiter vers l'approche la plus familière sans l'avoir réellement comparée ; risque de sous-estimer la complexité de la synchronisation temps réel avec AutoCAD Map 3D.

**Conseils** : privilégier une approche progressive — commencer par une génération de schéma statique (approche A), qui a une valeur pédagogique et de démonstration immédiate, avant d'attaquer l'intégration temps réel avec Map 3D.

---

### Phase 6 — Implémentation

**Pourquoi c'est important** : c'est la phase de concrétisation du choix d'architecture, dans un cadre structuré évitant la dette technique.

**Sous-étapes** :
1. **Préparation** : mise en place de l'environnement de développement (dépôt Git, structure de projet, environnement PostgreSQL/PostGIS de développement, gestion des dépendances).
2. **Développement** : développement incrémental, fonctionnalité par fonctionnalité (ex. d'abord la génération de schéma pour une classe d'objets simple sans géométrie, puis avec géométrie, puis avec relations).
3. **Tests unitaires** : tester chaque brique indépendamment (parseur du Data Model, générateur SQL, couche d'accès aux données).
4. **Validation** : vérifier le résultat dans PostgreSQL (structure attendue) puis, si possible, dans AutoCAD Map 3D.
5. **Corrections** : boucle itérative de correction basée sur les résultats de validation.

**Livrables** : code source versionné, documentation d'installation, journal des décisions techniques.

**Outils utiles** : Git/GitHub, un framework de test adapté au langage choisi (pytest si Python, NUnit/xUnit si C#), Docker pour isoler PostgreSQL.

**Difficultés possibles** : divergence entre le comportement réel d'AutoCAD Map 3D et les hypothèses issues des phases précédentes — prévoir du temps de re-analyse.

---

### Phase 7 — Validation

**Pourquoi c'est important** : garantir que la solution développée reproduit un comportement fonctionnel équivalent à TKI PGP, du point de vue de l'utilisateur final.

**Scénario de test de bout en bout proposé** :

```
Créer un Industry Model (Data Model de test)
        │
        ▼
Générer/synchroniser le schéma PostgreSQL/PostGIS
        │
        ▼
Ouvrir AutoCAD Map 3D et se connecter à la base
        │
        ▼
Vérifier :
  - lecture des objets existants (affichage carte + attributs) ;
  - création d'un nouvel objet (géométrie + attributs) ;
  - modification d'un objet existant ;
  - suppression d'un objet ;
  - synchronisation correcte avec PostgreSQL (les changements persistent) ;
  - cohérence des données (contraintes, relations respectées).
```

**Stratégie de tests complète proposée** :
- Tests unitaires sur chaque composant logiciel développé (voir Phase 6).
- Tests d'intégration automatisés autant que possible (ex. script qui génère un schéma puis vérifie par requête SQL que les tables/colonnes attendues existent).
- Tests manuels guidés dans AutoCAD Map 3D pour les scénarios utilisateur (checklist reproductible, avec captures d'écran).
- Tests de non-régression à chaque évolution majeure du Data Model de test.
- Journal de bugs/anomalies avec statut (ouvert/résolu).

**Livrable** : plan de tests documenté + rapport de validation final.

---

## 6. Technologies à apprendre

| Technologie | Pourquoi elle est nécessaire |
|---|---|
| **AutoCAD Map 3D** | Client final utilisateur, à comprendre pour valider toute solution. |
| **Autodesk Infrastructure Administrator** | Outil de création/gestion des Industry Models — cœur du sujet de stage. |
| **PostgreSQL** | Base de données cible de substitution. |
| **PostGIS** | Extension spatiale indispensable pour gérer les géométries. |
| **SQL / SQLite** | Nécessaire pour analyser le Data Model exporté et concevoir le schéma cible. |
| **Un langage de scripting (Python recommandé, ou C#/.NET)** | Pour développer les outils de génération/synchronisation de schéma. |
| **Git** | Gestion de version, indispensable pour un travail en binôme. |
| **Notions de SIG (systèmes de coordonnées, formats géospatiaux)** | Nécessaires pour comprendre et manipuler correctement les géométries. |
| **(Optionnel) API .NET AutoCAD / ObjectARX** | Si l'architecture retenue en Phase 5 nécessite un plugin natif Map 3D **[À VÉRIFIER selon le choix final]**. |

---

## 7. Questions restant ouvertes

1. Le format exact du Data Model pour un Industry Model **base de données** (Oracle/SQL Server) est-il identique, structurellement, au format SQLite obtenu lors d'un export pour Fachschalenvorlage ? **[À VÉRIFIER]**
2. TKI PGP crée-t-il un schéma PostgreSQL entièrement nouveau à partir du Data Model, ou reproduit-il fidèlement une structure Oracle/SQL Server existante ? **[À VÉRIFIER]**
3. Existe-t-il une API publique (ObjectARX, .NET, ou REST) permettant d'interroger/modifier un Industry Model par programmation, indépendamment du pilote de base de données ? **[À VÉRIFIER]**
4. Quel est le mécanisme exact de verrouillage/synchronisation multi-utilisateur d'un Industry Model (« check-out / check-in » ?) et devra-t-il être reproduit dans notre solution ? **[À VÉRIFIER]**
5. Le connecteur FDO PostgreSQL déjà natif à AutoCAD Map 3D peut-il servir de brique de base pour notre solution, ou est-il technique­ment trop limité (pas de notion de « classes métier », de règles, de formulaires) pour remplir les objectifs du stage ? **[À VÉRIFIER par prototype, Phase 5]**
6. Quelles licences seront réellement disponibles pour nous (AutoCAD Map 3D éducation, éventuellement licence d'essai TKI PGP à titre de référence comparative) ? **[À VÉRIFIER avec l'encadrante]**
7. Le périmètre du stage inclut-il la gestion des règles métier et des formulaires (Formulaire-Designer), ou se limite-t-il au stockage des données et géométries ? **[À VÉRIFIER avec l'encadrante — point de cadrage important]**

---

## 8. Roadmap détaillée (indicative)

> Les durées sont **indicatives** et doivent être ajustées avec l'encadrante en fonction de la durée réelle du stage.

| Jalon | Objectif | Durée estimée | Dépendances | Livrables | Critère de validation |
|---|---|---|---|---|---|
| J1 | Phase 1 — Comprendre Autodesk | 2 semaines | Accès logiciel AutoCAD Map 3D | `01-autodesk-architecture.md` | Un Industry Model fichier créé et documenté |
| J2 | Phase 2 — Comprendre PostgreSQL/PostGIS | 1,5 semaine | — (peut être menée en parallèle de J1) | `02-postgis-postgresql.md` | Connexion FDO PostgreSQL testée dans Map 3D |
| J3 | Phase 3 — Étudier le Data Model | 3 semaines | J1 | `03-data-model-analyse.md` + fichiers SQLite d'exemple | Structure du Data Model SQLite entièrement cataloguée |
| J4 | Phase 4 — Rôle de TKI PGP | 2 semaines | J1, J2, J3 | `04-role-tki-pgp.md` | Tableau Documenté/Hypothèse/À vérifier complété |
| J5 | Phase 5 — Conception de la solution | 2 semaines | J1–J4 | `05-architecture-cible.md` + prototypes de comparaison | Architecture validée par l'encadrante |
| J6 | Phase 6 — Implémentation | 4 à 6 semaines | J5 | Code source, documentation technique | Fonctionnalités clés opérationnelles (génération de schéma + accès basique depuis Map 3D) |
| J7 | Phase 7 — Validation | 2 semaines | J6 | Plan de tests + rapport de validation | Scénario de bout en bout exécuté avec succès |
| J8 | Rédaction du rapport de stage / soutenance | 2 semaines | J1–J7 | Rapport final, support de soutenance | Rapport complet et cohérent |

---

## 9. Livrables du stage

**Livrables techniques :**
- Code source de la solution (dépôt Git structuré).
- Scripts de génération de schéma PostgreSQL/PostGIS à partir d'un Data Model.
- Exemples de Data Models de test (fichiers SQLite) et schémas PostgreSQL correspondants.
- Suite de tests (unitaires + scénario de validation de bout en bout).
- Documentation d'installation et d'utilisation de la solution développée.

**Livrables documentaires :**
- Ce README technique, tenu à jour tout au long du stage.
- Les documents de phase (`01-...md` à `05-...md`) produits en section 5.
- Le tableau des questions ouvertes, mis à jour au fur et à mesure des réponses obtenues.
- Un journal de bord (avancement hebdomadaire).
- Le rapport de stage final et le support de soutenance.

---

## Annexe A — Sources consultées pour ce document

- Documentation officielle Autodesk (aide AutoCAD Map 3D / Infrastructure Administrator, plusieurs versions 2014–2025), notamment sur : l'outil Infrastructure Administrator et ses modules (Data Model Administrator, Formulaire-Designer, Sécurité-Administrator, import Oracle) ; la création de Fachschalenvorlage et l'export de Data Model en SQLite ; le connecteur FDO PostgreSQL/PostGIS natif de Map 3D.
- Forum développeur Autodesk (2014) confirmant que les Industry Models ne sont officiellement supportés que sur Oracle, SQL Server et SQLite (mode fichier).
- Sites officiels TKI (tki-chemnitz.com / tki-net.com / help.tki-chemnitz.de) décrivant le produit **PGP (PostgreSQL Provider)** et son intégration à Infrastructure Administrator, ainsi que les notes de version de **TKI NET**.

Toute information non issue de ces sources et présentée dans ce document est explicitement signalée comme **[HYPOTHÈSE]** ou **[À VÉRIFIER]**, conformément à la consigne du projet.
