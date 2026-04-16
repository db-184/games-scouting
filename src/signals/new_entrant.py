"""New Entrant signal (spec §3.2).

A game qualifies when:
  - it first appeared in the chart within the last `max_window_days`, AND
  - it is still charting on `as_of`, AND
  - it is within the platform's chart ceiling.

The `recent_release` boolean flags games whose release_date is within
`recent_release_bonus_days` — used for extra weighting in the report.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any


def find_new_entrants(
    conn: sqlite3.Connection,
    *,
    as_of: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    cfg = config["new_entrant"]
    window_days = cfg["max_window_days"]
    play_ceiling = cfg["play_store_chart_ceiling"]
    ios_ceiling = cfg["app_store_chart_ceiling"]
    release_bonus = cfg["recent_release_bonus_days"]

    as_of_d = date.fromisoformat(as_of)
    window_start = (as_of_d - timedelta(days=window_days)).isoformat()
    release_bonus_cutoff = (as_of_d - timedelta(days=release_bonus)).isoformat()

    rows = conn.execute(
        """
        WITH first_seen AS (
          SELECT app_id, country, platform, chart_type, MIN(snapshot_date) AS first_seen_date
          FROM chart_snapshots
          GROUP BY app_id, country, platform, chart_type
        ),
        current_rank AS (
          SELECT app_id, country, platform, chart_type, rank
          FROM chart_snapshots
          WHERE snapshot_date = ?
        )
        SELECT
          cr.app_id, cr.country, cr.platform, cr.chart_type, cr.rank AS current_rank,
          fs.first_seen_date,
          a.release_date,
          (a.release_date IS NOT NULL AND a.release_date >= ?) AS recent_release
        FROM current_rank cr
        JOIN first_seen fs
          ON cr.app_id = fs.app_id
         AND cr.country = fs.country
         AND cr.platform = fs.platform
         AND cr.chart_type = fs.chart_type
        LEFT JOIN apps a
          ON cr.app_id = a.app_id AND cr.platform = a.platform
        WHERE fs.first_seen_date >= ?
          AND (
            (cr.platform = 'play' AND cr.rank <= ?)
            OR (cr.platform = 'ios' AND cr.rank <= ?)
          )
        ORDER BY fs.first_seen_date DESC, cr.rank ASC
        """,
        (as_of, release_bonus_cutoff, window_start, play_ceiling, ios_ceiling),
    ).fetchall()

    return [dict(r) | {"recent_release": bool(r["recent_release"])} for r in rows]
