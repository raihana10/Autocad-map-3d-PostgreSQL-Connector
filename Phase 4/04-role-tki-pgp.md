# Phase 4 — Rôle de TKI PGP dans l'architecture Autodesk

> Légende (identique à celle du README du projet) :
> - **[DOCUMENTÉ]** = information confirmée par une source officielle Autodesk ou TKI.
> - **[HYPOTHÈSE]** = déduction raisonnable, non confirmée par une source officielle.
> - **[À VÉRIFIER]** = information manquante ou nécessitant un test / une confirmation auprès de l'encadrante ou du support Autodesk.
>
> Les sources sont numérotées `[n]` et listées en Annexe, en fin de document.

---

## 1. Présentation de TKI PGP

**TKI PGP** signifie **PostgreSQL Provider**. C'est un logiciel de connectivité développé par l'entreprise **TKI Software / TKI Chemnitz**, destiné à permettre l'utilisation des **Autodesk Industry Models (Fachschalen)** avec une base de données **PostgreSQL** plutôt qu'avec Oracle ou SQL Server. La documentation officielle le présente comme le **« connecteur effectif »** entre AutoCAD Map 3D et PostgreSQL **[DOCUMENTÉ] [1]**.

Sur le plan technique, PGP est donc :

- un **provider** au sens fonctionnel, c'est-à-dire un composant qui permet à une application cliente Autodesk de travailler avec PostgreSQL selon la logique des Fachschalen **[DOCUMENTÉ] [1]** ;
- un **connecteur applicatif**, avec des fonctions d'administration et d'échange de données, et non un simple driver de base de données **[DOCUMENTÉ] [3]** ;
- un produit **commercial et versionné**, nécessitant une licence activée sur un serveur de licences réseau, avec une compatibilité stricte de version vis-à-vis d'AutoCAD Map 3D **[DOCUMENTÉ] [8]**.

Le produit est édité par **TKI**, présenté selon les sites et portails d'aide officiels tantôt comme **TKI Software**, tantôt comme **TKI Chemnitz** **[DOCUMENTÉ] [5]**. Le centre d'aide TKI comporte une section dédiée à PGP, ce qui confirme qu'il s'agit d'un produit officiel de la société et non d'un plugin communautaire **[DOCUMENTÉ] [7]**.

Sa fonction générale est de permettre à des Fachschalen Autodesk d'être exploitées avec PostgreSQL au lieu des SGBD traditionnellement supportés dans l'écosystème Autodesk (Oracle, SQL Server) **[DOCUMENTÉ] [4]**. La documentation indique qu'il prend en charge :

- les fonctionnalités de l'**Infrastructure Administrator** **[DOCUMENTÉ] [1]** ;
- l'**import/export de dumps PostgreSQL** **[DOCUMENTÉ] [6]** ;
- le **SQL sheet** de Map 3D **[DOCUMENTÉ] [3]**.

**Date et origine** : aucune année de création n'est explicitement indiquée dans les sources publiques consultées **[À VÉRIFIER]**. Le produit existe au moins depuis son apparition dans le centre d'aide TKI et sur les pages produits officielles, régulièrement mises à jour **[DOCUMENTÉ] [4]**.

---

## 2. Analyse fonctionnelle dans l'architecture Autodesk

TKI PGP s'insère dans l'architecture Autodesk comme une **couche de liaison spécialisée** entre les Autodesk Industry Models / Fachschalen et une base de données PostgreSQL. Il ne se limite pas à ouvrir une connexion base de données : il adapte le fonctionnement du modèle Autodesk à l'environnement PostgreSQL **[DOCUMENTÉ] [2]**.

Dans cette architecture, PGP joue un rôle intermédiaire entre trois niveaux :

1. **L'application Autodesk** — AutoCAD Map 3D et l'Infrastructure Administrator.
2. **La logique métier Autodesk** — les Fachschalen, leurs objets, attributs et workflows d'administration.
3. **Le SGBD PostgreSQL** — qui stocke les données et assure leur persistance.

PGP fait correspondre les attentes du monde Autodesk aux capacités de PostgreSQL **[DOCUMENTÉ] [1]**.

**Prise en charge de l'Infrastructure Administrator.** PGP intervient dans les opérations de gestion des Fachschalen (création, administration, maintenance, exploitation des structures de données), pas uniquement dans le transport des données **[DOCUMENTÉ] [2]**.

**Import/export de dumps PostgreSQL.** Ce mécanisme garantit sauvegarde, restauration et échange de données. Il place PGP comme un outil qui accompagne le cycle de vie des bases projet, utile en migration, duplication d'environnement ou transfert entre serveurs **[DOCUMENTÉ] [6]**.

**Support du SQL sheet.** PGP s'intègre dans les mécanismes de consultation déjà utilisés dans Autodesk : l'utilisateur conserve ses habitudes de travail dans Map 3D tout en s'appuyant sur PostgreSQL comme moteur de stockage **[DOCUMENTÉ] [1]**.

**Couche d'abstraction technique.** PGP permet de maintenir une expérience fonctionnelle proche des environnements Autodesk classiques tout en utilisant PostgreSQL/PostGIS, sans les contraintes de licence d'Oracle ou SQL Server **[DOCUMENTÉ] [2]**.

**Contrainte de spécialisation.** PGP est un produit commercial et versionné, avec licence serveur et compatibilité stricte de version avec AutoCAD Map 3D — ce n'est pas un connecteur générique réutilisable dans n'importe quel contexte **[DOCUMENTÉ] [8]**.

### Synthèse fonctionnelle

PGP peut être compris comme un outil qui :

- relie les Fachschalen Autodesk à PostgreSQL **[DOCUMENTÉ] [1]** ;
- conserve les workflows d'administration déjà utilisés dans l'environnement Autodesk **[DOCUMENTÉ] [2]** ;
- facilite l'échange de données via les dumps **[DOCUMENTÉ] [6]** ;
- permet l'exploitation opérationnelle via le SQL sheet **[DOCUMENTÉ] [1]** ;
- réduit la rupture d'usage lors du passage vers PostgreSQL **[DOCUMENTÉ] [1]**.

Cette position en fait un **pivot fonctionnel** : PGP ne remplace ni Autodesk ni PostgreSQL, il rend les deux compatibles dans un cadre métier précis **[DOCUMENTÉ] [1]**.

---

## 3. Comparaison Oracle / SQL Server / TKI PGP

Cette comparaison reste factuelle et documentaire : elle ne préjuge pas encore de la solution alternative, qui fait l'objet de la Phase 5.

| Critère | Oracle (natif) | SQL Server (natif) | TKI PGP (PostgreSQL) |
|---|---|---|---|
| Support officiel Autodesk Industry Model « base de données » | Oui **[DOCUMENTÉ]** | Oui **[DOCUMENTÉ]** | Non natif — via connecteur tiers **[DOCUMENTÉ] [1]** |
| Éditeur | Oracle Corporation | Microsoft | TKI Software / TKI Chemnitz **[DOCUMENTÉ] [5]** |
| Modèle de licence | Payant (licence Oracle) | Payant (licence SQL Server) | Payant — licence PGP activée sur serveur, **en plus** d'une licence PostgreSQL elle-même libre **[DOCUMENTÉ] [8]** |
| Intégration Infrastructure Administrator | Native | Native | Reprend les fonctionnalités de l'Infrastructure Administrator **[DOCUMENTÉ] [1]** |
| Import/export | Outils Oracle natifs | Outils SQL Server natifs | Import/export de dumps PostgreSQL pris en charge par PGP **[DOCUMENTÉ] [6]** |
| SQL sheet Map 3D | Supporté nativement | Supporté nativement | Supporté via PGP **[DOCUMENTÉ] [3]** |
| Coût total (licences SGBD + connecteur) | Élevé (licence SGBD) | Élevé (licence SGBD) | Licence PGP + PostgreSQL/PostGIS gratuits — argument économique mis en avant par TKI **[DOCUMENTÉ] [2]** |
| Dépendance à un éditeur tiers | Non | Non | Oui — dépendance à TKI pour le connecteur **[DOCUMENTÉ] [8]** |
| Mécanisme interne exact de correspondance schéma ↔ Industry Model | Documenté par Autodesk | Documenté par Autodesk | Non documenté publiquement **[À VÉRIFIER]** |

---

## 4. Tableau récapitulatif — Documenté / Hypothèse / À vérifier

| # | Élément | Statut | Source / Remarque |
|---|---|---|---|
| 1 | PGP est décrit comme le « connecteur effectif » entre AutoCAD Map 3D et PostgreSQL | **[DOCUMENTÉ]** | [1] |
| 2 | PGP prend en charge les fonctionnalités de l'Infrastructure Administrator | **[DOCUMENTÉ]** | [1] [2] |
| 3 | PGP gère l'import/export de dumps PostgreSQL | **[DOCUMENTÉ]** | [6] |
| 4 | PGP supporte le SQL sheet de Map 3D | **[DOCUMENTÉ]** | [1] [3] |
| 5 | PGP nécessite une licence activée sur un serveur de licences réseau | **[DOCUMENTÉ]** | [8] |
| 6 | PGP est compatible uniquement avec certaines versions précises d'AutoCAD Map 3D | **[DOCUMENTÉ]** | [7] [8] |
| 7 | L'éditeur est présenté selon les cas comme TKI Software ou TKI Chemnitz | **[DOCUMENTÉ]** | [3] [4] [5] |
| 8 | L'argument économique (éviter les coûts Oracle/SQL Server) est mis en avant par TKI | **[DOCUMENTÉ]** | [2] |
| 9 | TKI PGP est distinct de TKI NET (solution métier FTTx complète) | **[DOCUMENTÉ]** | Cf. README du projet, §1.3 |
| 10 | Date de création / première version de PGP | **[À VÉRIFIER]** | Non trouvée dans les sources publiques consultées |
| 11 | PGP crée-t-il un schéma PostgreSQL entièrement nouveau à partir du Data Model, ou reproduit-il une structure Oracle/SQL Server existante ? | **[À VÉRIFIER]** | Question ouverte n°2 du README ; aucune source ne détaille le mécanisme interne |
| 12 | PGP reproduit-il un mécanisme de verrouillage / check-out / check-in multi-utilisateur ? | **[À VÉRIFIER]** | Non documenté dans les pages consultées |
| 13 | PGP s'appuie-t-il sur le connecteur FDO PostgreSQL déjà natif à Map 3D, ou implémente-t-il sa propre couche d'accès ? | **[HYPOTHÈSE]** | Probable au vu de l'écosystème Autodesk, mais non confirmé par une source officielle |
| 14 | Le prix / modèle tarifaire exact de la licence PGP | **[À VÉRIFIER]** | Non public sur les pages consultées |
| 15 | PGP gère-t-il les règles métier et les formulaires (Formulaire-Designer), ou uniquement le stockage/géométries ? | **[À VÉRIFIER]** | Recoupe la question ouverte n°7 du README |

---

## 5. Questions ouvertes issues de cette analyse

Ces points restent en suspens à l'issue de la Phase 4 et complètent la section 7 du README :

1. **Mécanisme de génération du schéma** — PGP crée-t-il le schéma PostgreSQL à partir du Data Model, ou réplique-t-il une structure Oracle/SQL Server préexistante ? C'est probablement la question la plus structurante pour la Phase 5, car elle détermine si notre solution doit **générer** un schéma ou **traduire** un schéma existant.
2. **Verrouillage multi-utilisateur** — PGP reproduit-il un mécanisme de check-out/check-in analogue à celui d'Oracle/SQL Server ?
3. **Réutilisation du connecteur FDO PostgreSQL natif** — PGP s'appuie-t-il dessus, ou le contourne-t-il entièrement ?
4. **Périmètre fonctionnel réel** — règles métier et formulaires sont-ils couverts par PGP, ou seulement le stockage des objets et géométries ?

Ces questions ne sont **pas** traitées ici : elles sont transmises telles quelles à la Phase 5 pour orienter les choix d'architecture, et pourront si besoin faire l'objet d'une clarification avec l'encadrante ou d'un test si une licence d'essai TKI PGP est obtenue.

---

## 6. Pistes pour la Phase 5

Cette analyse de TKI PGP met en évidence quatre fonctions-clés que la solution alternative devra reproduire à un niveau équivalent : génération/synchronisation du schéma PostgreSQL/PostGIS, intégration aux workflows de l'Infrastructure Administrator, import/export de données, et accès en lecture/écriture depuis Map 3D (SQL sheet ou équivalent). La conception détaillée de cette solution — choix d'architecture, technologies, spécification fonctionnelle complète — fait l'objet du document `05-architecture-cible.md`, et n'est volontairement pas anticipée ici.

---

## Annexe — Sources consultées

| Réf. | Description | URL |
|---|---|---|
| [1] | TKI Help Center — Introduction PostgreSQL Provider (EN) | https://help.tki-chemnitz.de/hc/en-gb/articles/360015894560-Introduction-PostgreSQL-provider |
| [2] | TKI Help Center — Einführung PostgreSQL Provider (DE) | https://help.tki-chemnitz.de/hc/de/articles/360015894560-Einführung-PostgreSQL-Provider |
| [3] | TKI Chemnitz — Page produit PGP (EN) | https://www.tki-chemnitz.com/software/products/pgp.html |
| [4] | TKI Chemnitz — Page produit PGP (DE) | https://www.tki-chemnitz.de/de/software/produkte/pgp.html |
| [5] | TKI Net — Page produit PGP | https://www.tki-net.com/products/pgp.html |
| [6] | TKI Help Center — Import/Export de dumps PostgreSQL | https://help.tki-chemnitz.de/hc/en-gb/articles/360015674100-Importing-and-Exporting-PostgreSQL-database-dump |
| [7] | TKI Help Center — Section PostgreSQL Provider (PGP) | https://help.tki-chemnitz.de/hc/en-gb/sections/360004497540-PostgreSQL-Provider-PGP |
| [8] | TKI Help Center — General Information about TKI Licensing | https://help.tki-chemnitz.de/hc/en-gb/articles/360015914979-General-Information-about-TKI-Licensing |
