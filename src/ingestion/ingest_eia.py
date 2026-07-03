"""EIA API client + raw landing writer.

Pulls hourly region data from the EIA API v2, paginating past the API's
5000-row/request cap and retrying transient failures, then lands each
region/series-type pull as newline-delimited JSON (one line per page, i.e.
one line per full API response object) at:

    <prefix>/region=<region>/type=<type>/ingest_date=<date>/data.ndjson
    <prefix>/region=<region>/type=<type>/ingest_date=<date>/manifest.json

`ingest_date` is the date the *pull* ran, not the date range requested — a
5-year backfill run today lands under a single ingest_date partition. The
raw layer is immutable: this module never reshapes or filters the payload,
it only paginates and lands it. Reshaping into one row per hourly reading
happens later, in dbt staging.

This module is the engine; src/ingestion/run.py is the CLI that drives it
across regions/series-types/date-ranges.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date
from typing import Any

import requests

from src.ingestion.data_ingestion import IngestionConfig, RetryConfig


def build_session() -> requests.Session:
    session = requests.Session()
    session.params = {"api_key": os.environ["EIA_API_KEY"]}
    return session


def _sleep_before_retry(attempt: int, retry_cfg: RetryConfig) -> None:
    # attempt 1 = first try, no sleep. attempt 2..N = retries: 1.5s, 3s, 6s, 12s...
    if attempt <= 1:
        return
    delay = retry_cfg.backoff_factor * (2 ** (attempt - 2))
    time.sleep(delay)


def _get_with_retry(
    session: requests.Session, url: str, params: dict, timeout: int, retry_cfg: RetryConfig
) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(1, retry_cfg.max_attempts + 1):
        _sleep_before_retry(attempt, retry_cfg)
        try:
            response = session.get(url, params=params, timeout=timeout)
        except requests.RequestException as exc:
            last_exc = exc
            continue
        if response.status_code in retry_cfg.status_forcelist:
            last_exc = requests.HTTPError(
                f"{response.status_code} from {url}", response=response
            )
            continue
        response.raise_for_status()
        return response
    assert last_exc is not None
    raise last_exc


def fetch_eia_series(
    session: requests.Session,
    config: IngestionConfig,
    region: str,
    series_type: str,
    start: str,
    end: str,
) -> list[dict[str, Any]]:
    """Paginate through the full [start, end) window, returning one dict per page."""
    pages: list[dict[str, Any]] = []
    offset = 0
    total: int | None = None

    while total is None or offset < total:
        params = {
            "frequency": config.frequency,
            "data[0]": "value",
            "facets[respondent][]": region,
            "facets[type][]": series_type,
            "start": start,
            "end": end,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "offset": offset,
            "length": config.page_size,
        }
        response = _get_with_retry(
            session, config.base_url, params, config.request_timeout, config.retry
        )
        payload = response.json()
        pages.append(payload)

        total = int(payload.get("response", {}).get("total", 0))
        rows = payload.get("response", {}).get("data", [])
        print(
            f"  page offset={offset}: {len(rows)} rows "
            f"({offset + len(rows)}/{total})"
        )
        if not rows:
            break
        offset += len(rows)

    return pages


def row_count(pages: list[dict[str, Any]]) -> int:
    return sum(len(p.get("response", {}).get("data", [])) for p in pages)


def build_manifest(
    region: str,
    series_type: str,
    start: str,
    end: str,
    pages: list[dict[str, Any]],
    ingest_date: str,
) -> dict[str, Any]:
    rows = row_count(pages)
    return {
        "region": region,
        "type": series_type,
        "start": start,
        "end": end,
        "ingest_date": ingest_date,
        "page_count": len(pages),
        "row_count": rows,
        "empty": rows == 0,
        "api_version": pages[0].get("apiVersion") if pages else None,
    }


def _partition_key(
    s3_prefix: str, region: str, series_type: str, ingest_date: str, filename: str
) -> str:
    return f"{s3_prefix}/region={region}/type={series_type}/ingest_date={ingest_date}/{filename}"


def _to_ndjson(pages: list[dict[str, Any]]) -> bytes:
    return ("\n".join(json.dumps(p) for p in pages) + "\n" if pages else "").encode("utf-8")


def upload_to_s3(
    s3_client: Any,
    pages: list[dict[str, Any]],
    manifest: dict[str, Any],
    bucket: str,
    s3_prefix: str,
    region: str,
    series_type: str,
    ingest_date: str,
) -> str:
    data_key = _partition_key(s3_prefix, region, series_type, ingest_date, "data.ndjson")
    manifest_key = _partition_key(s3_prefix, region, series_type, ingest_date, "manifest.json")

    s3_client.put_object(Bucket=bucket, Key=data_key, Body=_to_ndjson(pages))
    s3_client.put_object(
        Bucket=bucket, Key=manifest_key, Body=json.dumps(manifest, indent=2).encode("utf-8")
    )
    return data_key


def write_local(
    pages: list[dict[str, Any]],
    manifest: dict[str, Any],
    out_dir: Any,
    s3_prefix: str,
    region: str,
    series_type: str,
    ingest_date: str,
) -> Any:
    """Dry-run landing: mirror the S3 key layout under a local directory."""
    partition_dir = (
        out_dir
        / s3_prefix
        / f"region={region}"
        / f"type={series_type}"
        / f"ingest_date={ingest_date}"
    )
    partition_dir.mkdir(parents=True, exist_ok=True)

    (partition_dir / "data.ndjson").write_bytes(_to_ndjson(pages))
    (partition_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return partition_dir / "data.ndjson"


def default_ingest_date() -> str:
    return date.today().isoformat()
