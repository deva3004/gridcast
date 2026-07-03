"""CLI entrypoint for EIA backfills — drives ingest_eia.py across every
region x series-type combination in config/data_ingestion.config over a
date range, landing each combination as its own raw partition.

Examples:
    # ~5 years, all regions/types configured, to S3 (needs AWS + EIA_API_KEY)
    python -m src.ingestion.run

    # Same, but write to ./data/ instead of S3 (no AWS needed) — inspect first
    python -m src.ingestion.run --dry-run

    # A narrower, explicit backfill
    python -m src.ingestion.run --regions PJM --types D --start 2021-01-01T00 --end 2026-01-01T00
"""

from __future__ import annotations

import argparse # helps with CLI args
import os # helps with env vars
from datetime import datetime, timedelta, timezone # helps with date math
from pathlib import Path # Path helps with file path

from dotenv import load_dotenv # helps with .env files

from src.ingestion.data_ingestion import load_config # Whenever I need my configuration, I'll ask data_ingestion.py.
from src.ingestion.ingest_eia import (
    build_manifest,
    build_session,
    default_ingest_date,
    fetch_eia_series,
    row_count,
    upload_to_s3,
    write_local,
) # this is the engine; src/ingestion/run.py is the CLI that drives it across regions/series-types/date-ranges.

load_dotenv() 

LOCAL_DRY_RUN_DIR = Path("data") # helps with local dry-run writes, so you can inspect before uploading to S3

# parse_args() is used to parse command-line arguments, and it takes the configuration as input to validate the provided regions and series types. It returns a Namespace object containing the parsed arguments.
def parse_args(config) -> argparse.Namespace: 
    parser = argparse.ArgumentParser(description="Backfill EIA region data into the raw landing layer.")
    parser.add_argument("--regions", nargs="+", choices=list(config.regions), default=list(config.regions))
    parser.add_argument(
        "--types", nargs="+", dest="series_types", choices=list(config.series_types), default=list(config.series_types)
    )
    parser.add_argument("--start", help="e.g. 2021-01-01T00 (UTC hour). Requires --end.")
    parser.add_argument("--end", help="e.g. 2026-01-01T00 (UTC hour). Requires --start.")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=config.default_lookback_days,
        help="Used when --start/--end aren't given.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help=f"Land under ./{LOCAL_DRY_RUN_DIR}/ instead of S3; no AWS needed."
    )
    args = parser.parse_args()

    if bool(args.start) != bool(args.end): # smart check: if one is given, the other must be given too. If both are given, it's fine. If neither is given, it's fine.
        parser.error("--start and --end must be given together")
    return args

# resolve_window() is used to determine the start and end date for the backfill operation. If both --start and --end are provided, it uses those values. If not, it calculates the start date based on the current date minus the lookback days specified in the configuration.
def resolve_window(args: argparse.Namespace) -> tuple[str, str]:
    if args.start and args.end:
        return args.start, args.end
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=args.lookback_days)
    return start_dt.strftime("%Y-%m-%dT%H"), end_dt.strftime("%Y-%m-%dT%H")


def main() -> None:
    config = load_config()
    args = parse_args(config)
    start, end = resolve_window(args)
    ingest_date = default_ingest_date()

    s3_client = None
    bucket = None
    if not args.dry_run:
        import boto3

        bucket = os.environ["GRIDCAST_S3_BUCKET"]
        s3_client = boto3.client("s3", region_name=os.environ.get("AWS_REGION"))

    session = build_session()

    combos = [(r, t) for r in args.regions for t in args.series_types]
    print(f"Backfilling {len(combos)} region/type combinations from {start} to {end}"
          f"{' (dry run, local only)' if args.dry_run else f' -> s3://{bucket}/{config.s3_prefix}'}")

    manifests = []
    for region, series_type in combos:
        print(f"\n=== {region} / {series_type} ===")
        pages = fetch_eia_series(session, config, region, series_type, start, end) # this is the main workhorse function that fetches the data from the EIA API for the given region and series type over the specified date range. It returns a list of pages, where each page is a dictionary containing the data for that page.
        manifest = build_manifest(region, series_type, start, end, pages, ingest_date) # this function builds a manifest for the fetched data, which includes metadata such as the region, series type, start and end dates, ingest date, page count, row count, and whether the data is empty. The manifest is a dictionary that provides a summary of the fetched data.
        manifests.append(manifest)

        if args.dry_run:
            path = write_local(
                pages, manifest, LOCAL_DRY_RUN_DIR, config.s3_prefix, region, series_type, ingest_date
            )
            print(f"[dry-run] wrote {path} ({manifest['row_count']} rows, {manifest['page_count']} pages)")
        else:
            key = upload_to_s3(
                s3_client, pages, manifest, bucket, config.s3_prefix, region, series_type, ingest_date
            )
            print(f"Uploaded s3://{bucket}/{key} ({manifest['row_count']} rows, {manifest['page_count']} pages)")

        if manifest["empty"]:
            print(f"  WARNING: no rows returned for {region}/{series_type} in this window.")

    total_rows = sum(m["row_count"] for m in manifests)
    empty = [f"{m['region']}/{m['type']}" for m in manifests if m["empty"]]
    print(f"\nDone. {total_rows} total rows across {len(manifests)} partitions.")
    if empty:
        print(f"Empty partitions: {', '.join(empty)}")


if __name__ == "__main__":
    main()
