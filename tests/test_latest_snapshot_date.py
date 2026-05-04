"""Helper that picks `as_of` from DB instead of clock — so weekly reports
work even when today's daily snapshot hasn't run yet (cron skew between
daily UTC-evening and weekly UTC-morning means today's snapshot lags by
one day, leaving fast/new signal queries empty)."""
from datetime import date

from src.jobs.weekly import latest_snapshot_date
from tests.conftest import seed_ranks


def test_latest_snapshot_date_returns_max_date_in_db(db):
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-30": 50, "2026-05-01": 45, "2026-05-03": 40,
    })
    assert latest_snapshot_date(db) == date(2026, 5, 3)


def test_latest_snapshot_date_returns_none_when_db_empty(db):
    assert latest_snapshot_date(db) is None
