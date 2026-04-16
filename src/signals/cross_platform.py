"""Fuzzy cross-platform matching: does the same game appear on Play and iOS?

Matching is lenient on minor differences (casing, punctuation, trailing "HD"/"Free")
but requires both title AND developer to agree above thresholds.

Uses only stdlib (difflib) to avoid adding dependencies.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

TITLE_THRESHOLD = 0.85
DEV_THRESHOLD = 0.85


def _normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\b(hd|free|lite|premium)\b", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def match_cross_platform(candidates: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Return pairs of (play_app_id, ios_app_id) that appear to be the same game."""
    play = [c for c in candidates if c["platform"] == "play"]
    ios = [c for c in candidates if c["platform"] == "ios"]
    pairs: list[tuple[str, str]] = []
    for p in play:
        for i in ios:
            if (_similar(p["title"], i["title"]) >= TITLE_THRESHOLD
                and _similar(p.get("developer") or "", i.get("developer") or "") >= DEV_THRESHOLD):
                pairs.append((p["app_id"], i["app_id"]))
    return pairs
