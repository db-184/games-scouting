from pathlib import Path
from src.config import load_config

CONFIG_DIR = Path(__file__).parent.parent / "config"


def test_load_countries():
    cfg = load_config(CONFIG_DIR)
    assert "IN" in cfg.countries["play_store"]
    assert "CN" in cfg.countries["app_store"]
    assert "CN" not in cfg.countries["play_store"]  # spec §2.2


def test_load_signals_thresholds():
    cfg = load_config(CONFIG_DIR)
    assert cfg.signals["fast_climber"]["min_rank_jump"] == 20
    assert cfg.signals["new_entrant"]["max_window_days"] == 14


def test_load_genres_mapping():
    cfg = load_config(CONFIG_DIR)
    assert cfg.genres["play_store"]["GAME_PUZZLE"] == "match3"
    assert "match-3" in cfg.genres["keyword_overrides"]["match3"]
