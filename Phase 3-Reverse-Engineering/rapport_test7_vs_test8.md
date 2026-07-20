# Comparaison `schema_test07` -> `schema_test08`


## Tables ajoutees

- `+ TEST_CLASS_GEO_02`

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

- `+ TEST_CLASS_GEO_02_AD_FID`
- `+ TEST_CLASS_GEO_02_AI_FID`
- `+ TEST_CLASS_GEO_02_AU_FID`
- `+ TEST_CLASS_GEO_02_BI_FID`
- `+ TEST_CLASS_GEO_02_BU_FID`

## Triggers supprimes

Aucun

## Vues ajoutes

Aucun

## Vues supprimes

Aucun

## Donnees (dump)


**Table : `TB_ATTRIBUTE`**

_3 ligne(s) ajoutee(s)_
- `+ {'ID': 59, 'CAPTION': 'FID', 'DESCRIPTION': 'FID', 'F_CLASS_ID': 10, 'IS_SYSTEM': 1, 'NAME': 'FID', 'UNIT_ID': 0}`
- `+ {'ID': 60, 'CAPTION': 'Geometry', 'DESCRIPTION': 'Geometry column of the feature class', 'F_CLASS_ID': 10, 'IS_SYSTEM': 1, 'NAME': 'GEOM', 'UNIT_ID': 0}`
- `+ {'ID': 61, 'CAPTION': 'Length of the line', 'DESCRIPTION': 'Length of the line', 'F_CLASS_ID': 10, 'IS_SYSTEM': 1, 'NAME': 'LENGTH', 'UNIT_ID': 1012}`

**Table : `TB_DICTIONARY`**

_1 ligne(s) ajoutee(s)_
- `+ {'F_CLASS_ID': 10, 'ACTIVE': 1, 'CAPTION': 'TEST_CLASS_GEO_02', 'DIMENSION': 2, 'F_CLASS_NAME': 'TEST_CLASS_GEO_02', 'F_CLASS_TYPE': 'L', 'FEATURE_REPRESENTATION': None, 'MAX_X': 'Inf', 'MAX_Y': 'Inf', 'MAX_Z': 'Inf', 'MIN_X': '-Inf', 'MIN_Y': '-Inf', 'MIN_Z': '-Inf', 'MODEL_F_CLASS_ID': None, 'PARENT_F_CLASS_ID': 1, 'READ_ONLY': 0, 'SPATIAL_RELATE': 'AnyInteract', 'SRID': 0, 'TABLE_DOES_NOT_EXIST': 0, 'TOLERANCE': 0.0005, 'TOPIC_ID': 1, 'USER_DEFINED_ELEVATION': 0, 'USER_DEFINED_ORIENTATION': 0, 'VERSION_ENABLED': 0}`

**Table : `TB_RULE_BASE`**

_11 ligne(s) ajoutee(s)_
- `+ {'ID': 73, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 0, 'BD': 0, 'BI': 0, 'BU': 1, 'F_CLASS_ID': 10, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 39, 'RULE_DEF_ID': 8035}`
- `+ {'ID': 76, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 0, 'BD': 0, 'BI': 0, 'BU': 1, 'F_CLASS_ID': 10, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 75, 'RULE_DEF_ID': 8104}`
- `+ {'ID': 79, 'ACTIVE': 1, 'AD': 1, 'AI': 0, 'AU': 0, 'BD': 0, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 10, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 130, 'RULE_DEF_ID': 8107}`
- `+ {'ID': 69, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 0, 'BD': 1, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 10, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 50, 'RULE_DEF_ID': 10}`
- `+ {'ID': 75, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 0, 'BD': 0, 'BI': 1, 'BU': 1, 'F_CLASS_ID': 10, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 39, 'RULE_DEF_ID': 8042}`
- `+ {'ID': 72, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 0, 'BD': 0, 'BI': 1, 'BU': 0, 'F_CLASS_ID': 10, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 35, 'RULE_DEF_ID': 8034}`
- `+ {'ID': 78, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 0, 'BD': 1, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 10, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 75, 'RULE_DEF_ID': 8106}`
- `+ {'ID': 71, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 0, 'BD': 0, 'BI': 1, 'BU': 1, 'F_CLASS_ID': 10, 'PARAMETER_1': '3', 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 39, 'RULE_DEF_ID': 25}`
- `+ {'ID': 74, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 0, 'BD': 1, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 10, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 99, 'RULE_DEF_ID': 8036}`
- `+ {'ID': 70, 'ACTIVE': 1, 'AD': 1, 'AI': 0, 'AU': 0, 'BD': 0, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 10, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 130, 'RULE_DEF_ID': 11}`
- `+ {'ID': 77, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 1, 'BD': 0, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 10, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 150, 'RULE_DEF_ID': 8105}`

**Table : `TB_SEQUENCE_EMULATION`**

_3 ligne(s) modifiee(s)_
- Ligne `['SEQUENCE_NAME']=('TB_DICTIONARY_S',)` :
  - `NEXT_VALUE` : `10` -> `11`
- Ligne `['SEQUENCE_NAME']=('TB_RULE_BASE_S',)` :
  - `NEXT_VALUE` : `69` -> `80`
- Ligne `['SEQUENCE_NAME']=('TB_ATTRIBUTE_S',)` :
  - `NEXT_VALUE` : `59` -> `62`

**Table : `fdo_columns`**

_2 ligne(s) ajoutee(s)_
- `+ {'f_table_name': 'TEST_CLASS_GEO_02', 'f_column_name': 'LENGTH', 'f_column_desc': 'Number', 'fdo_data_type': 3, 'fdo_data_details': 0, 'fdo_data_length': 0, 'fdo_data_precision': 20, 'fdo_data_scale': 8}`
- `+ {'f_table_name': 'TEST_CLASS_GEO_02', 'f_column_name': 'FID', 'f_column_desc': 'Number', 'fdo_data_type': 7, 'fdo_data_details': 2, 'fdo_data_length': 0, 'fdo_data_precision': 18, 'fdo_data_scale': 0}`

**Table : `geometry_columns`**

_1 ligne(s) ajoutee(s)_
- `+ {'f_table_name': 'TEST_CLASS_GEO_02', 'f_geometry_column': 'GEOM', 'geometry_type': 2, 'geometry_dettype': 2578, 'coord_dimension': 0, 'srid': 0, 'geometry_format': 'FGF'}`
