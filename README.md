# Alternative libre à TKI PGP — Industry Model Autodesk vers PostgreSQL/PostGIS

> Projet de fin d'année (stage PFA) visant à concevoir une alternative open-source au connecteur commercial **TKI PGP**, permettant d'utiliser **PostgreSQL/PostGIS** comme moteur de stockage pour un **Industry Model** (Fachschale) Autodesk, en lieu et place d'Oracle ou de Microsoft SQL Server.

---

## Sommaire

- [Contexte](#contexte)
- [Problématique](#problématique)
- [Objectifs du projet](#objectifs-du-projet)
- [Architecture](#architecture)
- [Structure du dépôt](#structure-du-dépôt)
- [Technologies utilisées](#technologies-utilisées)
- [Méthodologie](#méthodologie)
- [Limites et périmètre](#limites-et-périmètre)
- [Auteurs](#auteurs)
- [Licence](#licence)

---

## Contexte

**AutoCAD Map 3D**, associé au module **Autodesk Infrastructure Administrator**, permet de créer des **Industry Models** (appelés *Fachschalen*) : des modèles de données métier destinés à la gestion d'infrastructures (réseaux d'eau, d'électricité, de gaz, de télécommunications, etc.).

Officiellement, un Industry Model de type « base de données » ne peut être créé que sur **Oracle** ou **Microsoft SQL Server**. **PostgreSQL** n'est pas proposé nativement, alors qu'il s'agit d'un système de gestion de base de données open source, gratuit, et disposant avec **PostGIS** d'une extension spatiale mature.

Pour combler ce manque, la société **TKI** commercialise un connecteur, **TKI PGP (PostgreSQL Provider)**, qui permet d'utiliser PostgreSQL/PostGIS comme moteur de stockage d'un Industry Model. Ce connecteur est cependant un produit **commercial et sous licence**.

## Problématique

Comment permettre à un Industry Model Autodesk d'être stocké et exploité dans PostgreSQL/PostGIS, avec un niveau de fonctionnalité comparable à TKI PGP (création du schéma, lecture, création, modification et suppression d'objets depuis AutoCAD Map 3D), **sans dépendre d'un produit commercial** ?

## Objectifs du projet

1. Comprendre en détail le fonctionnement interne du **Data Model** Autodesk (comment les classes d'objets, attributs, géométries, domaines et relations sont traduits en structures relationnelles).
2. Comprendre le périmètre fonctionnel exact de **TKI PGP**, à partir de sa documentation publique et de son comportement observable, sans rétro-ingénierie de son code.
3. Concevoir et comparer plusieurs architectures possibles pour une solution alternative.
4. Développer un outil capable de générer automatiquement un schéma **PostgreSQL/PostGIS** équivalent à partir d'un Data Model Autodesk.
5. Valider la solution par un scénario de bout en bout dans AutoCAD Map 3D.

## Architecture

### Architecture officielle Autodesk (référence)

```
Infrastructure Administrator ──► Data Model ──► Industry Model (Fachschale)
                                                        │
                                          ┌─────────────┴─────────────┐
                                          ▼                           ▼
                                       Oracle                    SQL Server
                                          │                           │
                                          └─────────────┬─────────────┘
                                                         ▼
                                                 AutoCAD Map 3D
```

### Architecture cible du projet

```
Infrastructure Administrator ──► Data Model (export SQLite)
                                          │
                                          ▼
                         Générateur de schéma PostgreSQL/PostGIS
                                  [en cours de conception]
                                          │
                                          ▼
                                PostgreSQL + PostGIS
                                          │
                                          ▼
                                 AutoCAD Map 3D
                            [couche d'accès à développer]
```



## Structure du dépôt

```
.
├── Phase 1/
│   └── 01-autodesk-architecture.md      # Phase 1 — architecture Autodesk observée
├── Phase 2/
│   └── 02-postgis-postgresql.md         # Phase 2 — PostgreSQL/PostGIS et connecteur FDO
├── Phase 3-Reverse-Engineering/
│   ├── compare_sqlite.py                # Script de comparaison automatisée de deux exports SQLite
│   ├── rapport_test1_vs_test2.md        # Exemple de rapport de comparaison
│   ├── Test0/ ... Test18/               # Campagne de tests différentiels (schéma + dump SQL par test)
│   └── PFA-Phase 3.xlsx                 # Support de travail / document de synthèse
└── README.md
```

> Les documents `0X-*.md` correspondent chacun au livrable d'une phase du projet et sont complétés au fur et à mesure de l'avancement.

## Technologies utilisées

- **AutoCAD Map 3D** / **Autodesk Infrastructure Administrator** — environnement de référence
- **PostgreSQL** / **PostGIS** — base de données cible
- **SQLite** — format de stockage intermédiaire du Data Model, analysé en Phase 3
- **Python** — scripts d'analyse et de comparaison (`compare_sqlite.py`)
- **Git** — gestion de version

## Méthodologie

La compréhension du Data Model Autodesk repose sur une méthode de **reverse engineering par différentiel contrôlé** : chaque test consiste à effectuer **une seule modification** dans Infrastructure Administrator (ajout d'une classe, d'un attribut, d'une relation, etc.), puis à comparer automatiquement l'état du schéma SQLite avant/après pour en déduire, par observation reproductible, la logique de correspondance entre le modèle conceptuel et sa représentation physique.

## Limites et périmètre

- Le projet se concentre exclusivement sur **TKI PGP** ; la solution métier **TKI NET** n'entre pas dans le périmètre du stage.
- Aucune rétro-ingénierie du code de TKI PGP n'est réalisée : l'analyse se base uniquement sur la documentation publique et le comportement observable du produit.
- Le développement s'appuie sur des Data Models de test créés spécifiquement pour ce projet, et non sur des données de production.

## Auteurs

Projet réalisé dans le cadre d'un stage de fin d'année (PFA), en binôme.

## Licence

© 2026 — Tous droits réservés.

Ce projet est réalisé dans le cadre d'un stage de fin d'année. Son statut de propriété intellectuelle n'est pas encore définitivement fixé. Aucune licence d'utilisation, de copie, de modification ou de redistribution n'est accordée à ce stade. Le code est visible publiquement à titre de démonstration/portfolio uniquement.
