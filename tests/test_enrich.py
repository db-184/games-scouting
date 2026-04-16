from unittest.mock import patch

from src.signals.enrich import enrich_qualifying_apps
from src.store.db import upsert_app


def test_enrich_refreshes_metadata_for_signal_hits(db):
    candidates = [
        {"app_id": "com.a", "platform": "play"},
        {"app_id": "123",   "platform": "ios"},
    ]

    play_meta = {
        "app_id": "com.a", "platform": "play", "title": "A", "developer": "X",
        "genre_raw": "GAME_PUZZLE", "release_date": "2026-04-01", "icon_url": "u",
        "description": "match-3 game", "price_tier": "free_iap",
        "screenshots_json": "[]", "store_url": "https://play/",
        "rating_avg": 4.5, "rating_count": 1000,
    }
    ios_meta = {
        "app_id": "123", "platform": "ios", "title": "A", "developer": "X",
        "genre_raw": "Puzzle", "release_date": "2026-04-01", "icon_url": "u",
        "description": "match-3 game", "price_tier": "free_iap",
        "screenshots_json": "[]", "store_url": "https://apps/",
        "rating_avg": 4.6, "rating_count": 900,
    }

    with patch("src.signals.enrich.play_fetch_app_metadata", return_value=play_meta), \
         patch("src.signals.enrich.ios_fetch_app_metadata", return_value=ios_meta):
        enrich_qualifying_apps(db, candidates, as_of="2026-04-15", genres_cfg={
            "play_store": {"GAME_PUZZLE": "match3"},
            "app_store": {"Puzzle": "match3"},
            "keyword_overrides": {},
        })

    rows = db.execute("SELECT app_id, platform, genre_bucket, developer FROM apps ORDER BY platform").fetchall()
    assert len(rows) == 2
    assert rows[0]["genre_bucket"] == "match3"
    assert rows[1]["genre_bucket"] == "match3"


def test_enrich_tolerates_individual_failures(db):
    candidates = [
        {"app_id": "com.good", "platform": "play"},
        {"app_id": "com.bad",  "platform": "play"},
    ]

    def _side_effect(app_id, country):
        if app_id == "com.bad":
            raise RuntimeError("iTunes 404")
        return {
            "app_id": app_id, "platform": "play", "title": "OK", "developer": "X",
            "genre_raw": "GAME_PUZZLE", "release_date": None, "icon_url": None,
            "description": None, "price_tier": "free_iap", "screenshots_json": "[]",
            "store_url": None, "rating_avg": 4.0, "rating_count": 100,
        }

    with patch("src.signals.enrich.play_fetch_app_metadata", side_effect=_side_effect):
        enrich_qualifying_apps(db, candidates, as_of="2026-04-15", genres_cfg={
            "play_store": {"GAME_PUZZLE": "match3"},
            "app_store": {},
            "keyword_overrides": {},
        })

    rows = db.execute("SELECT app_id FROM apps").fetchall()
    assert [r["app_id"] for r in rows] == ["com.good"]
