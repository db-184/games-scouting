from src.signals.new_entrant import find_new_entrants
from src.store.db import upsert_app
from tests.conftest import seed_ranks

SIGNALS_CFG = {
    "new_entrant": {
        "max_window_days": 14,
        "play_store_chart_ceiling": 200,
        "app_store_chart_ceiling": 100,
        "recent_release_bonus_days": 90,
    }
}


def _register_app(db, app_id, platform, release_date=None, genre_bucket="match3"):
    upsert_app(
        db, app_id, platform,
        title=f"Game {app_id}", developer="Dev", genre_raw="GAME_PUZZLE",
        genre_bucket=genre_bucket, release_date=release_date,
        icon_url=None, description=None, price_tier="free_iap",
        screenshots_json="[]", store_url=None, last_seen="2026-04-15",
    )
    db.commit()


def test_app_first_seen_within_window_is_new_entrant(db):
    _register_app(db, "com.a", "play", release_date="2026-04-05")
    # first and only appearance on 2026-04-12 (within 14 days of 2026-04-15)
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-12": 150,
        "2026-04-15": 120,
    })
    result = find_new_entrants(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert len(result) == 1
    assert result[0]["app_id"] == "com.a"
    assert result[0]["first_seen_date"] == "2026-04-12"
    assert result[0]["recent_release"] is True  # released 2026-04-05, 10 days before as_of


def test_app_first_seen_before_window_is_not_new(db):
    _register_app(db, "com.a", "play", release_date="2025-01-01")
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-03-01": 180,  # first seen >14 days before 2026-04-15
        "2026-04-15": 150,
    })
    result = find_new_entrants(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert result == []


def test_app_not_currently_charting_is_excluded(db):
    _register_app(db, "com.a", "play", release_date="2026-04-01")
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-10": 180,
        # not present on as_of 2026-04-15
    })
    result = find_new_entrants(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert result == []


def test_ios_uses_100_ceiling_not_200(db):
    _register_app(db, "123", "ios", release_date="2026-04-05")
    # rank 120 is allowed in Play (ceiling 200) but NOT in iOS (ceiling 100)
    seed_ranks(db, "123", "ios", "US", "top_free", {
        "2026-04-12": 120,
        "2026-04-15": 120,
    })
    result = find_new_entrants(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert result == []
