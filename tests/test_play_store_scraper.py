import json
from unittest.mock import patch, MagicMock

from src.scrape.play_store import fetch_top_chart, fetch_app_metadata


def _mock_proc(stdout: str, returncode: int = 0, stderr: str = ""):
    return MagicMock(stdout=stdout, stderr=stderr, returncode=returncode)


def test_fetch_top_chart_returns_ranked_app_ids():
    fake_json = json.dumps([
        {"rank": 1, "app_id": "com.a"},
        {"rank": 2, "app_id": "com.b"},
        {"rank": 3, "app_id": "com.c"},
    ])
    with patch("src.scrape.play_store.subprocess.run", return_value=_mock_proc(fake_json)):
        result = fetch_top_chart(country="IN", chart_type="top_free", num=3)
    assert result == [
        {"rank": 1, "app_id": "com.a"},
        {"rank": 2, "app_id": "com.b"},
        {"rank": 3, "app_id": "com.c"},
    ]


def test_fetch_top_chart_empty_result_raises():
    """An empty chart means the scraper is likely broken (spec §9.1, §9.3)."""
    import pytest
    with patch("src.scrape.play_store.subprocess.run", return_value=_mock_proc("[]")):
        with pytest.raises(RuntimeError, match="empty"):
            fetch_top_chart(country="IN", chart_type="top_free", num=200)


def test_fetch_top_chart_node_error_raises():
    import pytest
    with patch("src.scrape.play_store.subprocess.run", return_value=_mock_proc("", returncode=1, stderr="boom")):
        with pytest.raises(RuntimeError, match="fetch failed"):
            fetch_top_chart(country="IN", chart_type="top_free", num=100)


def test_fetch_app_metadata_maps_fields():
    raw = {
        "appId": "com.a",
        "title": "Game A",
        "developer": "Studio X",
        "genreId": "GAME_PUZZLE",
        "genre": "Puzzle",
        "released": "Feb 12, 2026",
        "icon": "https://example.com/icon.png",
        "description": "A puzzle game.",
        "free": True,
        "offersIAP": True,
        "screenshots": ["https://example.com/s1.png"],
        "url": "https://play.google.com/store/apps/details?id=com.a",
        "score": 4.5,
        "ratings": 1234,
    }
    with patch("src.scrape.play_store.gps_app", return_value=raw):
        meta = fetch_app_metadata("com.a", country="IN")
    assert meta["app_id"] == "com.a"
    assert meta["title"] == "Game A"
    assert meta["developer"] == "Studio X"
    assert meta["genre_raw"] == "GAME_PUZZLE"
    assert meta["release_date"] == "2026-02-12"
    assert meta["price_tier"] == "free_iap"
    assert meta["rating_avg"] == 4.5
    assert meta["rating_count"] == 1234
