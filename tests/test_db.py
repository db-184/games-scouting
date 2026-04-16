from pathlib import Path
import sqlite3

from src.store.db import connect, init_schema, upsert_snapshot_row, fetch_snapshots_for_app

SCHEMA_PATH = Path(__file__).parent.parent / "src" / "store" / "schema.sql"


def test_init_creates_tables(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = connect(db_path)
    init_schema(conn, SCHEMA_PATH)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"chart_snapshots", "apps", "app_ratings_history"} <= tables


def test_upsert_snapshot_and_fetch(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = connect(db_path)
    init_schema(conn, SCHEMA_PATH)

    upsert_snapshot_row(conn, "2026-04-01", "IN", "play", "top_free", 10, "com.example.game")
    upsert_snapshot_row(conn, "2026-04-02", "IN", "play", "top_free", 8,  "com.example.game")
    conn.commit()

    rows = fetch_snapshots_for_app(conn, "com.example.game", since="2026-03-25")
    assert len(rows) == 2
    ranks = [r["rank"] for r in rows]
    assert ranks == [10, 8]


def test_upsert_is_idempotent(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = connect(db_path)
    init_schema(conn, SCHEMA_PATH)
    for _ in range(2):
        upsert_snapshot_row(conn, "2026-04-01", "IN", "play", "top_free", 10, "com.example.game")
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM chart_snapshots").fetchone()[0]
    assert count == 1
