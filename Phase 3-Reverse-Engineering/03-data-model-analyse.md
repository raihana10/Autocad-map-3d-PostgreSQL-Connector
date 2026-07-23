# 03 — Analyse et Reverse Engineering du Data Model Autodesk

> **Phase 3 du projet de recherche** — Compréhension du fonctionnement interne des Industry Models Autodesk en vue du développement d'un convertisseur automatique Data Model Autodesk → PostgreSQL/PostGIS.

---

## Sommaire

1. [Objectif de la phase](#1-objectif-de-la-phase)
2. [Principe du reverse engineering](#2-principe-du-reverse-engineering)
3. [Outils utilisés](#3-outils-utilisés)
4. [Campagne complète de tests](#4-campagne-complète-de-tests)
5. [Tableau de suivi](#5-tableau-de-suivi)
6. [Analyse finale](#6-analyse-finale)
7. [Conclusion](#7-conclusion)

---

## 1. Objectif de la phase

### 1.1 Pourquoi cette phase est la plus critique du projet

Le projet global vise à terme à produire un outil capable de lire un **Data Model Autodesk** (tel qu'il est défini dans **Autodesk Infrastructure Administrator**) et de générer automatiquement un **schéma PostgreSQL/PostGIS** strictement équivalent, sans dépendre d'Oracle ni de SQL Server comme bases de stockage intermédiaires.

Un tel convertisseur ne peut être conçu correctement que si l'on comprend **exactement** comment Autodesk traduit, en interne, les concepts manipulés dans l'interface graphique (classes, attributs, domaines, relations, représentations graphiques, etc.) en structures relationnelles concrètes. Cette phase 3 est donc la **fondation technique** de tout le reste du projet :

- Toute erreur d'interprétation à ce stade se répercutera mécaniquement sur la phase de génération du schéma PostgreSQL/PostGIS.
- Le mapping conceptuel construit ici (« telle notion du Data Model = telle(s) table(s)/colonne(s) SQLite ») constituera la **spécification fonctionnelle** du futur moteur de conversion.
- Sans cette phase, tout développement ultérieur reposerait sur des suppositions non vérifiées, ce qui est inacceptable dans un contexte de recherche rigoureux ou de mémoire de fin d'études.

> **Remarque**
> Cette phase ne vise pas à produire du code, mais à produire de la **connaissance vérifiée et documentée**. Le code viendra dans une phase ultérieure, une fois le modèle interne stabilisé.

### 1.2 Deux représentations d'un même objet

Il est essentiel de bien distinguer **deux couches** qui décrivent, chacune à sa manière, le même Data Model :

1. **La couche conceptuelle / applicative** : le Data Model tel qu'il est **visible et manipulable** dans Infrastructure Administrator (arborescence des classes, propriétés, domaines, relations, styles de représentation, etc.). C'est la vue destinée à l'utilisateur métier.
2. **La couche physique / de stockage** : la **représentation réelle** de ce même Data Model, persistée dans un fichier **SQLite** (extension généralement `.sqlite` ou équivalent selon la configuration du dépôt). C'est cette couche qui nous intéresse en priorité, car c'est elle qui devra être lue par notre futur outil de conversion.

```
┌──────────────────────────────────────┐
│      Infrastructure Administrator      │
│   (vue conceptuelle / interface UI)    │
│                                         │
│   Classe "Vanne"                       │
│     ├─ Attribut "Diametre" (Double)    │
│     ├─ Attribut "Materiau" (Domaine)   │
│     └─ Géométrie (Point)               │
└──────────────────┬────────────────────┘
                    │  persistance interne
                    ▼
┌──────────────────────────────────────┐
│         Fichier SQLite (moteur)        │
│      (vue physique / relationnelle)    │
│                                         │
│  Table CLASSDEFINITION                 │
│  Table ATTRIBUTEDEFINITION             │
│  Table DOMAIN                          │
│  Table GEOMETRYDEFINITION              │
│  ... (noms indicatifs, à vérifier)     │
└──────────────────────────────────────┘
```

L'objectif de cette phase est de construire, **empiriquement et avec preuves**, la table de correspondance entre ces deux couches.

> **Hypothèse**
> Le nom exact des tables et colonnes SQLite peut varier selon la version d'Autodesk Infrastructure Administrator utilisée (AutoCAD Map 3D / Autodesk Utility Design / etc.). Les noms mentionnés dans ce document sont **génériques et indicatifs** ; ils devront être confirmés ou corrigés lors de chaque test, colonne « Conclusion à noter ».

### 1.3 Ce que cette phase doit produire concrètement

À l'issue de cette phase, nous devons disposer de :

- Une cartographie table par table du schéma SQLite du Data Model.
- Une compréhension claire de la manière dont chaque concept métier (classe, attribut, domaine, relation, géométrie, label, template, héritage) est traduit en lignes/colonnes.
- Un ensemble de captures d'écran et de diffs SQLite servant de preuves reproductibles.
- Un tableau de suivi rempli, exploitable comme base de spécification pour le développement du convertisseur PostgreSQL/PostGIS.

---

## 2. Principe du reverse engineering

### 2.1 Méthodologie générale

La méthodologie retenue est celle du **reverse engineering par différentiel contrôlé** (differential analysis). Le principe est simple dans son énoncé mais exigeant dans son exécution : on observe l'effet, dans le fichier SQLite, d'**une seule modification connue et maîtrisée** effectuée dans Infrastructure Administrator.

> **Remarque**
> Cette approche s'inspire des techniques classiques de rétro-ingénierie de formats de fichiers propriétaires : on ne cherche pas à « deviner » la structure, on la **déduit** d'observations reproductibles.

### 2.2 Règle absolue : une seule modification à la fois

**Il ne faut jamais modifier plusieurs paramètres simultanément.**

Cette règle est la pierre angulaire de toute la démarche. Si l'on modifie deux paramètres en même temps (par exemple ajouter un attribut *et* changer son type dans la même opération), il devient impossible de savoir laquelle des deux modifications est responsable de tel ou tel changement observé dans le SQLite. Le diff perd alors toute valeur probante.

> **À vérifier**
> Certaines opérations d'Infrastructure Administrator peuvent déclencher des effets de bord automatiques (par exemple la création implicite d'un index ou d'une contrainte). Il faudra bien distinguer, dans les observations, ce qui relève de la modification volontaire de ce qui relève d'un effet de bord du logiciel.

### 2.3 Cycle opératoire

Chaque test suit rigoureusement le cycle suivant :

```
   ┌─────────────────────────┐
   │   Modification unique    │
   └────────────┬─────────────┘
                 ▼
   ┌─────────────────────────┐
   │        Sauvegarde         │
   └────────────┬─────────────┘
                 ▼
   ┌─────────────────────────┐
   │  Ouverture du SQLite      │
   └────────────┬─────────────┘
                 ▼
   ┌─────────────────────────┐
   │       Comparaison         │
   │  (état N vs état N-1)     │
   └────────────┬─────────────┘
                 ▼
   ┌─────────────────────────┐
   │        Observation        │
   └────────────┬─────────────┘
                 ▼
   ┌─────────────────────────┐
   │         Déduction         │
   └─────────────────────────┘
```

1. **Modification unique** : réaliser une seule action précise dans Infrastructure Administrator (ex. : ajout d'un attribut).
2. **Sauvegarde** : enregistrer le Data Model pour forcer la persistance dans le fichier SQLite sous-jacent.
3. **Ouverture du SQLite** : ouvrir une copie du fichier avec DB Browser for SQLite (ou équivalent).
4. **Comparaison** : comparer l'état du schéma/des données avec la copie précédente (avant modification).
5. **Observation** : noter précisément quelles tables, colonnes et valeurs ont changé.
6. **Déduction** : formuler une hypothèse sur le rôle de chaque table/colonne concernée.

### 2.4 Traçabilité systématique

Toutes les observations doivent être consignées dans le **tableau de suivi** (voir [section 5](#5-tableau-de-suivi)), sans exception, y compris lorsque le résultat d'un test est négatif ou inattendu (« aucun changement observé » est en soi une information précieuse).

> **Observation**
> Un test qui ne produit aucune modification visible dans le SQLite est tout aussi important qu'un test qui en produit une : il peut indiquer que la donnée est calculée dynamiquement, mise en cache ailleurs, ou stockée dans un fichier annexe non encore identifié.

### 2.5 Conditions de reproductibilité

Pour que chaque test soit exploitable scientifiquement, il convient de respecter les conditions suivantes :

- Travailler sur une **copie de sauvegarde** du Data Model avant toute campagne de tests.
- Copier le fichier SQLite **avant** et **après** chaque modification, avec un nommage horodaté (ex. `datamodel_test01_avant.sqlite`, `datamodel_test01_apres.sqlite`).
- Fermer proprement Infrastructure Administrator (ou forcer la sauvegarde) avant toute inspection du SQLite, afin d'éviter les verrous de fichier ou les écritures partielles.
- Ne jamais inspecter le SQLite pendant qu'Infrastructure Administrator le tient ouvert en écriture.

---

## 3. Outils utilisés

| Outil | Rôle dans la démarche |
|---|---|
| **Infrastructure Administrator** | Interface graphique Autodesk permettant de créer, modifier et gérer le Data Model (classes, attributs, domaines, relations, représentations). C'est l'outil qui **génère** les modifications que nous allons observer. |
| **DB Browser for SQLite** | Outil graphique libre permettant d'ouvrir, parcourir et comparer visuellement le schéma et les données du fichier SQLite. Utilisé pour l'inspection manuelle table par table après chaque test. |
| **SQL Sheet** | Interface d'exécution de requêtes SQL (intégrée à l'environnement de travail) permettant d'interroger directement le contenu des tables SQLite via des requêtes `SELECT` ciblées, utile pour vérifier rapidement une hypothèse sans naviguer manuellement dans l'interface graphique. |
| **sqlite3 CLI** | Outil en ligne de commande permettant d'automatiser l'export du schéma (`.schema`), l'export de données (`.dump`), et la production de fichiers texte comparables entre deux états du Data Model. Indispensable pour produire des diffs reproductibles et scriptables. |
| **Outil diff (comparaison de schémas)** | Outil de comparaison textuelle (par exemple `diff`, `git diff`, ou un outil dédié de comparaison de schémas SQLite) permettant de mettre en évidence automatiquement les différences entre l'export « avant » et l'export « après » d'un test. C'est l'outil qui matérialise concrètement l'étape « Comparaison » du cycle opératoire. |

> **Remarque**
> L'usage combiné de `sqlite3 .schema` (pour le schéma) et `sqlite3 .dump` (pour les données) avant/après chaque test, associé à un `diff` textuel, constitue la méthode la plus fiable et la plus reproductible. DB Browser for SQLite et SQL Sheet servent surtout à l'exploration exploratoire et à la vérification visuelle des hypothèses.

### 3.1 Procédure type d'extraction pour comparaison

# Avant modification
sqlite3 datamodel.sqlite ".schema" > schema_avant.sql
sqlite3 datamodel.sqlite ".dump"   > dump_avant.sql

# ... réalisation de la modification unique dans Infrastructure Administrator ...
# ... sauvegarde du Data Model ...

# Après modification
sqlite3 datamodel.sqlite ".schema" > schema_apres.sql
sqlite3 datamodel.sqlite ".dump"   > dump_apres.sql

Nous avons automatisé la comparaison en développant un script Python dédié (`compare_sqlite.py`) qui se charge de vérifier en profondeur et d'isoler de façon intelligente les différences de schémas et de données (dump) plutôt que d'utiliser de simples diff textuels :

```bash
# Lancement de l'outil de comparaison Python sur deux états
python compare_sqlite.py schema_testN.sql schema_testN1.sql \\
                              dump_testN.sql   dump_testN1.sql \\
                              -o rapport_testN_vs_testN1.md
```

---

## 4. Campagne complète de tests

> **Remarque générale**
> Chaque test suit systématiquement le même canevas : **Objectif**, **Modification réalisée**, **Procédure détaillée**, **Ce qu'il faut observer**, **Tables SQLite susceptibles d'être modifiées**, **Résultat attendu**, **Capture d'écran à réaliser**, **Conclusion à noter**. Les noms de tables indiqués sont des hypothèses de travail à confirmer test après test.

### Test 0 — État initial

- **Objectif** : établir une référence (baseline) avant toute modification, afin de disposer d'un point de comparaison pour tous les tests suivants.
- **Modification réalisée** : aucune. Il s'agit d'un état de référence.
- **Procédure détaillée** :
  1. Créer un Data Model vierge ou minimal dans Infrastructure Administrator.
  2. Sauvegarder.
  3. Copier le fichier SQLite obtenu sous le nom `datamodel_test00_reference.sqlite`.
  4. Exporter le schéma complet (`.schema`) et le dump complet (`.dump`).
- **Ce qu'il faut observer** : la liste complète des tables présentes par défaut, leurs colonnes, leurs types, ainsi que les données déjà présentes (tables système, métadonnées de version, etc.).
- **Tables SQLite susceptibles d'être modifiées** : toutes (inventaire initial, pas de modification).
- **Résultat attendu** : un référentiel complet du schéma « à vide », servant de socle de comparaison pour tous les tests suivants.
- **Capture d'écran à réaliser** : vue d'ensemble de l'arborescence du Data Model dans Infrastructure Administrator ; vue d'ensemble des tables dans DB Browser for SQLite.
- **Conclusion à noter** : Validé. Présence de nombreuses tables système Autodesk (préfixées par TB_) générées par défaut à l'initialisation.

### Test 1 — Ajout d'une classe

- **Objectif** : identifier la ou les tables responsables du stockage de la définition d'une classe (entité métier) du Data Model.
- **Modification réalisée** : création d'une nouvelle classe non géométrique, avec un nom simple et identifiable (ex. `TEST_CLASSE_01`).
- **Procédure détaillée** :
  1. Dans Infrastructure Administrator, créer une nouvelle classe nommée `TEST_CLASSE_01`, sans attribut additionnel.
  2. Sauvegarder le Data Model.
  3. Copier le fichier SQLite résultant.
  4. Comparer avec l'état du Test 0.
- **Ce que l'on a observé** : apparition d'une nouvelle ligne dans une table de type « catalogue de classes » ; valeur du nom de classe ; présence d'un identifiant technique (ID) généré automatiquement.
- **Tables SQLite susceptibles d'être modifiées** : `CLASSDEFINITION` (ou équivalent), éventuellement une table de métadonnées ou de version incrémentée.
- **Résultat attendu** : une nouvelle ligne correspondant exactement au nom `TEST_CLASSE_01`, avec un identifiant unique.
- **Capture d'écran à réaliser** : capture de la classe créée dans l'arborescence Infrastructure Administrator ; capture de la nouvelle ligne dans DB Browser for SQLite.
- **Conclusion à noter** : `TB_DICTIONARY` est le catalogue maître des classes.

### Test 2 — Ajout d'un attribut

- **Objectif** : identifier la table responsable du stockage des attributs (propriétés) d'une classe.
- **Modification réalisée** : ajout d'un attribut simple (ex. `TEST_ATTRIBUT_01`, type texte) à la classe créée au Test 1.
- **Procédure détaillée** :
  1. Ouvrir `TEST_CLASSE_01`.
  2. Ajouter un attribut nommé `TEST_ATTRIBUT_01` de type Texte (String), sans autre paramétrage.
  3. Sauvegarder et comparer avec l'état du Test 1.
- **Ce qu'il faut observer** : apparition d'une nouvelle ligne liée par clé étrangère à la classe `TEST_CLASSE_01` ; structure du lien classe ↔ attribut.
- **Tables SQLite susceptibles d'être modifiées** : `ATTRIBUTEDEFINITION` (ou équivalent), table de liaison classe-attribut si elle existe séparément.
- **Résultat attendu** : une ligne d'attribut référençant l'identifiant de `TEST_CLASSE_01` via une clé étrangère.
- **Capture d'écran à réaliser** : capture de l'attribut dans Infrastructure Administrator ; capture de la ligne correspondante en SQLite avec la clé étrangère mise en évidence.
- **Conclusion à noter** : `TB_ATTRIBUTE` est le catalogue des attributs. Une colonne physique est directement créée dans le DDL de la table parente.

### Test 3 — Modification du type d'un attribut

- **Objectif** : identifier comment le type de données d'un attribut est encodé (chaîne littérale, code numérique, table de référence des types).
- **Modification réalisée** : changer le type de `TEST_ATTRIBUT_01` de Texte vers Double (nombre décimal).
- **Procédure détaillée** :
  1. Modifier uniquement le type de l'attribut existant.
  2. Sauvegarder et comparer avec l'état du Test 2.
- **Ce qu'il faut observer** : la ou les colonnes dont la valeur change dans la ligne de l'attribut ; s'il s'agit d'un code numérique, rechercher une éventuelle table de référence des types de données.
- **Tables SQLite susceptibles d'être modifiées** : `ATTRIBUTEDEFINITION` (colonne type), éventuellement `DATATYPE` ou équivalent.
- **Résultat attendu** : la colonne type de l'attribut change de valeur ; aucune nouvelle ligne créée ailleurs si le type est un code fixe déjà existant.
- **Capture d'écran à réaliser** : capture avant/après du type dans Infrastructure Administrator ; capture du diff SQLite sur la ligne concernée.
- **Conclusion à noter** : Le type est défini directement en dur dans le DDL physique (ex: INTEGER(10)) et tracé via un code interne dans `fdo_columns`.

### Test 4 — Valeur par défaut

- **Objectif** : localiser le stockage d'une valeur par défaut associée à un attribut.
- **Modification réalisée** : définir une valeur par défaut (ex. `0` ou `"N/A"`) sur `TEST_ATTRIBUT_01`.
- **Procédure détaillée** :
  1. Définir la valeur par défaut sur l'attribut.
  2. Sauvegarder et comparer avec l'état du Test 3.
- **Ce qu'il faut observer** : apparition ou mise à jour d'une colonne dédiée dans la table des attributs (ou table annexe).
- **Tables SQLite susceptibles d'être modifiées** : `ATTRIBUTEDEFINITION` (colonne valeur par défaut).
- **Résultat attendu** : une colonne contenant exactement la valeur saisie.
- **Capture d'écran à réaliser** : capture du champ valeur par défaut dans Infrastructure Administrator ; capture de la colonne correspondante en SQLite.
- **Conclusion à noter** : Appliqué au niveau SQL par une simple instruction DEFAULT.

### Test 5 — Attribut obligatoire

- **Objectif** : localiser le stockage de la contrainte « obligatoire » (Required / Mandatory) sur un attribut.
- **Modification réalisée** : cocher l'option « obligatoire » sur `TEST_ATTRIBUT_01`.
- **Procédure détaillée** :
  1. Activer l'option obligatoire.
  2. Sauvegarder et comparer avec l'état du Test 4.
- **Ce qu'il faut observer** : changement d'une colonne booléenne (probablement 0/1) dans la table des attributs.
- **Tables SQLite susceptibles d'être modifiées** : `ATTRIBUTEDEFINITION` (colonne booléenne « required »/« mandatory »/« nullable »).
- **Résultat attendu** : une colonne booléenne passant de 0 à 1 (ou inversement selon la convention).
- **Capture d'écran à réaliser** : capture de la case à cocher dans Infrastructure Administrator ; capture du diff sur la colonne booléenne.
- **Conclusion à noter** : Appliqué physiquement au niveau SQL avec la contrainte NOT NULL.

### Test 6 — Longueur d'un champ

- **Objectif** : localiser le stockage de la longueur maximale d'un champ texte.
- **Statut** : **ABANDONNÉ**.
- **Justification** : Redondance — le comportement de la longueur maximale a déjà été observé et validé dans les Tests 1, 2 et 5 (ex: `Varchar2(10)` avec metadata dans `fdo_columns`).

### Test 7 — Nouvelle classe géométrique

- **Objectif** : identifier les différences structurelles entre une classe non géométrique et une classe géométrique (feature class).
- **Modification réalisée** : créer une nouvelle classe géométrique (ex. `TEST_CLASSE_GEO_01`) de type Point.
- **Procédure détaillée** :
  1. Créer la classe en précisant qu'elle possède une géométrie.
  2. Sauvegarder et comparer avec un état sans cette classe.
- **Ce qu'il faut observer** : lignes supplémentaires par rapport au Test 1 (classe simple), notamment dans une table dédiée à la géométrie.
- **Tables SQLite susceptibles d'être modifiées** : `CLASSDEFINITION`, `GEOMETRYDEFINITION` (ou équivalent), éventuellement une table de liaison classe-géométrie.
- **Résultat attendu** : une ligne classe classique **plus** une ligne dans une table géométrique référençant cette classe.
- **Capture d'écran à réaliser** : capture de la classe géométrique créée ; capture des deux tables SQLite concernées.
- **Conclusion à noter** : Enregistrement dans `geometry_columns` (standard SIG) et type de classe `P` (Point) dans `TB_DICTIONARY`.

### Test 8 — Changement du type de géométrie

- **Objectif** : localiser le stockage du type de géométrie (Point, Ligne, Polygone).
- **Modification réalisée** : création d'une nouvelle classe  `TEST_CLASSE_GEO_08`  avec le type Line String (Polyline).
- **Procédure détaillée** :
  1. créer la nouvelle classe `TEST_CLASSE_GEO_08` 
  2. Sauvegarder et comparer avec l'état du Test 7.
- **Ce qu'il faut observer** : changement d'une valeur (code numérique ou texte) dans la table géométrique identifiée au Test 7.
- **Tables SQLite susceptibles d'être modifiées** : `GEOMETRYDEFINITION` (colonne type de géométrie).
- **Résultat attendu** : la colonne type géométrie passe d'une valeur « Point » à une valeur « Ligne » (ou codes numériques correspondants).
- **Capture d'écran à réaliser** : capture avant/après dans Infrastructure Administrator ; capture du diff SQLite.

  ![Capture du Test 8](Test8/Screenshot%202026-07-16%20113143.png)

- **Conclusion à noter** : Identifiant de type de classe devient `L` (Ligne) et `geometry_type` vaut 2 dans `geometry_columns`.

### Test 9 — Ajout d'une relation entre deux classes

- **Objectif** : identifier comment une relation (association) entre deux classes est représentée.
- **Modification réalisée** : créer une relation simple entre `TEST_CLASSE_01` et `TEST_CLASSE_GEO_01` (par exemple relation 1-N).
- **Procédure détaillée** :
  1. Créer la relation via l'outil dédié d'Infrastructure Administrator.
  2. Sauvegarder et comparer.
- **Observation** : nouvelle table ou nouvelles lignes référençant les deux classes via leurs identifiants respectifs ; encodage de la cardinalité.
- **Tables SQLite modifiées** : `TB_RELATIONS` (nouvelle ligne décrivant parent/enfant), `TEST_CLASSE_01` (nouvelle colonne FK), `TB_ATTRIBUTE` et `fdo_columns` (déclaration de l'attribut).
- **Résultat attendu** : une ligne référençant les deux identifiants de classes avec un type/cardinalité de relation.


  ![Capture du Test 9 - vue 1](Test9/Screenshot%202026-07-16%20114643.png)

  ![Capture du Test 9 - vue 2](Test9/Screenshot%202026-07-16%20114658.png)

- **Conclusion** : la relation 1-N ne se limite pas à une simple description dans `TB_RELATIONS` : elle se matérialise aussi par l'ajout d'une colonne FK physique dans la table enfant, déclarée dans `TB_ATTRIBUTE` et `fdo_columns`, avec un index dédié. En revanche, aucune cardinalité (`MERGE_MODE` / `SPLIT_MODE`) n'a été enregistrée dans ce test simple ; un test complémentaire serait nécessaire pour vérifier où elle est stockée.

### Test 10.1 — Création d'un domaine de valeurs

- **Objectif** : localiser le stockage des domaines de valeurs (listes de valeurs autorisées, énumérations).
- **Modification réalisée** : créer un domaine `TEST_DOMAINE_10` avec  trois valeurs (ex. `Acier`, `PVC`, `Fonte`).
- **Procédure détaillée** :
  1. Créer le domaine avec ses valeurs.
  2. Sauvegarder et comparer.
- **Observation** : un catalogue de domaines et une table dédiée contenant les valeurs du domaine.
- **Tables SQLite modifiées** : `TB_DOMAIN` (catalogue des domaines), et une table dédiée générée dynamiquement portant le nom du domaine (ex. `TEST_DOMAINE_10_TBD`) contenant les valeurs.
- **Résultat attendu** : une ligne de domaine dans `TB_DOMAIN` et plusieurs lignes de valeurs associées dans la table dédiée du domaine.


 
- **Conclusion** : un domaine est matérialisé par son enregistrement dans `TB_DOMAIN` et par une table de valeurs dédiée (ex. `TEST_DOMAINE_10_TBD`).

### Test 10.2 — Rattachement d'un attribut à un domaine

- **Objectif** : vérifier comment un attribut référencé à un domaine est matérialisé dans le SQLite.
- **Modification réalisée** : créer un attribut `TEST_ATTRIBUT_10` dans `TEST_CLASSE_01` puis l'associer au domaine `TEST_DOMAINE_10`.
- **Procédure détaillée** :
  1. Ajouter l'attribut à la classe métier.
  2. Spécifier le domaine de valeurs dans l'interface.
  3. Sauvegarder et comparer avec l'état du Test 10.1.
- **Observation** : l'ajout d'une colonne FK physique dans la classe enfant, ainsi qu'une ligne de relation dans `TB_RELATIONS` pointant vers la table du domaine.
- **Tables SQLite modifiées (confirmé)** : `TB_RELATIONS` (ligne parent/enfant), `TEST_CLASSE_01` (nouvelle colonne FK), `TB_ATTRIBUTE` et `fdo_columns` (déclaration de l'attribut).
- **Résultat attendu** : une ligne dans `TB_RELATIONS` où `PARENT_TABLE_NAME` pointe vers la table du domaine, avec une colonne physique ajoutée à la table enfant.


 - **Conclusion** :  le rattachement d'un attribut à un domaine utilise exactement le même mécanisme qu'une relation classe-à-classe (Test 9) : ajout d'une colonne FK physique dans la table enfant, et une ligne `TB_RELATIONS` où `PARENT_TABLE_NAME` pointe vers la table du domaine plutôt que vers une classe métier. Aucune cardinalité (`MERGE_MODE` / `SPLIT_MODE`) n'a été enregistrée dans ce test simple ; un test complémentaire serait nécessaire pour vérifier où elle est stockée.
  ![Capture du Test 10 - vue 1](Test10/Screenshot%202026-07-16%20122339.png)

  ![Capture du Test 10 - vue 2](Test10/Screenshot%202026-07-16%20122411.png)

### Test 11 — Modification d'un domaine

- **Objectif** : observer l'effet de l'ajout/suppression d'une valeur dans un domaine existant.
- **Modification réalisée** : ajouter une nouvelle valeur (`Cuivre`) au domaine `TEST_DOMAINE_10`.
- **Procédure détaillée** :
  1. Ajouter uniquement cette valeur.
  2. Sauvegarder et comparer avec l'état du Test 10.
- **Observation** : une nouvelle ligne dans la table des valeurs de domaine, sans modification de la ligne « catalogue » du domaine (sauf éventuellement un numéro de version).
- **Tables SQLite modifiées** : la table dédiée du domaine créée au Test 10.1 (ici `TEST_DOMAINE_10_TBD`) — aucune autre table, ni `TB_DOMAIN`, ni structure, n'a été touchée.
- **Résultat observé** : une ligne supplémentaire uniquement.
- **Capture d'écran réalisée** : capture de la nouvelle valeur dans Infrastructure Administrator .

  ![Capture du Test 11](Test11/Screenshot%202026-07-16%20141255.png)

- **Conclusion** : ajout simple de type `INSERT` dans la table SQL cible, tout à fait incrémental.

### Test 12 — Héritage entre classes

- **Objectif** : localiser le mécanisme de représentation de l'héritage entre classes (classe parente / classe fille).
- **Modification réalisée** : créer une classe `TEST_CLASSE_FILLE_01` héritant de `TEST_CLASSE_01`.
- **Procédure détaillée** :
  1. Créer la classe fille en spécifiant la classe parente.
  2. Sauvegarder et comparer.
- **Observation** : l'héritage ne se limite pas à un simple lien de référence. La table fille est créée avec sa propre structure, puis reçoit l'ensemble des attributs hérités de la classe parente.
- **Tables SQLite modifiées (confirmé)** : `TEST_CLASSE_FILLE_01` (nouvelle table, structure complète), `TB_DICTIONARY` (lien logique via `MODEL_F_CLASS_ID`, pas via `PARENT_F_CLASS_ID`), `TB_ATTRIBUTE` et `fdo_columns` (recopie de tous les attributs hérités), `TB_RELATIONS` (recopie des relations/domaines hérités), `TB_RULE_BASE` (règles système standard), `TEST_CLASSE_01` (ajout de `MODEL_NAME` sur la classe parente devenue « modèle »).
- **Résultat observé** : la ligne de la classe fille est enregistrée dans `TB_DICTIONARY`, la table physique `TEST_CLASSE_FILLE_01` contient les colonnes héritées, et la classe parente reçoit un attribut `MODEL_NAME`.
- **Capture d'écran réalisée** : capture de l'héritage dans Infrastructure Administrator ; capture du diff SQLite correspondant.

  ![Capture du Test 12 - vue 1](Test12/Screenshot%202026-07-16%20142017.png)

  ![Capture du Test 12 - vue 2](Test12/Screenshot%202026-07-16%20142047.png)

- **Conclusion** : l'héritage chez Autodesk/ArcFM n'est pas une simple clé étrangère — c'est un héritage physique complet. La table fille recopie structurellement toutes les colonnes de la classe parente, y compris celles issues de relations ou de domaines, qui sont elles-mêmes redéclarées dans `TB_RELATIONS`. Le lien logique parent-enfant est porté par `TB_DICTIONARY.MODEL_F_CLASS_ID`, et non par `PARENT_F_CLASS_ID` (qui référence une classe système générique, `ID = 1`).


### Test 16 — Renommage d'une classe

- **Objectif** : vérifier si le renommage modifie uniquement le nom ou également l'identifiant technique.
- **Modification réalisée** : renommer `TEST_CLASSE_01` en `TEST_CLASSE_01_RENAME`.
- **Procédure détaillée** :
  1. Renommer la classe.
  2. Sauvegarder et comparer.
- **Observation** : le renommage ne modifie pas l'identifiant technique ni le nom physique de la table SQLite.
- **Tables SQLite modifiées (confirmé)** : `TB_DICTIONARY` uniquement — colonnes `CAPTION` (nom affiché) et `FEATURE_REPRESENTATION` (libellé dynamique généré, effet de bord du renommage). Aucun changement sur `F_CLASS_ID`, `F_CLASS_NAME`, ni sur le nom physique de la table SQLite.
- **Résultat observé** : stabilité de l'identifiant technique malgré le changement de nom — point crucial pour la fiabilité du futur mapping.
- **Capture d'écran réalisée** : capture avant/après du nom ; capture du diff SQLite montrant l'identifiant inchangé.

  ![Capture du Test 16](Test16/Screenshot%202026-07-16%20141255.png)

- **Conclusion** : seule `TB_DICTIONARY.CAPTION` porte le nom affiché à l'utilisateur ; le renommage met aussi à jour `FEATURE_REPRESENTATION` (libellé par défaut des objets). Le nom physique de la table SQLite et l'identifiant technique (`F_CLASS_ID`) restent totalement stables, confirmant que le mapping technique est indépendant du nom métier affiché. 
- Note annexe : un changement sans lien apparent (`TB_GN_FLYIN_USER.FLY_HEIGHT`) a aussi été observé — probablement un réglage de session sans rapport avec le test.

### Test 17 — Suppression d'une classe

- **Objectif** : observer la propagation de la suppression d'une classe sur les objets qui en dépendent (attributs, relations, domaines associés).
- **Modification réalisée** : supprimer `TEST_CLASSE_FILLE_01`.
- **Procédure détaillée** :
  1. Supprimer la classe.
  2. Sauvegarder et comparer.
- **Observation** : la suppression d'une classe déclenche un retrait complet des objets associés à cette classe, sans laisser de résidu visible.
- **Tables SQLite modifiées (confirmé)** : `TB_DICTIONARY`, `TB_ATTRIBUTE`, `TB_RELATIONS`, `TB_RULE_BASE`, `fdo_columns` — suppression en cascade totale de toutes les lignes créées au Test 12, plus `DROP TABLE TEST_CLASSE_FILLE_01`, ses index et ses triggers.
- **Résultat observé** : disparition complète de la table fille, de ses index, de ses triggers, ainsi que de toutes les lignes de métadonnées associées.
- **Capture d'écran réalisée** : capture de la suppression ; capture du diff SQLite sur l'ensemble des tables concernées.

  ![Capture du Test 17](Test17/Screenshot%202026-07-16%20145204.png)

- **Conclusion** : la suppression d'une classe applique un **hard delete en cascade complet et symétrique** à sa création — table, index, triggers, attributs, relations et règles sont tous supprimés sans laisser de résidu. La classe parente (`TEST_CLASSE_01`) n'est pas affectée, confirmant que l'héritage physique n'impacte que la table fille lors d'une suppression. 
- Note annexe : `TB_GN_FLYIN_USER.FLY_HEIGHT` varie de nouveau (retour à sa valeur initiale) — probablement un réglage de session sans rapport avec le test.

### Test 18 — Suppression d'un attribut

- **Objectif** : observer si la suppression entraîne une suppression physique (DELETE) ou un marquage logique (soft delete).
- **Modification réalisée** : supprimer `TEST_ATTRIBUT_01`.
- **Procédure détaillée** :
  1. Supprimer l'attribut.
  2. Sauvegarder et comparer.
- **Observation** : la suppression d'un attribut provoque la disparition réelle de la colonne physique et du catalogue associé, sans marquage logique.
- **Tables SQLite modifiées (confirmé)** : `TB_ATTRIBUTE` (déclaration catalogue), `fdo_columns` (déclaration FDO), et la table physique `TEST_CLASSE_01` elle-même (colonne réellement supprimée du schéma SQL, vrai `DROP COLUMN`).
- **Résultat observé** : suppression physique de la colonne, avec nettoyage en cascade des métadonnées associées.
- **Capture d'écran réalisée** : capture de la suppression dans Infrastructure Administrator ; capture du diff SQLite (ligne disparue ou marquée).

  ![Capture du Test 18](Test18/Screenshot%202026-07-16%20145352.png)

- **Conclusion** : hard delete confirmé — la colonne physique est réellement supprimée (`DROP COLUMN`), avec nettoyage en cascade de `TB_ATTRIBUTE` et `fdo_columns`. Aucun marquage logique (`deleted = 1`) n'est utilisé. Contrairement à la suppression d'une classe entière (Test 17), aucun index ni trigger n'est impacté ici, car ces objets sont rattachés à la classe et non à l'attribut individuel.




---

## 5. Tableau de suivi

| Test | Modification réalisée | Tables modifiées | Colonnes modifiées | Observation | Interprétation | Capture disponible (Oui/Non) |
|---|---|---|---|---|---|---|
| 0 | État initial | Aucune | Aucune | Baseline de référence générée | Structure minimale, présence de tables système (TB_...) | Oui |
| 1 | Ajout d'une classe (TEST_CLASSE_01) | `TB_DICTIONARY`, `TB_ATTRIBUTE`, `fdo_columns` | `TEST_CLASSE_01` (créée) | Création de la table physique et inscription dans les tables systèmes | Mapping 1-1 entre la classe et une table physique. | Oui |
| 2 | Ajout d'un attribut | `TB_ATTRIBUTE`, `fdo_columns` | `TEST_ATTRIBUT_01` (créée) | Attribut physique créé dans la table `TEST_CLASSE_01` | Chaque attribut est une colonne physique dans la table de sa classe. | Oui |
| 3 | Ajout d'un attribut (Type numérique) | `TB_ATTRIBUTE`, `fdo_columns` | `TEST_ATTRIBUT_02` (créée) | Création physique (INTEGER(10)) | Respect minutieux du type numérique en SQL. | Oui |
| 4 | Valeur par défaut | `TB_ATTRIBUTE`, `fdo_columns` | `TEST_ATTRIBUT_03` (créée) | Ajout de l'attribut avec contrainte DEFAULT 0 | Le schéma natif DDL intègre les valeurs par défaut. | Oui |
| 5 | Attribut obligatoire | `TB_ATTRIBUTE`, `fdo_columns` | `TEST_ATTRIBUT_05` (créée) | Ajout de l'attribut avec contrainte NOT NULL | Les contraintes d'obligation deviennent NOT NULL. | Oui |
| 7 | Nouvelle classe géométrique | `TB_DICTIONARY`, `TB_ATTRIBUTE`, `geometry_columns`, `fdo_columns` | `TEST_CLASSE_GEO_01` (créée) | Table créée avec colonnes Z, ORIENTATION, GEOM. `F_CLASS_TYPE` = 'P' | Les tables AutoCAD stockent la géométrie et la lient à `geometry_columns`. | Oui |
| 8 | Changement du type de géométrie | `TB_DICTIONARY`, `geometry_columns` | `TEST_CLASS_GEO_02` (créée) | `F_CLASS_TYPE` = 'L', `geometry_type` = 2 | Chaque classe fige son type (Ligne = L). | Oui |
| 9 | Relation entre deux classes (`TEST_CLASSE_01` ↔ `TEST_CLASSE_GEO_01`) | `TEST_CLASSE_01` (colonne FK), `TB_RELATIONS`, `TB_ATTRIBUTE`, `fdo_columns` | `TEST_ATTRIBUT_09` (créée, FK) | Colonne FK physique ajoutée dans la classe enfant + ligne parent/enfant dans `TB_RELATIONS` + index dédié (`TEST_CLASSE_01_IX1`) créé | Une relation n'est pas qu'une métadonnée : elle matérialise une vraie colonne FK dans la table enfant. Cardinalité (`MERGE_MODE`/`SPLIT_MODE`) non renseignée dans ce test simple. | Oui |
| 10.1 | Ajout d'un domaine de valeurs (`TEST_DOMAINE_10`) | `TB_DOMAIN`, `TEST_DOMAINE_10_TBD` (nouvelle table) | Aucune (table entière créée) | Table de valeurs dédiée créée (`Acier`, `PVC`, `Fonte`) + entrée catalogue dans `TB_DOMAIN` | Un domaine est matérialisé par sa propre table de valeurs, indépendamment de tout attribut. | Oui |
| 10.2 | Rattachement d'un attribut au domaine (`TEST_ATTRIBUT_10`) | `TEST_CLASSE_01` (colonne FK), `TB_RELATIONS`, `TB_ATTRIBUTE`, `fdo_columns` | `TEST_ATTRIBUT_10` (créée, FK) | Colonne FK ajoutée + ligne `TB_RELATIONS` où `PARENT_TABLE_NAME` pointe vers la table du domaine + index dédié (`TEST_CLASSE_01_IX2`) | Même mécanisme qu'une relation classe-classe (Test 9) : un domaine est traité comme une "classe parente" dans `TB_RELATIONS`. | Oui |
| 11 | Modification de domaine (ajout valeur `Cuivre`) | `TEST_DOMAINE_10_TBD` | Aucune | Ligne `Cuivre` ajoutée à la table de domaine ; `TB_DOMAIN` (catalogue) non modifié | Ajout transparent (simple `INSERT` incrémental), aucun impact structurel confirmé. | Oui |
| 12 | Héritage entre classes (`TEST_CLASSE_FILLE_01` hérite de `TEST_CLASSE_01`) | `TB_DICTIONARY`, `TB_ATTRIBUTE`, `TB_RELATIONS`, `TB_RULE_BASE`, `fdo_columns`, `TEST_CLASSE_01` (ajout `MODEL_NAME`) | `TEST_CLASSE_FILLE_01` (créée, structure complète copiée) | La table fille recopie toutes les colonnes du parent, y compris les relations/domaines hérités (`TB_RELATIONS`) ; lien d'héritage via `TB_DICTIONARY.MODEL_F_CLASS_ID` (pas `PARENT_F_CLASS_ID`) | Héritage physique complet : structure, attributs, relations et règles système sont tous recopiés dans la table fille. | Oui |
| 16 | Renommage d'une classe (`TEST_CLASSE_01` → `TEST_CLASSE_RENAME`) | `TB_DICTIONARY` | `CAPTION`, `FEATURE_REPRESENTATION` | Nom affiché changé + libellé dynamique généré automatiquement ; `F_CLASS_ID` et `F_CLASS_NAME` (nom physique) inchangés | Le renommage est purement cosmétique côté UI ; l'identifiant technique et le nom physique de la table SQL restent stables. Effet de bord non prévu sur `FEATURE_REPRESENTATION`. | Oui |
| 17 | Suppression d'une classe (`TEST_CLASSE_FILLE_01`) | `TB_DICTIONARY`, `TB_ATTRIBUTE`, `TB_RELATIONS`, `TB_RULE_BASE`, `fdo_columns` | `TEST_CLASSE_FILLE_01` (table supprimée, + 2 index + 5 triggers) | Hard delete complet et symétrique à la création (Test 12) ; classe parente (`TEST_CLASSE_01`) non affectée | Cascade totale et propre sur tout le catalogue, sans résidu ni clé étrangère orpheline. | Oui |
| 18 | Suppression d'un attribut (`TEST_ATTRIBUT_01`) | `TEST_CLASSE_01`, `TB_ATTRIBUTE`, `fdo_columns` | `TEST_ATTRIBUT_01` (colonne supprimée) | Colonne physique réellement supprimée (`DROP COLUMN`) + nettoyage catalogue/FDO ; aucun index/trigger impacté | Hard delete confirmé, symétrique à la création (Test 9) ; pas de soft delete (`deleted=1`). | Oui |

> **Remarque**
> Les tests 6, 13, 14 et 15 ont été volontairement exclus car ils n'impactent pas le Modèle de Données relationnel (voir Section 6.5).

---

## 6. Analyse finale

### 6.1 Méthode d'interprétation des résultats

Une fois l'ensemble des tests réalisés et le tableau de suivi rempli, l'interprétation a permis de **regrouper les observations par concept métier**, de déterminer la nature de tous les mécanismes et de les mapper en objets relationnels physiques.

### 6.2 Localisation des concepts clés

À partir des tests réalisés, voici les tables SQLite et mécanismes centraux d'Autodesk Infrastructure Administrator :

- **Classes** → Gérées principalement dans `TB_DICTIONARY`. AutoCAD utilise une table physique distincte pour chaque classe créée, respectant le nom interne (`F_CLASS_NAME`).
- **Attributs** → Enregistrés dans `TB_ATTRIBUTE` et `fdo_columns`. Chaque attribut instancie une nouvelle colonne dans la table cible correspondante avec ses contraintes traduites (ex: DEFAULT, NOT NULL testés lors des Tests 4 et 5). 
- **Domaines** → Définis dans `TB_DOMAIN` puis déployés en tant que tables réelles (ex: `TEST_DOMAINE_10_TBD` du Test 10) connectées par clé logique.
- **Relations** → Les relations parent/enfant utilisent la table `TB_RELATIONS` et déclenchent la création automatique d'un Index pour la clef étrangère cible (Test 9).
- **Géométries** → Référencées dans `geometry_columns` (qui s'apparente aux tables types de PostGIS). Autodesk sépare les points (`F_CLASS_TYPE = 'P'`, `geometry_type = 1`) des lignes (`geometry_type = 2`).
- **Héritage** → (Test 12) Déclaré dans `TB_DICTIONARY` via `MODEL_F_CLASS_ID`, et AutoCAD Map **recopie physiquement** tous les champs hérités dans la table fille SQL. Cet héritage est complet : il englobe les attributs métier, les relations/domaines et les métadonnées associées, et ne se limite pas à une simple clé étrangère.

### 6.3 Distinguer les catégories de tables

Grâce aux campagnes de tests, les concepts SQLite Autodesk ont pu être catégorisés :

| Catégorie | Description | Exemples typiques observés |
|---|---|---|
| **Tables métier** | Contiennent les définitions de l'utilisateur (classes, domaines). Tables à générer en PostgreSQL/PostGIS. | `TEST_CLASSE_01`, `TEST_CLASSE_GEO_01`, `TEST_DOMAINE_10_TBD` |
| **Tables système Autodesk (Catalogues)** | Définissant les structures logiques (métadonnées) du modèle tel que géré par les API C# / AutoCAD FDO. | `TB_DICTIONARY`, `TB_ATTRIBUTE`, `TB_RELATIONS`, `TB_DOMAIN`, `fdo_columns`, `geometry_columns` |
| **Tables de configuration/Interface** | Paramètres d'UI, d'affichage sans impact sur la structure relationnelle des données métier. | `TB_GN_FLYIN_USER`, `TB_SETTINGS` |
| **Générateurs / Séquences** | Simulants d'ID séquentielles gérant les primary keys. | `TB_SEQUENCE_EMULATION`, les nombreux Triggers générés |

> **Observation :**
> Lors de la suppression physique d'une classe (Test 17) ou d'un attribut (Test 18), Autodesk effectue un nettoyage en cascade total (hard delete) qui enlève toute trace des tables système ; une telle flexibilité nécessitera `ON DELETE CASCADE` sous PostgreSQL.

### 6.4 Vers la phase suivante

Cette phase a entièrement rempli son but : **démystifier la couche opaque d'Autodesk Infrastructure Administrator**. Pour le futur convertisseur automatisé, il suffira de lire `TB_DICTIONARY`, `TB_ATTRIBUTE`, et `TB_RELATIONS` pour collecter l'essentiel du modèle nécessaire pour le transformer en script DDL PostgreSQL/PostGIS. Aucune métadonnée cachée intraçable n'a été isolée.

### 6.5 Périmètre exclu (Tests 6, 13, 14, et 15)

Pour justifier l'abandon des Tests 6, 13, 14 et 15, il est primordial de revenir à l'objectif fondamental du projet : comprendre la structure interne du Data Model Autodesk (*Quelles tables, colonnes, contraintes et clés créer ?*) afin de générer automatiquement un schéma PostgreSQL/PostGIS.

- **Le Test 6 (Longueur)** a été jugé redondant suite au croisement des Tests 1, 2 et 5, montrant explicitement le comportement des longueurs de champs (ex : *Varchar2(10)*) ;
- **Le Test 13 (Représentation graphique)** ne concerne que la **stylisation SIG** (couleurs, épaisseurs, symboles). PostgreSQL ignore si une classe spatiale est censée être rouge ou pointillée ; ce style relève de l'application cliente (Map 3D, QGIS) ;
- **Le Test 14 (Labels)** représente uniquement l'étiquetage de la donnée (ex: Afficher le champ "ID" plutôt que "Diamètre" sur la carte) ;
- **Le Test 15 (Templates)** porte sur les assistants de saisie afin d'auto-remplir les champs, ce qui est une aide UI n'ayant aucun effet structurel ;

Ces fonctionnalités n'ont pas d'impact sur la structure relationnelle des données SQL. Elles relèvent de la couche de présentation ou de l'assistance à la saisie, et ne sont donc pas nécessaires pour atteindre l'objectif de conversion de phase.

---

## 7. Conclusion

Cette phase de reverse engineering du Data Model Autodesk permet désormais de comprendre et documenter intégralement le fonctionnement interne du Data Model, tel qu'il est physiquement stocké dans le fichier SQLite sous-jacent à Infrastructure Administrator.

Grâce à la méthodologie de modification unique et de comparaison différentielle appliquée, nous disposons à l'issue de cette phase :

- d'une cartographie validée et tracée des tables et colonnes du schéma SQL natif de l'application ;
- d'un ensemble de preuves reproductibles à travers tous les rapports ;
- d'une classification claire entre tables métier et tables système/catalogues ;
- de spécifications fonctionnelles robustes de la structure des géométries, des héritages et des contraintes.

Cette base permet d'asseoir sereinement la **phase suivante du projet** : le développement du système de **lecture automatique du Data Model SQLite et la génération de son schéma PostgreSQL/PostGIS équivalent**, coeur du développement de la Phase 4.

