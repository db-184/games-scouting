from unittest.mock import patch
from datetime import date

from src.jobs.daily import run_daily


def test_run_daily_handles_per_chart_failure_without_aborting(db, tmp_path):
    """One failing chart should be logged and skipped; others should still persist.

    NOTE: The test uses play_store=["IN", "BR", "US"] and app_store=["IN", "US"]
    so that 1 failure out of 5 total charts = 20% < 30% threshold (spec §9.1).
    The original plan used ["IN", "BR"] / ["IN"] giving 1/3 = 33% which would
    trip the hard-fail; this adjustment avoids that plan bug without changing
    production thresholds.
    """
    good_result = [{"rank": 1, "app_id": "com.good"}, {"rank": 2, "app_id": "com.good2"}]

    def play_side_effect(country, chart_type, num):
        if country == "BR":
            raise RuntimeError("Play scraper broke for BR")
        return good_result

    with patch("src.jobs.daily.play_fetch_top_chart", side_effect=play_side_effect), \
         patch("src.jobs.daily.ios_fetch_top_chart", return_value=good_result):
        config = {
            "countries": {"play_store": ["IN", "BR", "US"], "app_store": ["IN", "US"]},
            "signals": {},  # not used by daily
            "genres": {},
        }
        stats = run_daily(
            conn=db,
            as_of=date(2026, 4, 15),
            config=config,
            chart_types=("top_free",),
        )

    rows = db.execute("SELECT COUNT(*) FROM chart_snapshots").fetchone()[0]
    # 2 successful Play (IN, US) × 2 games + 1 failed Play (BR) × 0 + 2 iOS (IN, US) × 2 = 8
    assert rows == 8
    assert stats["charts_ok"] == 4
    assert stats["charts_failed"] == 1
