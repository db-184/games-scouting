"""Loads YAML configs from the config/ directory as a typed container."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Config:
    countries: dict[str, list[str]]
    genres: dict[str, Any]
    signals: dict[str, Any]


def load_config(config_dir: Path) -> Config:
    with (config_dir / "countries.yaml").open() as f:
        countries = yaml.safe_load(f)
    with (config_dir / "genres.yaml").open() as f:
        genres = yaml.safe_load(f)
    with (config_dir / "signals.yaml").open() as f:
        signals = yaml.safe_load(f)
    return Config(countries=countries, genres=genres, signals=signals)
