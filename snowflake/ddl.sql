-- DDL for the raw EIA landing table.
-- Each row = one S3 file (the full API response object), held as VARIANT.
-- Flattening response.data into one row per hourly reading happens later,
-- in dbt staging — this table stays an untouched copy of what EIA returned.
--
-- CREATE TABLE IF NOT EXISTS (not OR REPLACE): this table is loaded into
-- incrementally: rerunning this file must never drop already-loaded data.
USE DATABASE GRIDCAST;
USE SCHEMA STAGING;

CREATE TABLE IF NOT EXISTS RAW_EIA_DATA (
    payload      VARIANT,
    source_file  STRING,
    loaded_at    TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);