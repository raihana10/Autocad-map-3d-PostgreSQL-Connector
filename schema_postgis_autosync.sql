-- ============================================================
-- DDL GENERATED AUTOMATICALLY BY Autocad-map-3d-PostgreSQL-Connector
-- Source File : Drawing1
-- Target Database : PostgreSQL / PostGIS (SRID 2154)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS postgis;

-- ============================================================
-- 1. TABLES DE DOMAINES DE VALEURS (_TBD) & VALEURS ENUMERÉES
-- ============================================================

CREATE TABLE IF NOT EXISTS "TB_DOMAIN" (
    "ID" integer PRIMARY KEY,
    "ACTIVE" text,
    "CAPTION" text,
    "READ_ONLY" text,
    "TABLE_DOES_NOT_EXIST" text,
    "TABLE_NAME" text
);

INSERT INTO "TB_DOMAIN" ("ID", "ACTIVE", "CAPTION", "READ_ONLY", "TABLE_DOES_NOT_EXIST", "TABLE_NAME") VALUES (1, 1, 'Horizontal Alignment', 0, 0, 'TB_HOR_ALIGNMENT_TBD') ON CONFLICT DO NOTHING;
INSERT INTO "TB_DOMAIN" ("ID", "ACTIVE", "CAPTION", "READ_ONLY", "TABLE_DOES_NOT_EXIST", "TABLE_NAME") VALUES (2, 1, 'Vertical Alignment', 0, 0, 'TB_VER_ALIGNMENT_TBD') ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS "TB_HOR_ALIGNMENT_TBD" (
    "ID" integer PRIMARY KEY,
    "SHORT_VALUE" text,
    "VALUE" text,
    "DATE_OF_CREATION" text,
    "DESIGNER" text,
    "COMMENTARY" text,
    "ACTIVE" text,
    "PRIORITY" text
);

INSERT INTO "TB_HOR_ALIGNMENT_TBD" ("ID", "SHORT_VALUE", "VALUE", "DATE_OF_CREATION", "DESIGNER", "COMMENTARY", "ACTIVE", "PRIORITY") VALUES (1, 'Left', 'Left', NULL, 'Autodesk, Inc.', 'Horizontal Alignment', 1, NULL) ON CONFLICT DO NOTHING;
INSERT INTO "TB_HOR_ALIGNMENT_TBD" ("ID", "SHORT_VALUE", "VALUE", "DATE_OF_CREATION", "DESIGNER", "COMMENTARY", "ACTIVE", "PRIORITY") VALUES (2, 'Center', 'Center', NULL, 'Autodesk, Inc.', 'Horizontal Alignment', 1, NULL) ON CONFLICT DO NOTHING;
INSERT INTO "TB_HOR_ALIGNMENT_TBD" ("ID", "SHORT_VALUE", "VALUE", "DATE_OF_CREATION", "DESIGNER", "COMMENTARY", "ACTIVE", "PRIORITY") VALUES (3, 'Right', 'Right', NULL, 'Autodesk, Inc.', 'Horizontal Alignment', 1, NULL) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS "TB_VER_ALIGNMENT_TBD" (
    "ID" integer PRIMARY KEY,
    "SHORT_VALUE" text,
    "VALUE" text,
    "DATE_OF_CREATION" text,
    "DESIGNER" text,
    "COMMENTARY" text,
    "ACTIVE" text,
    "PRIORITY" text
);

INSERT INTO "TB_VER_ALIGNMENT_TBD" ("ID", "SHORT_VALUE", "VALUE", "DATE_OF_CREATION", "DESIGNER", "COMMENTARY", "ACTIVE", "PRIORITY") VALUES (1, 'Bottom', 'Bottom', NULL, 'Autodesk, Inc.', 'Vertical Alignment', 1, NULL) ON CONFLICT DO NOTHING;
INSERT INTO "TB_VER_ALIGNMENT_TBD" ("ID", "SHORT_VALUE", "VALUE", "DATE_OF_CREATION", "DESIGNER", "COMMENTARY", "ACTIVE", "PRIORITY") VALUES (2, 'Baseline', 'Baseline', NULL, 'Autodesk, Inc.', 'Vertical Alignment', 1, NULL) ON CONFLICT DO NOTHING;
INSERT INTO "TB_VER_ALIGNMENT_TBD" ("ID", "SHORT_VALUE", "VALUE", "DATE_OF_CREATION", "DESIGNER", "COMMENTARY", "ACTIVE", "PRIORITY") VALUES (3, 'Halfline', 'Halfline', NULL, 'Autodesk, Inc.', 'Vertical Alignment', 1, NULL) ON CONFLICT DO NOTHING;
INSERT INTO "TB_VER_ALIGNMENT_TBD" ("ID", "SHORT_VALUE", "VALUE", "DATE_OF_CREATION", "DESIGNER", "COMMENTARY", "ACTIVE", "PRIORITY") VALUES (4, 'Capline', 'Capline', NULL, 'Autodesk, Inc.', 'Vertical Alignment', 1, NULL) ON CONFLICT DO NOTHING;
INSERT INTO "TB_VER_ALIGNMENT_TBD" ("ID", "SHORT_VALUE", "VALUE", "DATE_OF_CREATION", "DESIGNER", "COMMENTARY", "ACTIVE", "PRIORITY") VALUES (5, 'Top', 'Top', NULL, 'Autodesk, Inc.', 'Vertical Alignment', 1, NULL) ON CONFLICT DO NOTHING;

-- ============================================================
-- 2. FEATURE CLASSES (TABLES METIERS ET GEOMETRIES POSTGIS)
-- ============================================================

-- ------------------------------------------------------------
-- Feature Class : CONSTRUCT (Construct Parent) [Type FDO: T]
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "CONSTRUCT" (
    "FID" integer NOT NULL,
    PRIMARY KEY ("FID")
);

-- ------------------------------------------------------------
-- Feature Class : CONSTRUCT_LINES (Construct Line) [Type FDO: L]
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "CONSTRUCT_LINES" (
    "FID" integer NOT NULL,
    "GEOM" geometry(LineString, 25832),
    "LENGTH" double precision,
    "DESCRIPTION" text,
    "FID_PARENT" integer,
    PRIMARY KEY ("FID")
);

CREATE INDEX IF NOT EXISTS "idx_CONSTRUCT_LINES_GEOM_gist" ON "CONSTRUCT_LINES" USING GIST ("GEOM");

-- ------------------------------------------------------------
-- Feature Class : CONSTRUCT_MARKERS (Construct Marker) [Type FDO: P]
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "CONSTRUCT_MARKERS" (
    "FID" integer NOT NULL,
    "GEOM" geometry(Point, 25832),
    "ORIENTATION" double precision NOT NULL DEFAULT 90,
    "Z" double precision,
    "QUALITY" integer,
    "DESCRIPTION" text,
    "FID_PARENT" integer,
    PRIMARY KEY ("FID")
);

CREATE INDEX IF NOT EXISTS "idx_CONSTRUCT_MARKERS_GEOM_gist" ON "CONSTRUCT_MARKERS" USING GIST ("GEOM");

-- ------------------------------------------------------------
-- Feature Class : CONSTRUCT_POINTS (Construct Point) [Type FDO: P]
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "CONSTRUCT_POINTS" (
    "FID" integer NOT NULL,
    "GEOM" geometry(Point, 25832),
    "ORIENTATION" double precision NOT NULL DEFAULT 90,
    "Z" double precision,
    "QUALITY" integer,
    "DESCRIPTION" text,
    "FID_PARENT" integer,
    PRIMARY KEY ("FID")
);

CREATE INDEX IF NOT EXISTS "idx_CONSTRUCT_POINTS_GEOM_gist" ON "CONSTRUCT_POINTS" USING GIST ("GEOM");

-- ------------------------------------------------------------
-- Feature Class : CONSTRUCT_POINTS_TBL (Construct Point Label) [Type FDO: A]
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "CONSTRUCT_POINTS_TBL" (
    "FID" integer NOT NULL,
    "GEOM" geometry(Point, 25832),
    "LABEL_DEF_ID" integer,
    "FID_PARENT" integer,
    "LABEL_TEXT" text,
    "HORIZONTAL_ALIGNMENT" text NOT NULL DEFAULT 'Left',
    "VERTICAL_ALIGNMENT" text NOT NULL DEFAULT 'Baseline',
    "ORIENTATION" double precision NOT NULL DEFAULT 90,
    "PRE" text,
    "SUF" text,
    PRIMARY KEY ("FID")
);

CREATE INDEX IF NOT EXISTS "idx_CONSTRUCT_POINTS_TBL_GEOM_gist" ON "CONSTRUCT_POINTS_TBL" USING GIST ("GEOM");

-- ------------------------------------------------------------
-- Feature Class : TB_FEATURE_GROUP (Feature Group) [Type FDO: P]
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "TB_FEATURE_GROUP" (
    "FID" integer NOT NULL,
    "GEOM" geometry(Point, 25832),
    "ORIENTATION" double precision NOT NULL DEFAULT 90,
    "Z" double precision,
    "QUALITY" integer,
    "DATE_CREATION" text,
    "FID_TEMPLATE" integer,
    "IS_MIRROR" integer,
    "SCALE_FACTOR" double precision,
    "USER_FLAG" text,
    PRIMARY KEY ("FID")
);

CREATE INDEX IF NOT EXISTS "idx_TB_FEATURE_GROUP_GEOM_gist" ON "TB_FEATURE_GROUP" USING GIST ("GEOM");

-- ------------------------------------------------------------
-- Feature Class : TB_FEATURE_GROUP_FEATURE (Feature Group Feature) [Type FDO: T]
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "TB_FEATURE_GROUP_FEATURE" (
    "FID" integer NOT NULL,
    "F_CLASS_ID" integer,
    "FID_FEATURE" integer,
    "FID_FEATURE_GROUP" integer,
    "FID_TEMPLATE_FEATURE" integer,
    "USER_FLAG" text,
    "DATE_CREATION" text,
    PRIMARY KEY ("FID")
);

-- ============================================================
-- 3. FOREIGN KEYS & RELATIONS (TB_RELATIONS)
-- ============================================================


-- ============================================================
-- 4. TRIGGERS PL/PGSQL POUR CALCULS AUTOMATIQUES (EX: ST_LENGTH)
-- ============================================================


CREATE OR REPLACE FUNCTION fn_calc_autodesk_length()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.geom IS NOT NULL THEN
        NEW.length := ST_Length(NEW.geom);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS "trg_calc_length_CONSTRUCT_LINES" ON "CONSTRUCT_LINES";
CREATE TRIGGER "trg_calc_length_CONSTRUCT_LINES" BEFORE INSERT OR UPDATE OF "GEOM" ON "CONSTRUCT_LINES" FOR EACH ROW EXECUTE FUNCTION fn_calc_autodesk_length();
