"""Sustained Climber signal (spec §3.3).

Qualifies if EITHER:
  A. Rank improved on ≥ min_rising_days of the last window_days, OR
  B. Net gain ≥ alt_net_gain_threshold over the window AND no reversal streak > max_reversal_streak

This signal is the strongest publishing indicator — it filters out paid-UA spikes.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any


def find_sustained_climbers(
    conn: sqlite3.Connection,
    *,
    as_of: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    cfg = config["sustained_climber"]
    min_rising, window_days = cfg["min_rising_days_out_of"]
    alt_net_gain = cfg["alt_net_gain_threshold"]
    max_reversal = cfg["max_reversal_streak"]

    as_of_d = date.fromisoformat(as_of)
    window_start = (as_of_d - timedelta(days=window_days)).isoformat()

    # Fetch all (app_id, country, platform, chart_type) series that have snapshots in the window.
    rows = conn.execute(
        """
        SELECT app_id, country, platform, chart_type, snapshot_date, rank
        FROM chart_snapshots
        WHERE snapshot_date >= ? AND snapshot_date <= ?
        ORDER BY app_id, country, platform, chart_type, snapshot_date
        """,
        (window_start, as_of),
    ).fetchall()

    # Group by series
    series: dict[tuple, list[tuple[str, int]]] = {}
    for r in rows:
        key = (r["app_id"], r["country"], r["platform"], r["chart_type"])
        series.setdefault(key, []).append((r["snapshot_date"], r["rank"]))

    results = []
    for (app_id, country, platform, chart_type), points in series.items():
        if len(points) < 2:
            continue

        ranks = [p[1] for p in points]
        # Day-over-day deltas: lower rank = improvement, so delta = previous - current (positive = improved)
        deltas = [ranks[i - 1] - ranks[i] for i in range(1, len(ranks))]

        rising_days = sum(1 for d in deltas if d > 0)
        net_gain = ranks[0] - ranks[-1]

        # Longest consecutive streak of worsening days
        max_streak = 0
        streak = 0
        for d in deltas:
            if d < 0:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0

        path_a = rising_days >= min_rising
        path_b = net_gain >= alt_net_gain and max_streak <= max_reversal

        if path_a or path_b:
            results.append({
                "app_id": app_id,
                "country": country,
                "platform": platform,
                "chart_type": chart_type,
                "current_rank": ranks[-1],
                "rank_start": ranks[0],
                "net_gain": net_gain,
                "rising_days": rising_days,
                "max_reversal_streak": max_streak,
            })

    # Sort by net_gain descending
    results.sort(key=lambda r: r["net_gain"], reverse=True)
    return results
