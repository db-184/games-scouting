"""Fast Climber signal (spec §3.1).

A game qualifies when:
  - rank improved by ≥ min_rank_jump positions over the last window_days, AND
  - current rank ≤ max_current_rank.

Works per (app, country, platform, chart_type). Same app can surface in multiple charts.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any


def find_fast_climbers(
    conn: sqlite3.Connection,
    *,
    as_of: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    cfg = config["fast_climber"]
    window_days = cfg["window_days"]
    min_jump = cfg["min_rank_jump"]
    max_rank = cfg["max_current_rank"]

    window_start = (date.fromisoformat(as_of) - timedelta(days=window_days)).isoformat()

    rows = conn.execute(
        """
        WITH latest AS (
          SELECT app_id, country, platform, chart_type, rank
          FROM chart_snapshots
          WHERE snapshot_date = ?
        ),
        earlier AS (
          SELECT app_id, country, platform, chart_type, rank
          FROM chart_snapshots
          WHERE snapshot_date = ?
        )
        SELECT
          l.app_id, l.country, l.platform, l.chart_type,
          l.rank AS current_rank,
          e.rank AS previous_rank,
          (e.rank - l.rank) AS rank_jump
        FROM latest l
        JOIN earlier e
          ON l.app_id = e.app_id
         AND l.country = e.country
         AND l.platform = e.platform
         AND l.chart_type = e.chart_type
        WHERE (e.rank - l.rank) >= ?
          AND l.rank <= ?
        ORDER BY rank_jump DESC
        """,
        (as_of, window_start, min_jump, max_rank),
    ).fetchall()

    return [dict(r) for r in rows]
