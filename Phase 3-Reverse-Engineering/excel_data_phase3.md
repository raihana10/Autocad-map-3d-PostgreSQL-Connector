| Test | Modification réalisée | Tables modifiées | Colonnes modifiées | Observation | Interprétation | Capture disponible (Oui/Non) |
|---|---|---|---|---|---|---|
| 0 | État initial | Aucune | Aucune | Baseline de référence générée | Structure minimale, présence de tables sytème (TB_...) | Oui |
| 1 | Ajout d'une classe (TEST_CLASSE_01) | TB_DICTIONARY, TB_ATTRIBUTE, fdo_columns | TEST_CLASSE_01 (créée) | Création de la table physique et inscription dans les tables systèmes | Mapping 1-1 entre la classe et une table physique. | Oui |
| 2 | Ajout d'un attribut | TB_ATTRIBUTE, fdo_columns | TEST_ATTRIBUT_01 (créée) | Attribut physique créé dans la table TEST_CLASSE_01 | Chaque attribut est une colonne physique dans la table de sa classe. | Oui |
| 3 | Ajout d'un attribut (Type numérique) | TB_ATTRIBUTE, fdo_columns | TEST_ATTRIBUT_02 (créée) | Création physique (INTEGER(10)) | Respect minutieux du type numérique en SQL. | Oui |
| 4 | Valeur par défaut | TB_ATTRIBUTE, fdo_columns | TEST_ATTRIBUT_03 (créée) | Ajout de l'attribut avec contrainte DEFAULT 0 | Le schéma natif DDL intègre les valeurs par défaut. | Oui |
| 5 | Attribut obligatoire | TB_ATTRIBUTE, fdo_columns | TEST_ATTRIBUT_05 (créée) | Ajout de l'attribut avec contrainte NOT NULL | Les contraintes d'obligation deviennent NOT NULL. | Oui |
| 6 | Longueur d'un champ | N/A | N/A | Test abandonné (redondance) | La configuration de longueur est déjà vérifiée dans le Test 2 (via Varchar2(10)). | Non |
| 7 | Nouvelle classe géométrique | TB_DICTIONARY, TB_ATTRIBUTE, geometry_columns, fdo_columns | TEST_CLASSE_GEO_01 (créée) | Table créée avec colonnes Z, ORIENTATION, GEOM. F_CLASS_TYPE = 'P' | Les tables AutoCAD stockent la géométrie et la lient à geometry_columns. | Oui |
| 8 | Changement du type de géométrie | TB_DICTIONARY, geometry_columns | TEST_CLASS_GEO_02 (créée) | F_CLASS_TYPE = 'L', geometry_type = 2 | Chaque classe fige son type (Ligne = L). | Oui |
| 9 | Relation entre deux classes | TB_RELATIONS | TEST_ATTRIBUT_09 (créée) | Entrée parent/enfant dans TB_RELATIONS et ajout d'un index explicite. | AutoCAD crée manuellement les relations et un index pour les optimiser. | Oui |
| 10 | Ajout de domaine de valeurs | TB_DOMAIN, TB_RELATIONS | TEST_DOMAINE_10_TBD (créée) | Création d'une table catalogue dédiée et enregistrement dans TB_DOMAIN. | Un domaine est matérialisé par sa propre table de valeurs. | Oui |
| 11 | Modification de domaine | TEST_DOMAINE_10_TBD | Aucune | Ligne 'Cuivre' ajoutée à la table de domaine. | Ajout transparent (incrémental) sans impact sur la configuration métier. | Oui |
| 12 | Héritage entre classes | TB_DICTIONARY, TB_ATTRIBUTE, fdo_columns | TEST_CLASSE_FILLE_01 (créée) | La table hérite *physiquement* des attributs du parent. | L'héritage d'Autodesk recopie les colonnes parentes dans la table fille SQL. | Oui |
| 13 | Représentation graphique | N/A | N/A | Test abandonné (Couche de présentation) | L'affichage (couleur/symbole) ne modifie pas le modèle relationnel. | Non |
| 14 | Ajout d'un Label | N/A | N/A | Test abandonné (Couche de présentation) | Idem, cela indique à l'interface client de Map 3D quoi afficher. | Non |
| 15 | Ajout d'un Template | N/A | N/A | Test abandonné (Couche de présentation) | Le template est un assistant de saisie de l'UI. | Non |
| 16 | Renommage d'une classe | TB_DICTIONARY | Aucune | Seule CAPTION est modifiée | Le nom physique de la table reste inchangé, l'UI modifie un label. | Oui |
| 17 | Suppression d'une classe | TB_DICTIONARY, TB_ATTRIBUTE, TB_RELATIONS | TEST_CLASSE_FILLE_01 (supprimée) | Suppression (hard delete) de la table physique et de ses entrées catalogues. | Casse en cascade les objets metadata du système (tables systèmes auto-nettoyées). | Oui |
| 18 | Suppression d'un attribut | TB_ATTRIBUTE, fdo_columns | TEST_ATTRIBUT_01 (supprimée) | Suppression (DROP) physique de la colonne | Vrai suppression sans soft-delete. | Oui |
| 19 | Comparaison auto | N/A | N/A | Les fichiers rapport_*.md générés avec succès | Validation des outils de comparaison. | Oui |
| 20 | Correspondance IA / SQLite | N/A | N/A | Achevé | Modèle parfaitement mappé pour Postgres. | Oui |
