"""Maps raw store-genre strings to watchlist buckets.

Strategy:
1. Look up the raw genre in the store's genre map → base bucket (or None).
2. Scan title + description for keyword overrides. An override "upgrades" or sets the bucket.
   Rationale: both stores categorize "hypercasual" and "hybrid-casual" inconsistently
   (everything lands in "Arcade" or "Casual"); keywords are a second pass.

Returns the bucket name (e.g., "match3") or None if the game should be excluded from the report.
"""
from __future__ import annotations

from typing import Any


def classify_bucket(
    *,
    platform: str,  # "play" | "ios"
    genre_raw: str | None,
    title: str,
    description: str | None,
    genres_cfg: dict[str, Any],
) -> str | None:
    store_key = "play_store" if platform == "play" else "app_store"
    base = genres_cfg.get(store_key, {}).get(genre_raw) if genre_raw else None

    haystack = f"{title or ''} {description or ''}".lower()

    # Keyword overrides win over store-genre base mapping, because store genres
    # lump hybrid-casual into casual/arcade buckets.
    for bucket, keywords in (genres_cfg.get("keyword_overrides") or {}).items():
        for kw in keywords:
            if kw.lower() in haystack:
                return bucket

    return base
