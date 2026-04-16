"""Smoke tests using recorded HTTP fixtures via vcrpy.

First run (online, locally): records fresh cassettes from real APIs into tests/fixtures/cassettes/.
Subsequent runs (offline or CI): replay cassettes, detect shape changes.

To refresh a cassette after an API change:
    rm tests/fixtures/cassettes/<name>.yaml
    pytest tests/test_scrape_smoke.py  # will re-record

In CI (env CI=true), record_mode is 'none' so a missing cassette or shape change fails
loudly instead of silently re-recording against live APIs.

Scope:
  - iOS scrapers go through Python requests → vcrpy intercepts normally.
  - Play Store scraper goes through a Node.js subprocess (scripts/fetch_play_chart.mjs) →
    vcrpy cannot intercept. Python-level unit tests in test_play_store_scraper.py already
    cover the shape of subprocess.run output at the Python boundary.
"""
import os
from pathlib import Path

import vcr

from src.scrape.app_store import (
    fetch_app_metadata as ios_meta,
    fetch_top_chart as ios_fetch_top,
)

CASSETTE_DIR = Path(__file__).parent / "fixtures" / "cassettes"

# In CI, never re-record — we want failures if the API shape changed.
# Locally, allow recording when a cassette is missing.
record_mode = "none" if os.environ.get("CI") else "once"

my_vcr = vcr.VCR(
    cassette_library_dir=str(CASSETTE_DIR),
    record_mode=record_mode,
    match_on=["method", "scheme", "host", "port", "path", "query"],
    filter_headers=["authorization", "cookie"],
)


@my_vcr.use_cassette("ios_top_free_us.yaml")
def test_ios_top_free_us_returns_games():
    """Legacy iTunes RSS with genre=6014. Should return 100 ranked game IDs."""
    result = ios_fetch_top(country="US", chart_type="top_free", num=100)
    assert len(result) == 100
    assert all("rank" in r and "app_id" in r for r in result)
    # First rank must always be 1
    assert result[0]["rank"] == 1


@my_vcr.use_cassette("ios_metadata_sample.yaml")
def test_ios_metadata_has_required_fields():
    """iTunes Search API lookup for a stable long-lived iOS game.

    Minecraft iOS (id 479516143) — chosen for longevity. If Mojang/Microsoft ever
    pulls it from the store, any stable popular iOS game ID works. The cassette
    captures the response; shape drift (renamed fields) will surface here.
    """
    meta = ios_meta("479516143", country="US")
    required = {
        "app_id", "platform", "title", "developer", "genre_raw",
        "release_date", "icon_url", "description", "price_tier",
        "screenshots_json", "store_url", "rating_avg", "rating_count",
    }
    assert required <= meta.keys()
    # Sanity: the scraper must at least return the app_id it was asked for
    assert meta["app_id"] == "479516143"
    assert meta["platform"] == "ios"
    # Title should be non-empty for a real record
    assert meta["title"]
