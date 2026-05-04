"""End-to-end test for weekly job: seed DB, run job, verify HTML + Slack were produced."""
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.jobs.weekly import run_weekly
from src.store.db import upsert_app, upsert_rating_snapshot
from tests.conftest import seed_ranks


def test_run_weekly_produces_html_and_slack(db, tmp_path):
    upsert_app(
        db, "com.a", "play",
        title="Merge Farm", developer="Studio X",
        genre_raw="GAME_SIMULATION", genre_bucket="casual_sim",
        release_date="2026-03-01", icon_url="u",
        description="merge farming tycoon game", price_tier="free_iap",
        screenshots_json="[]", store_url="https://play/",
        last_seen="2026-04-15",
    )
    upsert_rating_snapshot(db, "2026-04-15", "com.a", "play", 4.5, 10000)
    db.commit()

    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-08": 90, "2026-04-09": 85, "2026-04-10": 80,
        "2026-04-11": 75, "2026-04-12": 70, "2026-04-13": 65,
        "2026-04-14": 60, "2026-04-15": 55,
    })

    config = {
        "countries": {"play_store": ["IN"], "app_store": []},
        "signals": {
            "fast_climber": {"min_rank_jump": 20, "window_days": 7, "max_current_rank": 100},
            "new_entrant": {"max_window_days": 14, "play_store_chart_ceiling": 200,
                            "app_store_chart_ceiling": 100, "recent_release_bonus_days": 90},
            "sustained_climber": {"min_rising_days_out_of": [5, 7], "alt_net_gain_threshold": 15,
                                  "max_reversal_streak": 3},
            "report": {"max_games_per_section": 10},
        },
        "genres": {
            "play_store": {"GAME_SIMULATION": "casual_sim"},
            "app_store": {},
            "keyword_overrides": {"hybrid_casual": ["merge", "tycoon"]},
        },
    }

    with patch("src.jobs.weekly.enrich_qualifying_apps") as mock_enrich, \
         patch("src.jobs.weekly.post_headline") as mock_slack:
        mock_enrich.return_value = None
        result = run_weekly(
            conn=db,
            as_of=date(2026, 4, 15),
            config=config,
            out_dir=tmp_path,
            base_url="https://u.github.io/gs",
            slack_webhook_url="https://hooks.slack.com/fake",
        )

    report_html = tmp_path / "2026-04-15" / "index.html"
    assert report_html.exists()
    assert "Merge Farm" in report_html.read_text()
    assert (tmp_path / "index.html").exists()
    assert mock_slack.call_count == 1
    assert result["totals"]["sustained"] >= 1


def test_run_weekly_oversamples_past_out_of_scope_genres(db, tmp_path):
    # Both apps are fast climbers in the same chart; com.action ranks #1 by score
    # but is in a non-watchlist genre. Without oversample, the section would be empty
    # after genre filtering. With oversample_factor=2 and max_per_section=1, the watchlist
    # game should fill the slot.
    upsert_app(
        db, "com.action", "play",
        title="Combat Royale", developer="StudioA", genre_raw="GAME_ACTION",
        genre_bucket=None,  # non-watchlist
        release_date="2026-01-01", icon_url="u", description="action shooter",
        price_tier="free_iap", screenshots_json="[]", store_url="https://play/",
        last_seen="2026-04-15",
    )
    upsert_app(
        db, "com.match", "play",
        title="Match Pop", developer="StudioM", genre_raw="GAME_PUZZLE",
        genre_bucket="match3",
        release_date="2026-01-01", icon_url="u", description="match 3 puzzle",
        price_tier="free_iap", screenshots_json="[]", store_url="https://play/",
        last_seen="2026-04-15",
    )
    db.commit()
    # com.action: rank_jump 50, com.match: rank_jump 30 — both qualify, action ranked higher
    seed_ranks(db, "com.action", "play", "IN", "top_free", {
        "2026-04-08": 60, "2026-04-15": 10,
    })
    seed_ranks(db, "com.match", "play", "IN", "top_free", {
        "2026-04-08": 40, "2026-04-15": 10,
    })

    config = {
        "countries": {"play_store": ["IN"], "app_store": []},
        "signals": {
            "fast_climber": {"min_rank_jump": 20, "window_days": 7, "max_current_rank": 100},
            "new_entrant": {"max_window_days": 14, "play_store_chart_ceiling": 200,
                            "app_store_chart_ceiling": 100, "recent_release_bonus_days": 90},
            "sustained_climber": {"min_rising_days_out_of": [5, 7], "alt_net_gain_threshold": 999,
                                  "max_reversal_streak": 3},  # disable sustained
            "report": {"max_games_per_section": 1, "oversample_factor": 2},
        },
        "genres": {"play_store": {}, "app_store": {}, "keyword_overrides": {}},
    }

    with patch("src.jobs.weekly.enrich_qualifying_apps") as mock_enrich, \
         patch("src.jobs.weekly.post_headline"):
        mock_enrich.return_value = None
        result = run_weekly(
            conn=db, as_of=date(2026, 4, 15), config=config,
            out_dir=tmp_path, base_url="https://x", slack_webhook_url="https://hook",
        )

    assert result["totals"]["fast"] == 1, "section should fill from oversample, not stay empty"
