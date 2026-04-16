"""Combines the three signal outputs into report sections with priority-based dedup.

Priority (spec §3.5): sustained > fast > new.
A game appearing in multiple lists is placed only in its highest-priority section.
Within each section, items are sorted by the caller (by score) and truncated to max_per_section.
"""
from __future__ import annotations

from typing import Any


def compose_sections(
    *,
    fast: list[dict[str, Any]],
    new: list[dict[str, Any]],
    sustained: list[dict[str, Any]],
    max_per_section: int,
) -> dict[str, list[dict[str, Any]]]:
    seen: set[tuple[str, str]] = set()  # (app_id, platform)

    def _claim(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for item in items:
            key = (item["app_id"], item["platform"])
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
            if len(out) >= max_per_section:
                break
        return out

    # Claim in priority order
    sustained_out = _claim(sustained)
    fast_out = _claim(fast)
    new_out = _claim(new)

    return {
        "sustained": sustained_out,
        "fast": fast_out,
        "new": new_out,
    }
