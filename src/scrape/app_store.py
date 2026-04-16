"""App Store scraping via Apple's iTunes RSS (legacy) and iTunes Search API.

The modern `rss.applemarketingtools.com` API lists all top apps without a
genre filter — it would surface TurboTax, ChatGPT, etc. in our "top games"
list. The older `itunes.apple.com/{country}/rss/...` endpoints still work
and support a `genre=6014` filter for Games. This module uses the legacy
URL for that reason; if Apple turns it off we'll need to migrate to filtering
top-apps output via per-app iTunes lookups (expensive, ~8000 extra calls/day).

Both endpoints are free and no key is required.
"""
from __future__ import annotations

import json
import time
from typing import Any

import requests

RSS_BASE = "https://itunes.apple.com"
ITUNES_LOOKUP = "https://itunes.apple.com/lookup"
GAMES_GENRE_ID = 6014

CHART_RSS_MAP = {
    "top_free": "topfreeapplications",
    "top_grossing": "topgrossingapplications",
    "top_new": "newapplications",
}

REQUEST_TIMEOUT = 20
USER_AGENT = "games-scouting-agent/0.1"


def fetch_top_chart(country: str, chart_type: str, num: int = 100) -> list[dict[str, Any]]:
    feed_slug = CHART_RSS_MAP[chart_type]
    url = (
        f"{RSS_BASE}/{country.lower()}/rss/{feed_slug}/"
        f"limit={num}/genre={GAMES_GENRE_ID}/json"
    )
    resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    data = resp.json()
    entries = data.get("feed", {}).get("entry", [])
    if not entries:
        raise RuntimeError(f"App Store returned empty result for {country}/{chart_type}")
    return [
        {"rank": i + 1, "app_id": entry["id"]["attributes"]["im:id"]}
        for i, entry in enumerate(entries)
    ]


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
    return date_str[:10]


def polite_sleep(seconds: float = 0.2) -> None:
    time.sleep(seconds)
