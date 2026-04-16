from datetime import date
from pathlib import Path

from src.report.render import build_game_view, render_weekly, render_archive


def test_build_game_view_combines_signal_and_app_fields():
    app_row = {
        "app_id": "com.a", "platform": "play", "title": "Game A", "developer": "Studio X",
        "genre_bucket": "match3", "genre_raw": "GAME_PUZZLE", "release_date": "2026-04-01",
        "icon_url": "u", "description": "A match-3 puzzle game with cute graphics and a long story.",
        "price_tier": "free_iap", "screenshots": '["s1", "s2"]',
        "store_url": "https://play/",
    }
    signal_hit = {
        "app_id": "com.a", "platform": "play", "country": "IN",
        "signal": "sustained", "current_rank": 30, "rank_start": 84, "net_gain": 54,
    }
    ratings_current = {"rating_avg": 4.6, "rating_count": 12800}
    ratings_last_week = {"rating_count": 9600}

    view = build_game_view(
        app_row=app_row,
        signal_hit=signal_hit,
        ratings_current=ratings_current,
        ratings_last_week=ratings_last_week,
        cross_platform=False,
    )
    assert view["title"] == "Game A"
    assert view["signal_label"].startswith("Sustained")
    assert view["rating_count_delta"] == 3200
    assert view["screenshots"] == ["s1", "s2"]
    assert view["play_url"] == "https://play/"


def test_render_weekly_writes_html(tmp_path):
    sections = {"sustained": [], "fast": [], "new": []}
    out = render_weekly(
        out_dir=tmp_path,
        report_date=date(2026, 4, 20),
        sections=sections,
        cross_platform_games=[],
        totals={"sustained": 0, "fast": 0, "new": 0, "cross_platform": 0},
        heartbeat={"snapshots_this_week": 7},
        cold_start=None,
    )
    html = Path(out).read_text()
    assert "Sustained Climbers" in html
    assert "No games in this category" in html


def test_render_archive_lists_reports(tmp_path):
    reports = [
        {"slug": "2026-04-20", "date": "2026-04-20", "totals": {"sustained": 2, "fast": 1, "new": 3, "cross_platform": 0}},
        {"slug": "2026-04-13", "date": "2026-04-13", "totals": {"sustained": 0, "fast": 0, "new": 1, "cross_platform": 0}},
    ]
    path = render_archive(out_dir=tmp_path, reports=reports)
    html = Path(path).read_text()
    assert "2026-04-20" in html
    assert "2026-04-13" in html
