"""Data-cleaning step for the DVC pipeline.

Takes the raw ingest (one row per hour/respondent, with demand_mwh and
forecast_mwh) and fixes the two real problems that show up in it:
duplicate rows from re-running the same export, and physically impossible
negative demand readings. Missing values are left alone -- an hour EIA
hasn't reported yet is information, not something to paper over here; the
lag/rolling features in the next stage naturally carry that NaN forward.
"""

from __future__ import annotations

import pandas as pd


def clean_demand_forecast(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["demand_hour_utc"] = pd.to_datetime(df["demand_hour_utc"])

    df = df.drop_duplicates(subset=["respondent", "demand_hour_utc"], keep="first")

    # Demand can't be negative -- treat it as "not reported" rather than a
    # real reading, so it doesn't quietly drag down a rolling mean later.
    df.loc[df["demand_mwh"] < 0, "demand_mwh"] = pd.NA

    return df.sort_values(["respondent", "demand_hour_utc"]).reset_index(drop=True)
