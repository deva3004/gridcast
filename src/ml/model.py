"""Model fitting + evaluation for the DVC train stage.

Kept separate from notebooks/04_train.ipynb so the actual model-fitting logic
is plain, importable, and reusable later (e.g. from the FastAPI service),
while the notebook stays focused on orchestration, MLflow logging, and
plots -- the part that's genuinely easier to read as a notebook.

All four regressors here (LightGBM, XGBoost, CatBoost, scikit-learn's
RandomForest) implement the same fit(X, y)/predict(X) surface, so
train_model/evaluate stay written against that shared interface rather than
any one library -- swapping algorithms is a one-line change in params.yaml
(train.model_type), not a rewrite of this module.
"""

from __future__ import annotations

import catboost as cb
import lightgbm as lgb
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error

from src.ml.dataset import FEATURE_COLUMNS

MODEL_BUILDERS = {
    "lightgbm": lambda params: lgb.LGBMRegressor(**params),
    "xgboost": lambda params: xgb.XGBRegressor(**params),
    "catboost": lambda params: cb.CatBoostRegressor(**params, verbose=False),
    "random_forest": lambda params: RandomForestRegressor(**params),
}


def train_model(train_df: pd.DataFrame, model_type: str, params: dict):
    if model_type not in MODEL_BUILDERS:
        raise ValueError(f"unknown model_type {model_type!r}, expected one of {list(MODEL_BUILDERS)}")
    model = MODEL_BUILDERS[model_type](params)
    model.fit(train_df[FEATURE_COLUMNS], train_df["target_mwh"])
    return model


def score(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "mape": float(mean_absolute_percentage_error(actual, predicted)),
    }


def evaluate(model, test_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Returns the test set with a model_pred column attached, plus MAE/MAPE
    for the model and for the EIA baseline (baseline_mwh), so they're always
    scored on the exact same rows.
    """
    test_df = test_df.copy()
    test_df["model_pred"] = model.predict(test_df[FEATURE_COLUMNS])

    metrics = {
        "model": score(test_df["target_mwh"], test_df["model_pred"]),
        "baseline": score(test_df["target_mwh"], test_df["baseline_mwh"]),
    }
    return test_df, metrics
