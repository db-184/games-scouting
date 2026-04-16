"""SQLite access layer. Thin, no ORM."""
from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection, schema_path: Path) -> None:
    conn.executescript(schema_path.read_text())
    conn.commit()


def upsert_snapshot_row(
    conn: sqlite3.Connection,
    snapshot_date: str,
    country: str,
    platform: str,
    chart_type: str,
    rank: int,
    app_id: str,
) -> None:
    conn.execute(
        """
        INSERT INTO chart_snapshots (snapshot_date, country, platform, chart_type, rank, app_id)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(snapshot_date, country, platform, chart_type, app_id) DO UPDATE SET
            rank = excluded.rank
        """,
        (snapshot_date, country, platform, chart_type, rank, app_id),
    )


def fetch_snapshots_for_app(
    conn: sqlite3.Connection,
    app_id: str,
    since: str,
) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT snapshot_date, country, platform, chart_type, rank
            FROM chart_snapshots
            WHERE app_id = ? AND snapshot_date >= ?
            ORDER BY snapshot_date ASC
            """,
            (app_id, since),
        )
    )


def upsert_app(
    conn: sqlite3.Connection,
    app_id: str,
    platform: str,
    *,
    title: str,
    developer: str | None,
    genre_raw: str | None,
    genre_bucket: str | None,
    release_date: str | None,
    icon_url: str | None,
    description: str | None,
    price_tier: str | None,
    screenshots_json: str | None,
    store_url: str | None,
    last_seen: str,
) -> None:
    conn.execute(
        """
        INSERT INTO apps (app_id, platform, title, developer, genre_raw, genre_bucket,
                          release_date, icon_url, description, price_tier, screenshots,
                          store_url, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(app_id, platform) DO UPDATE SET
            title        = excluded.title,
            developer    = excluded.developer,
            genre_raw    = excluded.genre_raw,
            genre_bucket = excluded.genre_bucket,
            release_date = excluded.release_date,
            icon_url     = excluded.icon_url,
            description  = excluded.description,
            price_tier   = excluded.price_tier,
            screenshots  = excluded.screenshots,
            store_url    = excluded.store_url,
            last_seen    = excluded.last_seen
        """,
        (
            app_id, platform, title, developer, genre_raw, genre_bucket,
            release_date, icon_url, description, price_tier, screenshots_json,
            store_url, last_seen,
        ),
    )


def upsert_rating_snapshot(
    conn: sqlite3.Connection,
    snapshot_date: str,
    app_id: str,
    platform: str,
    rating_avg: float | None,
    rating_count: int | None,
) -> None:
    conn.execute(
        """
        INSERT INTO app_ratings_history (snapshot_date, app_id, platform, rating_avg, rating_count)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(snapshot_date, app_id, platform) DO UPDATE SET
            rating_avg   = excluded.rating_avg,
            rating_count = excluded.rating_count
        """,
        (snapshot_date, app_id, platform, rating_avg, rating_count),
    )
