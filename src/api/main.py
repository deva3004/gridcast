"""FastAPI serving layer for GridCast demand forecasts.

Loads the LightGBM model from the MLflow registry by alias (registry
*stages* -- None/Staging/Production -- are deprecated in favor of aliases,
and newer MLflow UIs drop the stage-transition control entirely) rather
than a local .pkl, so re-pointing the "production" alias at a new version
doesn't require redeploying the API. Re-reads the feature cache
(`data/cache/latest_features.csv`, written by refresh_feature_cache.py) on
every request too, so a cache refresh takes effect without an API restart.
"""

from __future__ import annotations

import os
from pathlib import Path

import mlflow
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from src.ml.dataset import FEATURE_COLUMNS

load_dotenv()

MODEL_URI = "models:/gridcast-demand-forecaster-lightgbm@production"
CACHE_PATH = Path("data/cache/latest_features.csv")
HORIZONS = range(1, 25)

mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
model = mlflow.pyfunc.load_model(MODEL_URI)

app = FastAPI(title="GridCast")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/forecast")
def forecast(respondent: str) -> dict:
    if not CACHE_PATH.exists():
        raise HTTPException(503, "feature cache not populated -- run refresh_feature_cache.py")

    cache = pd.read_csv(CACHE_PATH, parse_dates=["demand_hour_utc"])
    matches = cache[cache["respondent"] == respondent]
    if matches.empty:
        raise HTTPException(404, f"no cached features for respondent {respondent!r}")
    row = matches.iloc[0]

    origin_hour = row["demand_hour_utc"]
    base_features = row[[c for c in FEATURE_COLUMNS if c != "horizon"]].to_dict()
    inputs = pd.DataFrame(
        [{**base_features, "horizon": h} for h in HORIZONS]
    )[FEATURE_COLUMNS]

    predictions = model.predict(inputs)

    return {
        "respondent": respondent,
        "origin_hour_utc": origin_hour.isoformat(),
        "forecasts": [
            {
                "horizon": h,
                "target_hour_utc": (origin_hour + pd.Timedelta(hours=h)).isoformat(),
                "predicted_demand_mwh": float(pred),
            }
            for h, pred in zip(HORIZONS, predictions, strict=True)
        ],
    }
