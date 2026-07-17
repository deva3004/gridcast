"""Shared Snowflake connection helper.

ml/, monitoring/, and (eventually) the API all need to read from the
warehouse; this is the one place that knows how to open a connection and
pull a query into a DataFrame, so credentials and connection settings live
in exactly one spot instead of being copy-pasted into every consumer.
"""

from __future__ import annotations

import os

import pandas as pd
import snowflake.connector


def get_connection() -> snowflake.connector.SnowflakeConnection:
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        role=os.environ["SNOWFLAKE_ROLE"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
    )


def read_sql(query: str) -> pd.DataFrame:
    """Runs `query`, returns the full result as a DataFrame.

    fetch_pandas_all() pulls Arrow batches straight into pandas instead of
    building a list of Python tuples row by row -- much faster for the
    ~hundreds-of-thousands-of-rows feature pull this is used for.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetch_pandas_all()
    finally:
        conn.close()


def schema_for(layer: str) -> str:
    """The physical schema dbt materialized a given layer into.

    dbt_project.yml sets `+schema: <layer>` per layer (staging/intermediate/
    marts), but with no custom generate_schema_name macro in this project,
    dbt's *default* behavior applies: the custom schema is appended to the
    profile's target schema (SNOWFLAKE_SCHEMA), not used on its own. So
    `+schema: intermediate` with SNOWFLAKE_SCHEMA=RAW built that layer into
    `RAW_INTERMEDIATE`, not `INTERMEDIATE`.
    """
    return f"{os.environ['SNOWFLAKE_SCHEMA']}_{layer.upper()}"
