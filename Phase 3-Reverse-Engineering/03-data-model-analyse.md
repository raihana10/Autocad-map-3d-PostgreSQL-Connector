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
- **Ce qu'il faut observer** : apparition d'une nouvelle ligne dans une table de type « catalogue de classes » ; valeur du nom de classe ; présence d'un identifiant technique (ID) généré automatiquement.
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
- **Modification réalisée** : changer le type de géométrie de `TEST_CLASSE_GEO_01` de Point vers Ligne (Polyline).
- **Procédure détaillée** :
  1. Modifier uniquement le type géométrique.
  2. Sauvegarder et comparer avec l'état du Test 7.
- **Ce qu'il faut observer** : changement d'une valeur (code numérique ou texte) dans la table géométrique identifiée au Test 7.
- **Tables SQLite susceptibles d'être modifiées** : `GEOMETRYDEFINITION` (colonne type de géométrie).
- **Résultat attendu** : la colonne type géométrie passe d'une valeur « Point » à une valeur « Ligne » (ou codes numériques correspondants).
- **Capture d'écran à réaliser** : capture avant/après dans Infrastructure Administrator ; capture du diff SQLite.
- **Conclusion à noter** : Identifiant de type de classe devient `L` (Ligne) et `geometry_type` vaut 2 dans `geometry_columns`.

### Test 9 — Ajout d'une relation entre deux classes

- **Objectif** : identifier comment une relation (association) entre deux classes est représentée.
- **Modification réalisée** : créer une relation simple entre `TEST_CLASSE_01` et `TEST_CLASSE_GEO_01` (par exemple relation 1-N).
- **Procédure détaillée** :
  1. Créer la relation via l'outil dédié d'Infrastructure Administrator.
  2. Sauvegarder et comparer.
- **Ce qu'il faut observer** : nouvelle table ou nouvelles lignes référençant les deux classes via leurs identifiants respectifs ; encodage de la cardinalité.
- **Tables SQLite susceptibles d'être modifiées** : `RELATIONSHIPDEFINITION` (ou équivalent), éventuellement des colonnes de cardinalité (min/max occurrences).
- **Résultat attendu** : une ligne référençant les deux identifiants de classes avec un type/cardinalité de relation.
- **Capture d'écran à réaliser** : capture de la relation créée dans Infrastructure Administrator ; capture de la ligne SQLite correspondante.
- **Conclusion à noter** : AutoCAD crée une entrée dans `TB_RELATIONS` contenant le nom complet des tables Parent/Child et leurs clés, et génère explicitement un INDEX sur la colonne Child.

### Test 10 — Ajout d'un domaine de valeurs

- **Objectif** : localiser le stockage des domaines de valeurs (listes de valeurs autorisées, énumérations).
- **Modification réalisée** : créer un domaine `TEST_DOMAINE_01` avec deux ou trois valeurs (ex. `Acier`, `PVC`, `Fonte`).
- **Procédure détaillée** :
  1. Créer le domaine avec ses valeurs.
  2. Sauvegarder et comparer.
- **Ce qu'il faut observer** : une table « catalogue de domaines » et une table « valeurs de domaine » liée par clé étrangère.
- **Tables SQLite susceptibles d'être modifiées** : `DOMAIN` (ou équivalent), `DOMAINVALUE` (ou équivalent).
- **Résultat attendu** : une ligne de domaine et plusieurs lignes de valeurs associées.
- **Capture d'écran à réaliser** : capture du domaine créé dans Infrastructure Administrator ; capture des deux tables SQLite concernées.
- **Conclusion à noter** : Mapping vers une table de définition `TB_DOMAIN` et création d'une table SQL propre au domaine (ex: `TEST_DOMAINE_10_TBD`) contenant les valeurs.

### Test 11 — Modification d'un domaine

- **Objectif** : observer l'effet de l'ajout/suppression d'une valeur dans un domaine existant.
- **Modification réalisée** : ajouter une nouvelle valeur (`Cuivre`) au domaine `TEST_DOMAINE_01`.
- **Procédure détaillée** :
  1. Ajouter uniquement cette valeur.
  2. Sauvegarder et comparer avec l'état du Test 10.
- **Ce qu'il faut observer** : nouvelle ligne dans la table des valeurs de domaine, sans modification de la ligne « catalogue » du domaine (sauf éventuellement un numéro de version).
- **Tables SQLite susceptibles d'être modifiées** : `DOMAINVALUE` (ou équivalent).
- **Résultat attendu** : une ligne supplémentaire uniquement.
- **Capture d'écran à réaliser** : capture de la nouvelle valeur dans Infrastructure Administrator ; capture du diff SQLite.
- **Conclusion à noter** : Validé, ajout simple de type `INSERT` dans la table SQL cible, tout à fait incrémental.

### Test 12 — Héritage entre classes

- **Objectif** : localiser le mécanisme de représentation de l'héritage entre classes (classe parente / classe fille).
- **Modification réalisée** : créer une classe `TEST_CLASSE_FILLE_01` héritant de `TEST_CLASSE_01`.
- **Procédure détaillée** :
  1. Créer la classe fille en spécifiant la classe parente.
  2. Sauvegarder et comparer.
- **Ce qu'il faut observer** : une colonne de référence vers l'identifiant de la classe parente dans la table des classes.
- **Tables SQLite susceptibles d'être modifiées** : `CLASSDEFINITION` (colonne parent/superclasse).
- **Résultat attendu** : la ligne de la classe fille contient une clé étrangère vers la classe parente.
- **Capture d'écran à réaliser** : capture de l'héritage dans Infrastructure Administrator ; capture de la colonne parent dans SQLite.
- **Conclusion à noter** : L'héritage implique que la table fille regroupe (recopie physiquement) **toutes** les colonnes de la classe parente. Lien dans `TB_DICTIONARY.MODEL_F_CLASS_ID`.

### Test 13 — Nouvelle représentation graphique

- **Statut** : **ABANDONNÉ**
- **Justification** : La symbologie et l'affichage (couleurs, épaisseur) relèvent de la couche présentation applicative (QGIS ou Map 3D client). Il n'y a aucun impact sur la modélisation structurelle SQL.

### Test 14 — Ajout d'un Label

- **Statut** : **ABANDONNÉ**
- **Justification** : Relève exclusivement de l'étiquetage de présentation.

### Test 15 — Ajout d'un Template

- **Statut** : **ABANDONNÉ**
- **Justification** : Un template est un pur assistant UI de saisie. Ne touche pas le schéma logique SQLite.

### Test 16 — Renommage d'une classe

- **Objectif** : vérifier si le renommage modifie uniquement le nom ou également l'identifiant technique.
- **Modification réalisée** : renommer `TEST_CLASSE_01` en `TEST_CLASSE_01_RENAME`.
- **Procédure détaillée** :
  1. Renommer la classe.
  2. Sauvegarder et comparer.
- **Ce qu'il faut observer** : seule la colonne nom doit changer ; l'identifiant technique (clé primaire) et toutes les clés étrangères pointant vers cette classe doivent rester inchangés.
- **Tables SQLite susceptibles d'être modifiées** : `CLASSDEFINITION` (colonne nom uniquement).
- **Résultat attendu** : stabilité de l'identifiant technique malgré le changement de nom — point crucial pour la fiabilité du futur mapping.
- **Capture d'écran à réaliser** : capture avant/après du nom ; capture du diff SQLite montrant l'identifiant inchangé.
- **Conclusion à noter** : Seule la colonne `CAPTION` est altérée. Le nom de la table SQLite elle-même ne change pas, préservant la stabilité du modèle de données.

### Test 17 —  Suppression d'une classe

- **Objectif** : observer la propagation de la suppression d'une classe sur les objets qui en dépendent (attributs, relations, domaines associés).
- **Modification réalisée** : supprimer `TEST_CLASSE_FILLE_01`.
- **Procédure détaillée** :
  1. Supprimer la classe.
  2. Sauvegarder et comparer.
- **Ce qu'il faut observer** : suppression en cascade (ou non) des attributs et relations liés ; comportement des clés étrangères orphelines.
- **Tables SQLite susceptibles d'être modifiées** : `CLASSDEFINITION`, `ATTRIBUTEDEFINITION`, `RELATIONSHIPDEFINITION`.
- **Résultat attendu** : à déterminer — vérifier l'intégrité référentielle du fichier après suppression.
- **Capture d'écran à réaliser** : capture de la suppression ; capture du diff SQLite sur l'ensemble des tables concernées.
- **Conclusion à noter** : HARD DELETE applicable de la même manière sur une simple colonne (attribut drop).

### Test 18 — Suppression d'un attribut

- **Objectif** : observer si la suppression entraîne une suppression physique (DELETE) ou un marquage logique (soft delete).
- **Modification réalisée** : supprimer `TEST_ATTRIBUT_01`.
- **Procédure détaillée** :
  1. Supprimer l'attribut.
  2. Sauvegarder et comparer.
- **Ce qu'il faut observer** : disparition complète de la ligne, ou au contraire présence d'une colonne de statut (ex. `deleted = 1`) sans suppression physique.
- **Tables SQLite susceptibles d'être modifiées** : `ATTRIBUTEDEFINITION`.
- **Résultat attendu** : à déterminer par l'observation — les deux comportements sont plausibles selon l'implémentation Autodesk.
- **Capture d'écran à réaliser** : capture de la suppression dans Infrastructure Administrator ; capture du diff SQLite (ligne disparue ou marquée).
- **Conclusion à noter** : C'est une destruction matérielle complète (HARD DELETE) de la table physique. Cela engendre le DROP CASCADE manuel des références metadata dans tous les catalogues.

### Test 19 — Comparaison automatique des schémas SQLite

- **Objectif** : valider et outiller la méthode de comparaison utilisée tout au long de la campagne, afin de la rendre reproductible et scriptable.
- **Modification réalisée** : aucune modification fonctionnelle ; il s'agit de mettre en place un script de comparaison automatique entre deux exports `.schema`/`.dump`.
- **Procédure détaillée** :
  1. Sélectionner deux états déjà produits lors des tests précédents.
  2. Écrire un script (shell ou Python) automatisant l'export et le `diff`.
  3. Valider que le script produit les mêmes résultats que l'analyse manuelle réalisée précédemment.
- **Ce qu'il faut observer** : cohérence entre le résultat du script et les observations manuelles déjà consignées.
- **Tables SQLite susceptibles d'être modifiées** : aucune (test d'outillage, non de modification).
- **Résultat attendu** : un script fiable et réutilisable pour l'ensemble des tests futurs, et pour la phase suivante du projet.
- **Capture d'écran à réaliser** : capture de la sortie du script de comparaison.
- **Conclusion à noter** : L'utilisation de notre script `compare_sqlite.py` s'est avérée vitale pour le nettoyage du bruit SQLite et l'interprétation fiable.

### Test 20 — Correspondance entre Infrastructure Administrator et SQLite

- **Objectif** : réaliser une synthèse croisée, classe par classe et concept par concept, entre ce qui est visible dans l'interface d'Infrastructure Administrator et sa traduction exacte en SQLite.
- **Modification réalisée** : aucune nouvelle modification ; il s'agit d'un test de consolidation reprenant l'ensemble des classes de test créées (Tests 1 à 18).
- **Procédure détaillée** :
  1. Parcourir intégralement l'arborescence du Data Model dans Infrastructure Administrator.
  2. Pour chaque élément rencontré, retrouver sa ligne correspondante en SQLite en s'appuyant sur les identifiants techniques (jamais sur les noms, cf. Test 16).
  3. Construire un tableau de correspondance final.
- **Ce qu'il faut observer** : absence d'élément visible dans l'interface sans équivalent SQLite identifié, et inversement, absence de ligne SQLite « métier » non expliquée par un élément visible.
- **Tables SQLite susceptibles d'être modifiées** : aucune (test de synthèse).
- **Résultat attendu** : un mapping complet et validé, condition de sortie de la phase 3.
- **Capture d'écran à réaliser** : capture de synthèse de l'arborescence complète, en vis-à-vis des tables SQLite peuplées.
- **Conclusion à noter** : Objectif atteint. Les correspondances tables système/physique sont totalement comprises et synthétisées en Section 6.

---

## 5. Tableau de suivi

Le tableau ci-dessous est destiné à être rempli au fur et à mesure de la réalisation de chaque test. Il constitue la trace de référence pour la construction du mapping final.

| Test | Modification réalisée | Tables modifiées | Colonnes modifiées | Observation | Interprétation | Capture disponible (Oui/Non) |
|---|---|---|---|---|---|---|
| 0 | État initial | Aucune | Aucune | Baseline de référence générée | Structure minimale, présence de tables sytème (TB_...) | Oui |
| 1 | Ajout d'une classe (TEST_CLASSE_01) | `TB_DICTIONARY`, `TB_ATTRIBUTE`, `fdo_columns` | `TEST_CLASSE_01` (créée) | Création de la table physique et inscription dans les tables systèmes | Mapping 1-1 entre la classe et une table physique. | Oui |
| 2 | Ajout d'un attribut | `TB_ATTRIBUTE`, `fdo_columns` | `TEST_ATTRIBUT_01` (créée) | Attribut physique créé dans la table `TEST_CLASSE_01` | Chaque attribut est une colonne physique dans la table de sa classe. | Oui |
| 3 | Ajout d'un attribut (Type numérique) | `TB_ATTRIBUTE`, `fdo_columns` | `TEST_ATTRIBUT_02` (créée) | Création physique (INTEGER(10)) | Respect minutieux du type numérique en SQL. | Oui |
| 4 | Valeur par défaut | `TB_ATTRIBUTE`, `fdo_columns` | `TEST_ATTRIBUT_03` (créée) | Ajout de l'attribut avec contrainte DEFAULT 0 | Le schéma natif DDL intègre les valeurs par défaut. | Oui |
| 5 | Attribut obligatoire | `TB_ATTRIBUTE`, `fdo_columns` | `TEST_ATTRIBUT_05` (créée) | Ajout de l'attribut avec contrainte NOT NULL | Les contraintes d'obligation deviennent NOT NULL. | Oui |
| 6 | Longueur d'un champ | N/A | N/A | Test abandonné (redondance) | La configuration de longueur est déjà vérifiée dans le Test 2 (via `Varchar2(10)`). | Non |
| 7 | Nouvelle classe géométrique | `TB_DICTIONARY`, `TB_ATTRIBUTE`, `geometry_columns`, `fdo_columns` | `TEST_CLASSE_GEO_01` (créée) | Table créée avec colonnes Z, ORIENTATION, GEOM. `F_CLASS_TYPE` = 'P' | Les tables AutoCAD stockent la géométrie et la lient à `geometry_columns`. | Oui |
| 8 | Changement du type de géométrie | `TB_DICTIONARY`, `geometry_columns` | `TEST_CLASS_GEO_02` (créée) | `F_CLASS_TYPE` = 'L', `geometry_type` = 2 | Chaque classe fige son type (Ligne = L). | Oui |
| 9 | Relation entre deux classes | `TB_RELATIONS` | `TEST_ATTRIBUT_09` (créée) | Entrée parent/enfant dans `TB_RELATIONS` et ajout d'un index explicite. | AutoCAD crée manuellement les relations et un index pour les optimiser. | Oui |
| 10 | Ajout de domaine de valeurs | `TB_DOMAIN`, `TB_RELATIONS` | `TEST_DOMAINE_10_TBD` (créée) | Création d'une table catalogue dédiée et enregistrement dans `TB_DOMAIN`. | Un domaine est matérialisé par sa propre table de valeurs. | Oui |
| 11 | Modification de domaine | `TEST_DOMAINE_10_TBD` | Aucune | Ligne 'Cuivre' ajoutée à la table de domaine. | Ajout transparent (incrémental) sans impact sur la configuration métier. | Oui |
| 12 | Héritage entre classes | `TB_DICTIONARY`, `TB_ATTRIBUTE`, `fdo_columns` | `TEST_CLASSE_FILLE_01` (créée) | La table hérite *physiquement* des attributs du parent. | L'héritage d'Autodesk recopie les colonnes parentes dans la table fille SQL. | Oui |
| 13 | Représentation graphique | N/A | N/A | Test abandonné (Couche de présentation) | L'affichage (couleur/symbole) ne modifie pas le modèle relationnel. | Non |
| 14 | Ajout d'un Label | N/A | N/A | Test abandonné (Couche de présentation) | Idem, cela indique à l'interface client de Map 3D quoi afficher. | Non |
| 15 | Ajout d'un Template | N/A | N/A | Test abandonné (Couche de présentation) | Le template est un assistant de saisie de l'UI. | Non |
| 16 | Renommage d'une classe | `TB_DICTIONARY` | Aucune | Seule `CAPTION` est modifiée | Le nom physique de la table reste inchangé, l'UI modifie un label. | Oui |
| 17 | Suppression d'une classe | `TB_DICTIONARY`, `TB_ATTRIBUTE`, `TB_RELATIONS` | `TEST_CLASSE_FILLE_01` (supprimée) | Suppression (hard delete) de la table physique et de ses entrées catalogues. | Casse en cascade les objets metadata du système (tables systèmes auto-nettoyées). | Oui |
| 18 | Suppression d'un attribut | `TB_ATTRIBUTE`, `fdo_columns` | `TEST_ATTRIBUT_01` (supprimée) | Suppression (DROP) physique de la colonne | Vrai suppression sans soft-delete. | Oui |
| 19 | Comparaison auto | N/A | N/A | Les fichiers `rapport_*.md` générés avec succès | Validation des outils de comparaison. | Oui |
| 20 | Correspondance IA / SQLite | N/A | N/A | Achevé | Modèle parfaitement mappé pour Postgres. | Oui |

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
- **Héritage** → (Test 12) Déclaré dans `TB_DICTIONARY` (`MODEL_F_CLASS_ID`), et AutoCAD Map **recopie physiquement** tous les champs hérités dans la table fille SQL.

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

