"""App Store scraping via Apple's official RSS marketing feeds and iTunes Search API.

Both endpoints are free, no key required, and officially sanctioned for consumer use.
"""
from __future__ import annotations

import json
import time
from typing import Any

import requests

RSS_BASE = "https://rss.applemarketingtools.com/api/v2"
ITUNES_LOOKUP = "https://itunes.apple.com/lookup"

CHART_RSS_MAP = {
    "top_free": "top-free",
    "top_grossing": "top-grossing",
    "top_new": "top-free",  # Apple RSS has no dedicated "new games" feed — see play_store.py note
}

REQUEST_TIMEOUT = 20
USER_AGENT = "games-scouting-agent/0.1"


def fetch_top_chart(country: str, chart_type: str, num: int = 100) -> list[dict[str, Any]]:
    feed_slug = CHART_RSS_MAP[chart_type]
    url = f"{RSS_BASE}/{country.lower()}/apps/{feed_slug}/{num}/games.json"
    resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    data = resp.json()
    results = data.get("feed", {}).get("results", [])
    if not results:
        raise RuntimeError(f"App Store returned empty result for {country}/{chart_type}")
    return [{"rank": i + 1, "app_id": row["id"]} for i, row in enumerate(results)]


def fetch_app_metadata(app_id: str, country: str) -> dict[str, Any]:
    params = {"id": app_id, "country": country.lower(), "entity": "software"}
    resp = requests.get(
        ITUNES_LOOKUP,
        params=params,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("results"):
        raise RuntimeError(f"iTunes lookup returned no result for id={app_id} country={country}")
    raw = data["results"][0]
    return {
        "app_id": app_id,
        "platform": "ios",
        "title": raw.get("trackName", ""),
        "developer": raw.get("artistName"),
        "genre_raw": _primary_sub_genre(raw),
        "release_date": _parse_itunes_date(raw.get("releaseDate")),
        "icon_url": raw.get("artworkUrl512") or raw.get("artworkUrl100"),
        "description": raw.get("description"),
        "price_tier": "paid" if raw.get("price", 0) > 0 else "free_iap",
        "screenshots_json": json.dumps((raw.get("screenshotUrls") or [])[:3]),
        "store_url": raw.get("trackViewUrl"),
        "rating_avg": raw.get("averageUserRating"),
        "rating_count": raw.get("userRatingCount"),
    }


def _primary_sub_genre(raw: dict[str, Any]) -> str | None:
    genres = raw.get("genres") or []
    for g in genres:
        if g != "Games":
            return g
    return raw.get("primaryGenreName")


def _parse_itunes_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    # Format: "2026-02-12T00:00:00Z" — just take the date part
    return date_str[:10]


def polite_sleep(seconds: float = 0.2) -> None:
    time.sleep(seconds)
