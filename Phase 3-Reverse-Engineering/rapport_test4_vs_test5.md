# Comparaison `schema_test04` -> `schema_test05`


## Tables ajoutees

Aucune

## Tables supprimees

Aucune

## Colonnes ajoutees


**Table : `TEST_CLASSE_01`**
- `+ TEST_ATTRIBUT_05 (VARCHAR2(10), NOT NULL)`

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


**Table : `TB_ATTRIBUTE`**

_1 ligne(s) ajoutee(s)_
- `+ {'ID': 53, 'CAPTION': 'Test_Attribut_05', 'DESCRIPTION': None, 'F_CLASS_ID': 8, 'IS_SYSTEM': 0, 'NAME': 'TEST_ATTRIBUT_05', 'UNIT_ID': 0}`

**Table : `TB_SEQUENCE_EMULATION`**

_1 ligne(s) modifiee(s)_
- Ligne `['SEQUENCE_NAME']=('TB_ATTRIBUTE_S',)` :
  - `NEXT_VALUE` : `53` -> `54`

**Table : `fdo_columns`**

_1 ligne(s) ajoutee(s)_
- `+ {'f_table_name': 'TEST_CLASSE_01', 'f_column_name': 'TEST_ATTRIBUT_05', 'f_column_desc': 'Varchar2', 'fdo_data_type': 9, 'fdo_data_details': 0, 'fdo_data_length': 10, 'fdo_data_precision': 0, 'fdo_data_scale': 0}`
