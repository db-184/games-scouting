from src.signals.sustained import find_sustained_climbers
from tests.conftest import seed_ranks

SIGNALS_CFG = {
    "sustained_climber": {
        "min_rising_days_out_of": [5, 7],   # ≥5 of last 7 days rank improved
        "alt_net_gain_threshold": 15,
        "max_reversal_streak": 3,
    }
}


def test_rising_5_of_7_days_qualifies(db):
    # ranks: day-by-day. Lower number = better rank. Improving means current < previous.
    # 7-day series ending 2026-04-15: 90 → 85 → 83 → 80 → 78 → 75 → 73 → 71
    # Improved on 7 out of 7 days (relative to prior day).
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-08": 90, "2026-04-09": 85, "2026-04-10": 83, "2026-04-11": 80,
        "2026-04-12": 78, "2026-04-13": 75, "2026-04-14": 73, "2026-04-15": 71,
    })
    result = find_sustained_climbers(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert len(result) == 1
    assert result[0]["app_id"] == "com.a"


def test_volatile_rise_fails_5_of_7_rule(db):
    # Rises day 1, flat most days, rises day 7 — only 2 rising days
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-08": 90, "2026-04-09": 85, "2026-04-10": 85, "2026-04-11": 85,
        "2026-04-12": 85, "2026-04-13": 85, "2026-04-14": 85, "2026-04-15": 80,
    })
    result = find_sustained_climbers(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert result == []


def test_alt_path_net_gain_15_with_minor_dip_qualifies(db):
    # Net +20 over 7d, dip of 2 days (within max_reversal_streak=3)
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-08": 80, "2026-04-09": 78, "2026-04-10": 80, "2026-04-11": 82,
        "2026-04-12": 75, "2026-04-13": 70, "2026-04-14": 65, "2026-04-15": 60,
    })
    # Net: 80 → 60 = +20. Reversal streak max = 2 (days 10–11). Rising days >= 5 not required here.
    result = find_sustained_climbers(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert any(r["app_id"] == "com.a" for r in result)


def test_long_reversal_disqualifies(db):
    # Net gain but with a 4-day reversal streak — disqualified
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-08": 80, "2026-04-09": 85, "2026-04-10": 88, "2026-04-11": 90,
        "2026-04-12": 92, "2026-04-13": 88, "2026-04-14": 70, "2026-04-15": 60,
    })
    # 4 consecutive days of rising rank numbers (worsening): 09→10→11→12
    result = find_sustained_climbers(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert result == []
