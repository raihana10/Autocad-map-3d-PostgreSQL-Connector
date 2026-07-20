# Comparaison `schema_test05` -> `schema_test07`


## Tables ajoutees

- `+ TEST_CLASSE_GEO_01`

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

- `+ TEST_CLASSE_GEO_01_AD_FID`
- `+ TEST_CLASSE_GEO_01_AI_FID`
- `+ TEST_CLASSE_GEO_01_AU_FID`
- `+ TEST_CLASSE_GEO_01_BI_FID`
- `+ TEST_CLASSE_GEO_01_BU_FID`

## Triggers supprimes

Aucun

## Vues ajoutes

Aucun

## Vues supprimes

Aucun

## Donnees (dump)


**Table : `TB_ATTRIBUTE`**

_5 ligne(s) ajoutee(s)_
- `+ {'ID': 57, 'CAPTION': 'Z', 'DESCRIPTION': 'Z', 'F_CLASS_ID': 9, 'IS_SYSTEM': 1, 'NAME': 'Z', 'UNIT_ID': 0}`
- `+ {'ID': 56, 'CAPTION': 'Orientation', 'DESCRIPTION': 'Orientation', 'F_CLASS_ID': 9, 'IS_SYSTEM': 1, 'NAME': 'ORIENTATION', 'UNIT_ID': 3001}`
- `+ {'ID': 55, 'CAPTION': 'Geometry', 'DESCRIPTION': 'Geometry column of the feature class', 'F_CLASS_ID': 9, 'IS_SYSTEM': 1, 'NAME': 'GEOM', 'UNIT_ID': 0}`
- `+ {'ID': 58, 'CAPTION': 'Quality of the point', 'DESCRIPTION': 'Quality of the point', 'F_CLASS_ID': 9, 'IS_SYSTEM': 1, 'NAME': 'QUALITY', 'UNIT_ID': 0}`
- `+ {'ID': 54, 'CAPTION': 'FID', 'DESCRIPTION': 'FID', 'F_CLASS_ID': 9, 'IS_SYSTEM': 1, 'NAME': 'FID', 'UNIT_ID': 0}`

**Table : `TB_DICTIONARY`**

_1 ligne(s) ajoutee(s)_
- `+ {'F_CLASS_ID': 9, 'ACTIVE': 1, 'CAPTION': 'TEST_CLASSE_GEO_01', 'DIMENSION': 2, 'F_CLASS_NAME': 'TEST_CLASSE_GEO_01', 'F_CLASS_TYPE': 'P', 'FEATURE_REPRESENTATION': None, 'MAX_X': 'Inf', 'MAX_Y': 'Inf', 'MAX_Z': 'Inf', 'MIN_X': '-Inf', 'MIN_Y': '-Inf', 'MIN_Z': '-Inf', 'MODEL_F_CLASS_ID': None, 'PARENT_F_CLASS_ID': 1, 'READ_ONLY': 0, 'SPATIAL_RELATE': 'AnyInteract', 'SRID': 0, 'TABLE_DOES_NOT_EXIST': 0, 'TOLERANCE': 0.0005, 'TOPIC_ID': 1, 'USER_DEFINED_ELEVATION': 0, 'USER_DEFINED_ORIENTATION': 0, 'VERSION_ENABLED': 0}`

**Table : `TB_RULE_BASE`**

_7 ligne(s) ajoutee(s)_
- `+ {'ID': 63, 'ACTIVE': 1, 'AD': 1, 'AI': 0, 'AU': 0, 'BD': 0, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 9, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 130, 'RULE_DEF_ID': 11}`
- `+ {'ID': 66, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 1, 'BD': 0, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 9, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 150, 'RULE_DEF_ID': 8105}`
- `+ {'ID': 62, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 0, 'BD': 1, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 9, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 50, 'RULE_DEF_ID': 10}`
- `+ {'ID': 68, 'ACTIVE': 1, 'AD': 1, 'AI': 0, 'AU': 0, 'BD': 0, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 9, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 130, 'RULE_DEF_ID': 8107}`
- `+ {'ID': 65, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 0, 'BD': 0, 'BI': 0, 'BU': 1, 'F_CLASS_ID': 9, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 75, 'RULE_DEF_ID': 8104}`
- `+ {'ID': 64, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 0, 'BD': 0, 'BI': 1, 'BU': 1, 'F_CLASS_ID': 9, 'PARAMETER_1': '3', 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 39, 'RULE_DEF_ID': 25}`
- `+ {'ID': 67, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 0, 'BD': 1, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 9, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 75, 'RULE_DEF_ID': 8106}`

**Table : `TB_SEQUENCE_EMULATION`**

_4 ligne(s) modifiee(s)_
- Ligne `['SEQUENCE_NAME']=('TB_RULE_BASE_S',)` :
  - `NEXT_VALUE` : `62` -> `69`
- Ligne `['SEQUENCE_NAME']=('TB_DICTIONARY_S',)` :
  - `NEXT_VALUE` : `9` -> `10`
- Ligne `['SEQUENCE_NAME']=('TB_SETTINGS_S1',)` :
  - `NEXT_VALUE` : `7` -> `10`
- Ligne `['SEQUENCE_NAME']=('TB_ATTRIBUTE_S',)` :
  - `NEXT_VALUE` : `54` -> `59`

**Table : `TB_SETTINGS`**

_3 ligne(s) ajoutee(s)_
- `+ {'ID': 7, 'ITEMKEY': 'LAST_DIMENSION', 'ITEMTHEMA': 'TOPOBASE', 'ITEMVALUE': '2', 'MACHINE_ID': None, 'USER_ID': 'ALL'}`
- `+ {'ID': 8, 'ITEMKEY': 'LAST_TOLERANCE', 'ITEMTHEMA': 'TOPOBASE', 'ITEMVALUE': '0.0005', 'MACHINE_ID': None, 'USER_ID': 'ALL'}`
- `+ {'ID': 9, 'ITEMKEY': 'LAST_SRID', 'ITEMTHEMA': 'TOPOBASE', 'ITEMVALUE': '0', 'MACHINE_ID': None, 'USER_ID': 'ALL'}`

**Table : `fdo_columns`**

_4 ligne(s) ajoutee(s)_
- `+ {'f_table_name': 'TEST_CLASSE_GEO_01', 'f_column_name': 'Z', 'f_column_desc': 'Number', 'fdo_data_type': 3, 'fdo_data_details': 0, 'fdo_data_length': 0, 'fdo_data_precision': 20, 'fdo_data_scale': 8}`
- `+ {'f_table_name': 'TEST_CLASSE_GEO_01', 'f_column_name': 'FID', 'f_column_desc': 'Number', 'fdo_data_type': 7, 'fdo_data_details': 2, 'fdo_data_length': 0, 'fdo_data_precision': 18, 'fdo_data_scale': 0}`
- `+ {'f_table_name': 'TEST_CLASSE_GEO_01', 'f_column_name': 'QUALITY', 'f_column_desc': 'Number', 'fdo_data_type': 7, 'fdo_data_details': 0, 'fdo_data_length': 0, 'fdo_data_precision': 10, 'fdo_data_scale': 0}`
- `+ {'f_table_name': 'TEST_CLASSE_GEO_01', 'f_column_name': 'ORIENTATION', 'f_column_desc': 'Number', 'fdo_data_type': 3, 'fdo_data_details': 0, 'fdo_data_length': 0, 'fdo_data_precision': 6, 'fdo_data_scale': 3}`

**Table : `geometry_columns`**

_1 ligne(s) ajoutee(s)_
- `+ {'f_table_name': 'TEST_CLASSE_GEO_01', 'f_geometry_column': 'GEOM', 'geometry_type': 1, 'geometry_dettype': 1, 'coord_dimension': 0, 'srid': 0, 'geometry_format': 'FGF'}`
