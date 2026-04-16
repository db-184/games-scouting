from unittest.mock import patch, MagicMock

from src.scrape.app_store import fetch_top_chart, fetch_app_metadata


def _rss_fixture():
    return {
        "feed": {
            "results": [
                {"id": "111", "name": "Game A"},
                {"id": "222", "name": "Game B"},
                {"id": "333", "name": "Game C"},
            ]
        }
    }


def test_fetch_top_chart_parses_apple_rss():
    mock = MagicMock()
    mock.json.return_value = _rss_fixture()
    mock.raise_for_status.return_value = None
    with patch("src.scrape.app_store.requests.get", return_value=mock):
        result = fetch_top_chart(country="IN", chart_type="top_free", num=3)
    assert result == [
        {"rank": 1, "app_id": "111"},
        {"rank": 2, "app_id": "222"},
        {"rank": 3, "app_id": "333"},
    ]


def test_fetch_top_chart_empty_raises():
    mock = MagicMock()
    mock.json.return_value = {"feed": {"results": []}}
    mock.raise_for_status.return_value = None
    import pytest
    with patch("src.scrape.app_store.requests.get", return_value=mock):
        with pytest.raises(RuntimeError, match="empty"):
            fetch_top_chart(country="IN", chart_type="top_free", num=100)


def test_fetch_app_metadata_maps_itunes_fields():
    itunes_raw = {
        "results": [{
            "trackId": 111,
            "trackName": "Game A",
            "artistName": "Studio X",
            "primaryGenreName": "Games",
            "genres": ["Games", "Puzzle", "Entertainment"],
            "releaseDate": "2026-02-12T00:00:00Z",
            "artworkUrl512": "https://example.com/icon.png",
            "description": "A puzzle game.",
            "price": 0.0,
            "screenshotUrls": ["https://example.com/s1.png"],
            "trackViewUrl": "https://apps.apple.com/app/id111",
            "averageUserRating": 4.5,
            "userRatingCount": 1234,
        }]
    }
    mock = MagicMock()
    mock.json.return_value = itunes_raw
    mock.raise_for_status.return_value = None
    with patch("src.scrape.app_store.requests.get", return_value=mock):
        meta = fetch_app_metadata("111", country="IN")
    assert meta["app_id"] == "111"
    assert meta["title"] == "Game A"
    assert meta["developer"] == "Studio X"
    assert meta["genre_raw"] == "Puzzle"  # first non-"Games" sub-genre
    assert meta["release_date"] == "2026-02-12"
    assert meta["price_tier"] == "free_iap"
    assert meta["rating_count"] == 1234
