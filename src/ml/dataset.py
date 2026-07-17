"""Turns fct_demand_features (one row per hour/respondent) into a
horizon-stacked training frame, and splits it in time with an embargo gap.

Two separate concerns, kept apart on purpose:
  - fct_demand_features (dbt) is the *feature store* -- point-in-time-correct
    features, with no notion of what's being predicted.
  - stack_horizons here is *label engineering* -- it decides the prediction
    task (demand h hours out, for h in 1..24) and is a training-time
    concern, not something that belongs in a shared feature mart other
    consumers (serving, monitoring) also read from.
"""

from __future__ import annotations

import pandas as pd

FEATURE_COLUMNS = [
    "horizon",
    "hour_of_day",
    "day_of_week",
    "month",
    "is_weekend",
    "is_holiday",
    "demand_lag_1h",
    "demand_lag_24h",
    "demand_lag_168h",
    "demand_rolling_mean_24h",
    "demand_rolling_std_24h",
    "demand_rolling_mean_168h",
    "demand_rolling_std_168h",
]


def stack_horizons(features: pd.DataFrame, horizons: range) -> pd.DataFrame:
    """One row per (respondent, origin hour t, horizon h): features as of
    t, the true demand at t+h (target_mwh), and EIA's own forecast for t+h
    (baseline_mwh) -- so every row can be scored against the baseline it's
    trying to beat.

    Joins on demand_hour_utc rather than shifting by row position: a
    positional shift silently produces the wrong label the moment a
    respondent's series has a missing hour, and EIA's feed does have gaps.
    """
    frames = []
    for horizon in horizons:
        future = features[["respondent", "demand_hour_utc", "demand_mwh", "forecast_mwh"]].copy()
        future["demand_hour_utc"] -= pd.Timedelta(hours=horizon)
        future = future.rename(
            columns={"demand_mwh": "target_mwh", "forecast_mwh": "baseline_mwh"}
        )
        merged = features.merge(future, on=["respondent", "demand_hour_utc"], how="inner")
        merged["horizon"] = horizon
        frames.append(merged)
    return pd.concat(frames, ignore_index=True)


def time_split(
    stacked: pd.DataFrame, test_frac: float = 0.2, embargo_hours: int = 24
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Splits by *origin* hour (demand_hour_utc), never shuffled, with an
    embargo gap between train and test.

    Without the embargo, a train row with origin hour t and horizon 24 has
    a target at t+24, which can land inside the test window -- fitting the
    model on the very hours test is supposed to measure. The embargo pushes
    test's start out past every train row's furthest-out target.
    """
    origin_hours = stacked["demand_hour_utc"].sort_values().unique()
    cutoff = origin_hours[int(len(origin_hours) * (1 - test_frac))]
    test_start = cutoff + pd.Timedelta(hours=embargo_hours)

    train = stacked[stacked["demand_hour_utc"] <= cutoff]
    test = stacked[stacked["demand_hour_utc"] >= test_start]
    return train, test
