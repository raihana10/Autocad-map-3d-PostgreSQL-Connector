# Comparaison `schema_test10-01` -> `schema_test10-02`


## Tables ajoutees

Aucune

## Tables supprimees

Aucune

## Colonnes ajoutees


**Table : `TEST_CLASSE_01`**
- `+ TEST_ATTRIBUT_10 (INTEGER(10))`

## Colonnes supprimees

Aucune

## Colonnes modifiees

Aucune

## Relations ajoutees (cles etrangeres)

Aucune

## Relations supprimees (cles etrangeres)

Aucune

## Index ajoutes

- `+ TEST_CLASSE_01_IX2`

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
- `+ {'ID': 63, 'CAPTION': 'Test_Attribut_10', 'DESCRIPTION': None, 'F_CLASS_ID': 8, 'IS_SYSTEM': 0, 'NAME': 'TEST_ATTRIBUT_10', 'UNIT_ID': 0}`

**Table : `TB_RELATIONS`**

_1 ligne(s) ajoutee(s)_
- `+ {'ID': 12, 'ACTIVE': 1, 'CHILD_COLUMN_NAME': 'TEST_ATTRIBUT_10', 'CHILD_TABLE_NAME': 'TEST_CLASSE_01', 'CREATE_CHILD': 0, 'DELETE_CHILD': 'N', 'PARENT_COLUMN_NAME': 'ID', 'PARENT_TABLE_NAME': 'TEST_DOMAINE_10_TBD', 'MERGE_MODE': None, 'SPLIT_MODE': None}`

**Table : `TB_SEQUENCE_EMULATION`**

_1 ligne(s) modifiee(s)_
- Ligne `['SEQUENCE_NAME']=('TB_ATTRIBUTE_S',)` :
  - `NEXT_VALUE` : `63` -> `64`

**Table : `fdo_columns`**

_1 ligne(s) ajoutee(s)_
- `+ {'f_table_name': 'TEST_CLASSE_01', 'f_column_name': 'TEST_ATTRIBUT_10', 'f_column_desc': 'Number', 'fdo_data_type': 7, 'fdo_data_details': 0, 'fdo_data_length': 0, 'fdo_data_precision': 10, 'fdo_data_scale': 0}`
