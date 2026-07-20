# Comparaison `schema_test11` -> `schema_test12`


## Tables ajoutees

- `+ TEST_CLASSE_FILLE_01`

## Tables supprimees

Aucune

## Colonnes ajoutees


**Table : `TEST_CLASSE_01`**
- `+ MODEL_NAME (VARCHAR2(255))`

## Colonnes supprimees

Aucune

## Colonnes modifiees

Aucune

## Relations ajoutees (cles etrangeres)

Aucune

## Relations supprimees (cles etrangeres)

Aucune

## Index ajoutes

- `+ TEST_CLASSE_FILLE_01_IX1`
- `+ TEST_CLASSE_FILLE_01_IX2`

## Index supprimes

Aucun

## Triggers ajoutes

- `+ TEST_CLASSE_FILLE_01_AD_FID`
- `+ TEST_CLASSE_FILLE_01_AI_FID`
- `+ TEST_CLASSE_FILLE_01_AU_FID`
- `+ TEST_CLASSE_FILLE_01_BI_FID`
- `+ TEST_CLASSE_FILLE_01_BU_FID`

## Triggers supprimes

Aucun

## Vues ajoutes

Aucun

## Vues supprimes

Aucun

## Donnees (dump)


**Table : `TB_ATTRIBUTE`**

_8 ligne(s) ajoutee(s)_
- `+ {'ID': 66, 'CAPTION': 'Test_Attribut_02', 'DESCRIPTION': '', 'F_CLASS_ID': 11, 'IS_SYSTEM': 0, 'NAME': 'TEST_ATTRIBUT_02', 'UNIT_ID': 0}`
- `+ {'ID': 69, 'CAPTION': 'Test_Attribut_09', 'DESCRIPTION': '', 'F_CLASS_ID': 11, 'IS_SYSTEM': 0, 'NAME': 'TEST_ATTRIBUT_09', 'UNIT_ID': 0}`
- `+ {'ID': 68, 'CAPTION': 'Test_Attribut_05', 'DESCRIPTION': '', 'F_CLASS_ID': 11, 'IS_SYSTEM': 0, 'NAME': 'TEST_ATTRIBUT_05', 'UNIT_ID': 0}`
- `+ {'ID': 65, 'CAPTION': 'Test_Attribut_01', 'DESCRIPTION': '', 'F_CLASS_ID': 11, 'IS_SYSTEM': 0, 'NAME': 'TEST_ATTRIBUT_01', 'UNIT_ID': 0}`
- `+ {'ID': 71, 'CAPTION': 'Model Name', 'DESCRIPTION': 'Name or number of the model.', 'F_CLASS_ID': 8, 'IS_SYSTEM': 0, 'NAME': 'MODEL_NAME', 'UNIT_ID': 0}`
- `+ {'ID': 64, 'CAPTION': 'FID', 'DESCRIPTION': 'FID', 'F_CLASS_ID': 11, 'IS_SYSTEM': 1, 'NAME': 'FID', 'UNIT_ID': 0}`
- `+ {'ID': 70, 'CAPTION': 'Test_Attribut_10', 'DESCRIPTION': '', 'F_CLASS_ID': 11, 'IS_SYSTEM': 0, 'NAME': 'TEST_ATTRIBUT_10', 'UNIT_ID': 0}`
- `+ {'ID': 67, 'CAPTION': 'Test_Attribut_03', 'DESCRIPTION': '', 'F_CLASS_ID': 11, 'IS_SYSTEM': 0, 'NAME': 'TEST_ATTRIBUT_03', 'UNIT_ID': 0}`

**Table : `TB_DICTIONARY`**

_1 ligne(s) ajoutee(s)_
- `+ {'F_CLASS_ID': 11, 'ACTIVE': 1, 'CAPTION': 'TEST_CLASSE_FILLE_01', 'DIMENSION': 2, 'F_CLASS_NAME': 'TEST_CLASSE_FILLE_01', 'F_CLASS_TYPE': 'T', 'FEATURE_REPRESENTATION': None, 'MAX_X': 'Inf', 'MAX_Y': 'Inf', 'MAX_Z': 'Inf', 'MIN_X': '-Inf', 'MIN_Y': '-Inf', 'MIN_Z': '-Inf', 'MODEL_F_CLASS_ID': 8, 'PARENT_F_CLASS_ID': 1, 'READ_ONLY': 0, 'SPATIAL_RELATE': 'anyinteract', 'SRID': 0, 'TABLE_DOES_NOT_EXIST': 0, 'TOLERANCE': 0.0005, 'TOPIC_ID': 1, 'USER_DEFINED_ELEVATION': 0, 'USER_DEFINED_ORIENTATION': 0, 'VERSION_ENABLED': 0}`

**Table : `TB_RELATIONS`**

_2 ligne(s) ajoutee(s)_
- `+ {'ID': 13, 'ACTIVE': 1, 'CHILD_COLUMN_NAME': 'TEST_ATTRIBUT_09', 'CHILD_TABLE_NAME': 'TEST_CLASSE_FILLE_01', 'CREATE_CHILD': 0, 'DELETE_CHILD': 'N', 'PARENT_COLUMN_NAME': 'FID', 'PARENT_TABLE_NAME': 'TEST_CLASSE_GEO_01', 'MERGE_MODE': None, 'SPLIT_MODE': None}`
- `+ {'ID': 14, 'ACTIVE': 1, 'CHILD_COLUMN_NAME': 'TEST_ATTRIBUT_10', 'CHILD_TABLE_NAME': 'TEST_CLASSE_FILLE_01', 'CREATE_CHILD': 0, 'DELETE_CHILD': 'N', 'PARENT_COLUMN_NAME': 'ID', 'PARENT_TABLE_NAME': 'TEST_DOMAINE_10_TBD', 'MERGE_MODE': None, 'SPLIT_MODE': None}`

**Table : `TB_RULE_BASE`**

_6 ligne(s) ajoutee(s)_
- `+ {'ID': 82, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 0, 'BD': 0, 'BI': 0, 'BU': 1, 'F_CLASS_ID': 11, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 75, 'RULE_DEF_ID': 8104}`
- `+ {'ID': 85, 'ACTIVE': 1, 'AD': 1, 'AI': 0, 'AU': 0, 'BD': 0, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 11, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 130, 'RULE_DEF_ID': 8107}`
- `+ {'ID': 81, 'ACTIVE': 1, 'AD': 1, 'AI': 0, 'AU': 0, 'BD': 0, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 11, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 130, 'RULE_DEF_ID': 11}`
- `+ {'ID': 84, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 0, 'BD': 1, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 11, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 75, 'RULE_DEF_ID': 8106}`
- `+ {'ID': 80, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 0, 'BD': 1, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 11, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 50, 'RULE_DEF_ID': 10}`
- `+ {'ID': 83, 'ACTIVE': 1, 'AD': 0, 'AI': 0, 'AU': 1, 'BD': 0, 'BI': 0, 'BU': 0, 'F_CLASS_ID': 11, 'PARAMETER_1': None, 'PARAMETER_10': None, 'PARAMETER_2': None, 'PARAMETER_3': None, 'PARAMETER_4': None, 'PARAMETER_5': None, 'PARAMETER_6': None, 'PARAMETER_7': None, 'PARAMETER_8': None, 'PARAMETER_9': None, 'PRIORITY': 150, 'RULE_DEF_ID': 8105}`

**Table : `TB_SEQUENCE_EMULATION`**

_3 ligne(s) modifiee(s)_
- Ligne `['SEQUENCE_NAME']=('TB_ATTRIBUTE_S',)` :
  - `NEXT_VALUE` : `64` -> `72`
- Ligne `['SEQUENCE_NAME']=('TB_RULE_BASE_S',)` :
  - `NEXT_VALUE` : `80` -> `86`
- Ligne `['SEQUENCE_NAME']=('TB_DICTIONARY_S',)` :
  - `NEXT_VALUE` : `11` -> `12`

**Table : `fdo_columns`**

_8 ligne(s) ajoutee(s)_
- `+ {'f_table_name': 'TEST_CLASSE_FILLE_01', 'f_column_name': 'TEST_ATTRIBUT_10', 'f_column_desc': 'Number', 'fdo_data_type': 7, 'fdo_data_details': 0, 'fdo_data_length': 0, 'fdo_data_precision': 10, 'fdo_data_scale': 0}`
- `+ {'f_table_name': 'TEST_CLASSE_FILLE_01', 'f_column_name': 'TEST_ATTRIBUT_01', 'f_column_desc': 'Varchar2', 'fdo_data_type': 9, 'fdo_data_details': 0, 'fdo_data_length': 10, 'fdo_data_precision': 0, 'fdo_data_scale': 0}`
- `+ {'f_table_name': 'TEST_CLASSE_FILLE_01', 'f_column_name': 'TEST_ATTRIBUT_05', 'f_column_desc': 'Varchar2', 'fdo_data_type': 9, 'fdo_data_details': 0, 'fdo_data_length': 10, 'fdo_data_precision': 0, 'fdo_data_scale': 0}`
- `+ {'f_table_name': 'TEST_CLASSE_FILLE_01', 'f_column_name': 'TEST_ATTRIBUT_03', 'f_column_desc': 'Number', 'fdo_data_type': 7, 'fdo_data_details': 0, 'fdo_data_length': 0, 'fdo_data_precision': 10, 'fdo_data_scale': 0}`
- `+ {'f_table_name': 'TEST_CLASSE_FILLE_01', 'f_column_name': 'TEST_ATTRIBUT_02', 'f_column_desc': 'Number', 'fdo_data_type': 7, 'fdo_data_details': 0, 'fdo_data_length': 0, 'fdo_data_precision': 10, 'fdo_data_scale': 0}`
- `+ {'f_table_name': 'TEST_CLASSE_01', 'f_column_name': 'MODEL_NAME', 'f_column_desc': 'Varchar2', 'fdo_data_type': 9, 'fdo_data_details': 0, 'fdo_data_length': 255, 'fdo_data_precision': 0, 'fdo_data_scale': 0}`
- `+ {'f_table_name': 'TEST_CLASSE_FILLE_01', 'f_column_name': 'FID', 'f_column_desc': 'Number', 'fdo_data_type': 7, 'fdo_data_details': 2, 'fdo_data_length': 0, 'fdo_data_precision': 18, 'fdo_data_scale': 0}`
- `+ {'f_table_name': 'TEST_CLASSE_FILLE_01', 'f_column_name': 'TEST_ATTRIBUT_09', 'f_column_desc': 'Number', 'fdo_data_type': 7, 'fdo_data_details': 0, 'fdo_data_length': 0, 'fdo_data_precision': 10, 'fdo_data_scale': 0}`
