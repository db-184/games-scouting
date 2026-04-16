"""Play Store scraping.

Top charts come from the npm google-play-scraper library via subprocess — the Python
port only supports app() / search() / reviews(), not list() / collection.
App metadata uses the Python library directly (app() does work there).

The node helper lives at scripts/fetch_play_chart.mjs and outputs ranked JSON to stdout.
Note: google-play-scraper v10 is ESM-only ("type": "module"), so the script uses
.mjs extension and ES import syntax instead of require().
"""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from google_play_scraper import app as gps_app

REPO_ROOT = Path(__file__).parent.parent.parent
PLAY_CHART_SCRIPT = REPO_ROOT / "scripts" / "fetch_play_chart.mjs"
FETCH_TIMEOUT_SECONDS = 60


def fetch_top_chart(country: str, chart_type: str, num: int = 200) -> list[dict[str, Any]]:
    proc = subprocess.run(
        ["node", str(PLAY_CHART_SCRIPT), country, chart_type, str(num)],
        capture_output=True,
        text=True,
        timeout=FETCH_TIMEOUT_SECONDS,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Play Store fetch failed ({country}/{chart_type}): {proc.stderr.strip()}"
        )
    data = json.loads(proc.stdout)
    if not data:
        raise RuntimeError(f"Play Store returned empty result for {country}/{chart_type}")
    return data


def fetch_app_metadata(app_id: str, country: str) -> dict[str, Any]:
    raw = gps_app(app_id, country=country.lower(), lang="en")
    return {
        "app_id": app_id,
        "platform": "play",
        "title": raw.get("title", ""),
        "developer": raw.get("developer"),
        "genre_raw": raw.get("genreId"),
        "release_date": _parse_play_date(raw.get("released")),
        "icon_url": raw.get("icon"),
        "description": raw.get("description"),
        "price_tier": _price_tier(raw),
        "screenshots_json": json.dumps(raw.get("screenshots", [])[:3]),
        "store_url": raw.get("url"),
        "rating_avg": raw.get("score"),
        "rating_count": raw.get("ratings"),
    }


def _parse_play_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%b %d, %Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _price_tier(raw: dict[str, Any]) -> str:
    if not raw.get("free", True):
        return "paid"
    return "free_iap"


def polite_sleep(seconds: float = 0.2) -> None:
    time.sleep(seconds)
