# Comparaison `schema_test00` -> `schema_test01`


## Tables ajoutees

- `+ TEST_CLASSE_01`

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

- `+ TEST_CLASSE_01_AD_FID`
- `+ TEST_CLASSE_01_AI_FID`
- `+ TEST_CLASSE_01_AU_FID`
- `+ TEST_CLASSE_01_BI_FID`
- `+ TEST_CLASSE_01_BU_FID`

## Triggers supprimes

Aucun

## Vues ajoutes

Aucun

## Vues supprimes

Aucun

## Donnees (dump)


**Table : `TB_ATTRIBUTE`**

_1 ligne(s) ajoutee(s)_
- `+ {'ID': 49, 'CAPTION': 'FID', 'DESCRIPTION': 'FID', 'F_CLASS_ID': 8, 'IS_SYSTEM': 1, 'NAME': 'FID', 'UNIT_ID': 0}`

**Table : `TB_DICTIONARY`**

_1 ligne(s) ajoutee(s)_
- `+ {'F_CLASS_ID': 8, 'ACTIVE': 1, 'CAPTION': 'Test Classe 01', 'DIMENSION': 2, 'F_CLASS_NAME': 'TEST_CLASSE_01', 'F_CLASS_TYPE': 'T', 'FEATURE_REPRESENTATION': None, 'MAX_X': 'Inf', 'MAX_Y': 'Inf', 'MAX_Z': 'Inf', 'MIN_X': '-Inf', 'MIN_Y': '-Inf', 'MIN_Z': '-Inf', 'MODEL_F_CLASS_ID': None, 'PARENT_F_CLASS_ID': 1, 'READ_ONLY': 0, 'SPATIAL_RELATE': 'anyinteract', 'SRID': 25832, 'TABLE_DOES_NOT_EXIST': 0, 'TOLERANCE': 0.0005, 'TOPIC_ID': 1, 'USER_DEFINED_ELEVATION': 0, 'USER_DEFINED_ORIENTATION': 0, 'VERSION_ENABLED': 0}`

**Table : `TB_RULE_BASE`**

_6 ligne(s) ajoutee(s)_
- `+ {'ID': 57, 'ACTIVE': 1, 'AD': 1, 'AI': 0, 'AU': 0, 'BD': 0, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 8, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 130, 'RULE_DEF_ID': 11}`
- `+ {'ID': 60, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 0, 'BD': 1, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 8, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 75, 'RULE_DEF_ID': 8106}`
- `+ {'ID': 56, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 0, 'BD': 1, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 8, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 50, 'RULE_DEF_ID': 10}`
- `+ {'ID': 59, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 1, 'BD': 0, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 8, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 150, 'RULE_DEF_ID': 8105}`
- `+ {'ID': 61, 'ACTIVE': 1, 'AD': 1, 'AI': 0, 'AU': 0, 'BD': 0, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 8, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 130, 'RULE_DEF_ID': 8107}`
- `+ {'ID': 58, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 0, 'BD': 0, 'BI': 0, 'BU': 1, 'F_CLASS_ID': 8, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 75, 'RULE_DEF_ID': 8104}`

**Table : `TB_SEQUENCE_EMULATION`**

_4 ligne(s) modifiee(s)_
- Ligne `['SEQUENCE_NAME']=('TB_ATTRIBUTE_S',)` :
  - `NEXT_VALUE` : `49` -> `50`
- Ligne `['SEQUENCE_NAME']=('TB_RULE_BASE_S',)` :
  - `NEXT_VALUE` : `56` -> `62`
- Ligne `['SEQUENCE_NAME']=('TB_SETTINGS_S1',)` :
  - `NEXT_VALUE` : `6` -> `7`
- Ligne `['SEQUENCE_NAME']=('TB_DICTIONARY_S',)` :
  - `NEXT_VALUE` : `8` -> `9`

**Table : `TB_SETTINGS`**

_1 ligne(s) ajoutee(s)_
- `+ {'ID': 6, 'ITEMKEY': 'LAST_SPATIALMASK', 'ITEMTHEMA': 'TOPOBASE', 'ITEMVALUE': 'anyinteract', 'MACHINE_ID': None, 'USER_ID': 'ALL'}`

**Table : `fdo_columns`**

_1 ligne(s) ajoutee(s)_
- `+ {'f_table_name': 'TEST_CLASSE_01', 'f_column_name': 'FID', 'f_column_desc': 'Number', 'fdo_data_type': 7, 'fdo_data_details': 2, 'fdo_data_length': 0, 'fdo_data_precision': 18, 'fdo_data_scale': 0}`
