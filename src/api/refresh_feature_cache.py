"""Refreshes the local snapshot the API serves forecasts from.

Pulls just the latest row per respondent from fct_demand_features (via
QUALIFY ROW_NUMBER()) instead of rerunning 01_ingest.ipynb's full-history
pull, which would be wasteful just to get one fresh row per respondent.
Meant to be run periodically (cron/Airflow), separate from the API process
itself, so a cache refresh doesn't require restarting the API.

Usage:
    python -m src.api.refresh_feature_cache
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

from src.warehouse.snowflake_client import read_sql, schema_for

CACHE_PATH = Path("data/cache/latest_features.csv")

QUERY_TEMPLATE = """
SELECT *
FROM {schema}.FCT_DEMAND_FEATURES
QUALIFY ROW_NUMBER() OVER (PARTITION BY respondent ORDER BY demand_hour_utc DESC) = 1
"""


def refresh(cache_path: Path = CACHE_PATH) -> Path:
    query = QUERY_TEMPLATE.format(schema=schema_for("marts"))
    df = read_sql(query)
    df.columns = df.columns.str.lower()

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path, index=False)
    return cache_path


def main() -> None:
    load_dotenv()
    path = refresh()
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
