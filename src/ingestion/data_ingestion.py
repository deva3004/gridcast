"""Load ingestion settings from config/data_ingestion.config (YAML).

Keeps region/series-type/retry/pagination knobs out of code so they can be
tuned (or a new region added) without touching ingest_eia.py or run.py.
"""

from __future__ import annotations # this is needed for the type hinting of RetryConfig and IngestionConfig in ingest_eia.py, example: def _sleep_before_retry(attempt: int, retry_cfg: RetryConfig) -> None:

from dataclasses import dataclass 
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "data_ingestion.config"


@dataclass(frozen=True) #frozen=True makes the dataclass immutable, meaning that once an instance is created, its attributes cannot be modified. This is useful for configuration objects that should not change after they are initialized.
class RetryConfig:
    max_attempts: int
    backoff_factor: float
    status_forcelist: tuple[int, ...]


@dataclass(frozen=True)
class IngestionConfig:
    base_url: str
    frequency: str
    regions: tuple[str, ...]
    series_types: tuple[str, ...]
    page_size: int
    request_timeout: int
    default_lookback_days: int
    s3_prefix: str
    retry: RetryConfig


def load_config(path: Path = CONFIG_PATH) -> IngestionConfig:
    raw = yaml.safe_load(path.read_text())
    eia = raw["eia"]
    retry = raw["retry"]
    ingestion = raw["ingestion"]
    return IngestionConfig(
        base_url=eia["base_url"],
        frequency=eia["frequency"],
        regions=tuple(eia["regions"]),
        series_types=tuple(eia["series_types"]),
        page_size=eia["page_size"],
        request_timeout=ingestion["request_timeout"],
        default_lookback_days=ingestion["default_lookback_days"],
        s3_prefix=raw["s3"]["prefix"],
        retry=RetryConfig(
            max_attempts=retry["max_attempts"],
            backoff_factor=retry["backoff_factor"],
            status_forcelist=tuple(retry["status_forcelist"]),
        ),
    )
