"""For each app that qualified for a signal, fetch fresh metadata and update the apps table.

Tolerant of per-app failures — one bad lookup shouldn't break the whole report.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Any

from src.genre_filter import classify_bucket
from src.scrape.app_store import fetch_app_metadata as ios_fetch_app_metadata
from src.scrape.play_store import fetch_app_metadata as play_fetch_app_metadata
from src.store.db import upsert_app, upsert_rating_snapshot

log = logging.getLogger(__name__)


def enrich_qualifying_apps(
    conn: sqlite3.Connection,
    candidates: list[dict[str, Any]],
    *,
    as_of: str,
    genres_cfg: dict[str, Any],
    country_for_lookup: str = "US",  # iTunes metadata varies slightly by country; US is stable
) -> None:
    seen: set[tuple[str, str]] = set()
    for c in candidates:
        key = (c["app_id"], c["platform"])
        if key in seen:
            continue
        seen.add(key)

        try:
            if c["platform"] == "play":
                meta = play_fetch_app_metadata(c["app_id"], country=country_for_lookup)
            else:
                meta = ios_fetch_app_metadata(c["app_id"], country=country_for_lookup)
        except Exception as e:
            log.warning("metadata fetch failed for %s/%s: %s", c["platform"], c["app_id"], e)
            continue

        bucket = classify_bucket(
            platform=c["platform"],
            genre_raw=meta.get("genre_raw"),
            title=meta.get("title", ""),
            description=meta.get("description"),
            genres_cfg=genres_cfg,
        )

        upsert_app(
            conn,
            app_id=c["app_id"],
            platform=c["platform"],
            title=meta["title"],
            developer=meta.get("developer"),
            genre_raw=meta.get("genre_raw"),
            genre_bucket=bucket,
            release_date=meta.get("release_date"),
            icon_url=meta.get("icon_url"),
            description=meta.get("description"),
            price_tier=meta.get("price_tier"),
            screenshots_json=meta.get("screenshots_json"),
            store_url=meta.get("store_url"),
            last_seen=as_of,
        )
        upsert_rating_snapshot(
            conn,
            snapshot_date=as_of,
            app_id=c["app_id"],
            platform=c["platform"],
            rating_avg=meta.get("rating_avg"),
            rating_count=meta.get("rating_count"),
        )
    conn.commit()
