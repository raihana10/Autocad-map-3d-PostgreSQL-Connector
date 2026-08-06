# Comparaison `schema_test08` -> `schema_test09`


## Tables ajoutees

Aucune

## Tables supprimees

Aucune

## Colonnes ajoutees


**Table : `TEST_CLASSE_01`**
- `+ TEST_ATTRIBUT_09 (INTEGER(10))`

## Colonnes supprimees

Aucune

## Colonnes modifiees

Aucune

## Relations ajoutees (cles etrangeres)

Aucune

## Relations supprimees (cles etrangeres)

Aucune

## Index ajoutes

- `+ TEST_CLASSE_01_IX1`

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


**Table : `TB_ATTRIBUTE`**

_1 ligne(s) ajoutee(s)_
- `+ {'ID': 62, 'CAPTION': 'Test_Attribut_09', 'DESCRIPTION': None, 'F_CLASS_ID': 8, 'IS_SYSTEM': 0, 'NAME': 'TEST_ATTRIBUT_09', 'UNIT_ID': 0}`

**Table : `TB_RELATIONS`**

_1 ligne(s) ajoutee(s)_
- `+ {'ID': 11, 'ACTIVE': 1, 'CHILD_COLUMN_NAME': 'TEST_ATTRIBUT_09', 'CHILD_TABLE_NAME': 'TEST_CLASSE_01', 'CREATE_CHILD': 0, 'DELETE_CHILD': 'N', 'PARENT_COLUMN_NAME': 'FID', 'PARENT_TABLE_NAME': 'TEST_CLASSE_GEO_01', 'MERGE_MODE': None, 'SPLIT_MODE': None}`

**Table : `TB_SEQUENCE_EMULATION`**

_1 ligne(s) modifiee(s)_
- Ligne `['SEQUENCE_NAME']=('TB_ATTRIBUTE_S',)` :
  - `NEXT_VALUE` : `62` -> `63`

**Table : `fdo_columns`**

_1 ligne(s) ajoutee(s)_
- `+ {'f_table_name': 'TEST_CLASSE_01', 'f_column_name': 'TEST_ATTRIBUT_09', 'f_column_desc': 'Number', 'fdo_data_type': 7, 'fdo_data_details': 0, 'fdo_data_length': 0, 'fdo_data_precision': 10, 'fdo_data_scale': 0}`


## Interprétation

La création d'une relation métier génère une définition SQL stockée dans `TB_RELATIONS` contenant la table parente, la table fille et leurs clés. Un INDEX est également créé sur la colonne enfant pour les performances.
