from src.signals.fast_climber import find_fast_climbers
from tests.conftest import seed_ranks

SIGNALS_CFG = {
    "fast_climber": {
        "min_rank_jump": 20,
        "window_days": 7,
        "max_current_rank": 100,
    }
}


def test_climber_with_big_jump_is_found(db):
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-08": 85,
        "2026-04-15": 30,  # +55 jump in 7d, current rank 30 ≤ 100
    })
    result = find_fast_climbers(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert len(result) == 1
    assert result[0]["app_id"] == "com.a"
    assert result[0]["rank_jump"] == 55
    assert result[0]["current_rank"] == 30


def test_small_jump_is_filtered_out(db):
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-08": 50,
        "2026-04-15": 40,  # only +10
    })
    result = find_fast_climbers(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert result == []


def test_game_outside_top_100_is_filtered(db):
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-08": 180,
        "2026-04-15": 150,  # jumped +30 but current rank 150 > 100
    })
    result = find_fast_climbers(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert result == []


def test_multiple_climbers_sorted_by_jump_magnitude(db):
    seed_ranks(db, "com.a", "play", "IN", "top_free", {"2026-04-08": 60, "2026-04-15": 35})   # +25
    seed_ranks(db, "com.b", "play", "IN", "top_free", {"2026-04-08": 90, "2026-04-15": 20})   # +70
    seed_ranks(db, "com.c", "play", "IN", "top_free", {"2026-04-08": 80, "2026-04-15": 40})   # +40
    result = find_fast_climbers(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert [r["app_id"] for r in result] == ["com.b", "com.c", "com.a"]


def test_per_chart_per_country_unique(db):
    # Same app climbing in two countries — each surfaces separately
    seed_ranks(db, "com.a", "play", "IN", "top_free", {"2026-04-08": 60, "2026-04-15": 30})
    seed_ranks(db, "com.a", "play", "BR", "top_free", {"2026-04-08": 70, "2026-04-15": 40})
    result = find_fast_climbers(db, as_of="2026-04-15", config=SIGNALS_CFG)
    countries = sorted(r["country"] for r in result)
    assert countries == ["BR", "IN"]
