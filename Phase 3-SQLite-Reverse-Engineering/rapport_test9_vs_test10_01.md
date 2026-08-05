# Comparaison `schema_test09` -> `schema_test10-01`


## Tables ajoutees

- `+ TEST_DOMAINE_10_TBD`

## Tables supprimees

Aucune

## Colonnes ajoutees

Aucune

## Colonnes supprimees

Aucune

## Colonnes modifiees

Aucune

## Relations ajoutees (cles etrangeres)

Aucune

## Relations supprimees (cles etrangeres)

Aucune

## Index ajoutes

Aucun

## Index supprimes

Aucun

## Triggers ajoutes

Aucun

## Triggers supprimes

Aucun

## Vues ajoutes

Aucun

## Vues supprimes

Aucun

## Donnees (dump)


**Table : `TB_DOMAIN`**

_1 ligne(s) ajoutee(s)_
- `+ {'ID': 3, 'ACTIVE': 1, 'CAPTION': 'TEST_DOMAINE_10', 'READ_ONLY': 0, 'TABLE_DOES_NOT_EXIST': 0, 'TABLE_NAME': 'TEST_DOMAINE_10_TBD'}`

**Table : `TEST_DOMAINE_10_TBD`**

_3 ligne(s) ajoutee(s)_
- `+ {'ID': 1, 'SHORT_VALUE': '', 'VALUE': 'Acier', 'DATE_OF_CREATION': None, 'DESIGNER': None, 'COMMENTARY': '', 'ACTIVE': 1, 'PRIORITY': None}`
- `+ {'ID': 2, 'SHORT_VALUE': '', 'VALUE': 'PVC', 'DATE_OF_CREATION': None, 'DESIGNER': None, 'COMMENTARY': '', 'ACTIVE': 1, 'PRIORITY': None}`
- `+ {'ID': 3, 'SHORT_VALUE': '', 'VALUE': 'Fonte', 'DATE_OF_CREATION': None, 'DESIGNER': None, 'COMMENTARY': '', 'ACTIVE': 1, 'PRIORITY': None}`


## Interprétation

Un domaine est matérialisé par sa propre table de valeurs (ex: `TEST_DOMAINE_10_TBD`) et son enregistrement dans la table du catalogue des domaines `TB_DOMAIN`.
