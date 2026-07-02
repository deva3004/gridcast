"""Pull hourly demand data from the EIA API and land the raw response in S3.

Basic version: one region + one series type + one date range per run, no
pagination or retry yet. Lands at:

    s3://<bucket>/source/eia/region=<region>/type=<type>/ingest_date=<date>/data.json

Run:
    python -m src.ingestion.ingest_eia --region PJM --type D --start 2024-01-01T00 --end 2024-01-02T00
"""

from __future__ import annotations

import argparse  # for CLI argument parsing, example: --region PJM --type D --start 2024-01-01T00 --end 2024-01-02T00
import json # for serializing the payload to JSON before uploading to S3
import os # for accessing environment variables, such as API keys and S3 bucket names,  example: os.environ["EIA_API_KEY"]
from datetime import date 

import boto3 # for interacting with AWS S3, example: boto3.client("s3", region_name=os.environ.get("AWS_REGION"))
import requests # for making HTTP requests to the EIA API, example: requests.get(EIA_BASE_URL, params=params, timeout=30)
from dotenv import load_dotenv 

load_dotenv()

EIA_BASE_URL = "https://api.eia.gov/v2/electricity/rto/region-data/data/"


def fetch_eia_data(region: str, series_type: str, start: str, end: str) -> dict:
    params = {
        "api_key": os.environ["EIA_API_KEY"],
        "frequency": "hourly",
        "data[0]": "value",
        "facets[respondent][]": region,
        "facets[type][]": series_type,
        "start": start,
        "end": end,
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "offset": 0, # starting point for pagination, default is 0
        "length": 5000, # max length per request is 5000, so we may need to paginate if the date range is large, paginate means to make multiple requests with different offsets until we get all the data
    }
    response = requests.get(EIA_BASE_URL, params=params, timeout=30) # Make a GET request to the EIA API with the specified parameters and a timeout of 30 seconds
    response.raise_for_status() # Raises an HTTPError if the response status code indicates an error (4xx or 5xx)
    return response.json() 


def upload_to_s3(payload: dict, bucket: str, region: str, series_type: str) -> str:
    ingest_date = date.today().isoformat()
    key = f"source/eia/region={region}/type={series_type}/ingest_date={ingest_date}/data.json"
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION"))
    s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(payload).encode("utf-8"))
    return key


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull EIA region data and land it in S3.")
    parser.add_argument("--region", default="PJM", choices=["PJM", "CISO", "ERCO"])
    parser.add_argument("--type", dest="series_type", default="D", choices=["D", "DF"])
    parser.add_argument("--start", required=True, help="e.g. 2024-01-01T00")
    parser.add_argument("--end", required=True, help="e.g. 2024-01-02T00")
    args = parser.parse_args()

    bucket = os.environ["GRIDCAST_S3_BUCKET"]

    print(f"Fetching {args.series_type} for {args.region} from {args.start} to {args.end}...")
    payload = fetch_eia_data(args.region, args.series_type, args.start, args.end)

    rows = len(payload.get("response", {}).get("data", [])) # Count the number of rows in the response data, defaulting to 0 if the keys are missing
    print(f"Got {rows} rows.")

    key = upload_to_s3(payload, bucket, args.region, args.series_type)
    print(f"Uploaded to s3://{bucket}/{key}")


if __name__ == "__main__":
    main()
