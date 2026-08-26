"""Registers an already-trained model into MLflow, without retraining.

Exists because the production MLflow registry is deliberately ephemeral --
`terraform/compute.tf` uses `health_check_type = "EC2"` specifically because
this instance's registry has no durable backend (see problem_faced.txt entry
13), so every replacement instance boots with an *empty* registry. Retraining
on every replacement would be wasteful (and, right now, impossible -- the
source warehouse is unreachable). Instead, this imports the same fitted
model object DVC's train stage already produced (`models/model_lightgbm.pkl`)
into whatever fresh registry it's pointed at, then promotes it straight to
the "production" alias.

Usage:
    python -m src.api.register_pretrained_model
"""

from __future__ import annotations

import os
from pathlib import Path

import joblib
import mlflow
import mlflow.lightgbm
from mlflow.tracking import MlflowClient

MODEL_PATH = Path("data/model/model_lightgbm.pkl")
REGISTERED_MODEL_NAME = "gridcast-demand-forecaster-lightgbm"
ALIAS = "production"


def register(model_path: Path = MODEL_PATH) -> int:
    model = joblib.load(model_path)

    with mlflow.start_run(run_name="register-pretrained-lightgbm"):
        info = mlflow.lightgbm.log_model(
            model,
            artifact_path="model",
            registered_model_name=REGISTERED_MODEL_NAME,
        )

    version = info.registered_model_version
    MlflowClient().set_registered_model_alias(REGISTERED_MODEL_NAME, ALIAS, version)
    return version


def main() -> None:
    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    version = register()
    print(f"registered {REGISTERED_MODEL_NAME} v{version} @{ALIAS}")


if __name__ == "__main__":
    main()
