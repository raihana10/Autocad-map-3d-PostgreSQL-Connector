# Alternative libre à TKI PGP — Industry Model Autodesk vers PostgreSQL/PostGIS

> Projet de fin d'année (stage PFA) visant à concevoir une alternative open-source au connecteur commercial **TKI PGP**, permettant d'utiliser **PostgreSQL/PostGIS** comme moteur de stockage pour un **Industry Model** (Fachschale) Autodesk, en lieu et place d'Oracle ou de Microsoft SQL Server.

---

**Version Française** | [ English Version (Version Anglaise) ](README.md)

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
                                   [Script Python]
                                           │
                                           ▼
                                 PostgreSQL + PostGIS
                                           │
                                           ▼
                                  AutoCAD Map 3D
                            [Connecteur FDO PostgreSQL natif]
```

## Structure du dépôt

```
.
├── Phase 1-FDO-Provider-Analysis/
│   ├── 01-autodesk-architecture.md      # Phase 1 — architecture Autodesk observée (FR)
│   └── 01-autodesk-architecture_EN.md   # Phase 1 — architecture Autodesk observée (EN)
├── Phase 2-PostGIS-Direct-Connection/
│   ├── 02-postgis-postgresql.md         # Phase 2 — PostgreSQL/PostGIS et connecteur FDO (FR)
│   └── 02-postgis-postgresql_EN.md      # Phase 2 — PostgreSQL/PostGIS et connecteur FDO (EN)
├── Phase 3-SQLite-Reverse-Engineering/
│   ├── 03-data-model-analyse.md         # Phase 3 — Analyse et reverse engineering (FR)
│   ├── 03-data-model-analyse_EN.md      # Phase 3 — Analyse et reverse engineering (EN)
│   ├── compare_sqlite.py                # Script de comparaison automatisée de deux exports SQLite
│   ├── rapport_test1_vs_test2.md        # Exemple de rapport de comparaison
│   ├── Test0/ ... Test18/               # Campagne de tests différentiels (schéma + dump SQL par test)
│   └── PFA-Phase 3.xlsx                 # Support de travail / document de synthèse
├── Phase 4-TKI-PGP-Role-Analysis/
│   ├── 04-role-tki-pgp.md               # Phase 4 — Rôle de TKI PGP dans l'architecture Autodesk (FR)
│   └── 04-role-tki-pgp_EN.md            # Phase 4 — Rôle de TKI PGP dans l'architecture Autodesk (EN)
├── Phase 5-Target-Architecture/
│   ├── 05-architecture-cible.md         # Phase 5 — Architecture cible & solution alternative (FR)
│   └── 05-architecture-cible_EN.md      # Phase 5 — Architecture cible & solution alternative (EN)
├── Phase 6-Implementation-Testing/
│   ├── scripts/
│   │   ├── convert_autodesk_to_postgis.py   # Convertisseur automatisé SQLite vers DDL PostgreSQL
│   │   └── watch_and_sync.py                # Service de surveillance et synchronisation en temps réel
│   ├── tests/
│   │   ├── conftest.py                      # Fixtures Pytest et configuration partagée
│   │   ├── test_converter.py                # Tests unitaires du convertisseur DDL
│   │   ├── test_inheritance.py              # Tests unitaires pour l'héritage de tables
│   │   └── test_watcher.py                  # Tests unitaires du service de surveillance
│   └── requirements-dev.txt                 # Dépendances de développement et de test
├── README_FR.md                         # README principal (Français)
└── README.md                            # README principal (Anglais)
```

## Technologies utilisées

- **AutoCAD Map 3D** / **Autodesk Infrastructure Administrator** — environnement de référence
- **PostgreSQL** / **PostGIS** — base de données cible
- **SQLite** — format de stockage intermédiaire du Data Model, analysé en Phase 3
- **Python** — scripts d'analyse, de comparaison et de génération DDL (`compare_sqlite.py`, `convert_autodesk_to_postgis.py`)
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
