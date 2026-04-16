"""Shared test fixtures: in-memory SQLite with schema applied + helper to seed snapshots."""
from pathlib import Path

import pytest

from src.store.db import connect, init_schema, upsert_snapshot_row

SCHEMA_PATH = Path(__file__).parent.parent / "src" / "store" / "schema.sql"


@pytest.fixture
def db(tmp_path):
    conn = connect(tmp_path / "test.sqlite")
    init_schema(conn, SCHEMA_PATH)
    return conn


def seed_ranks(conn, app_id: str, platform: str, country: str, chart_type: str, ranks_by_date: dict[str, int]):
    """Insert a series of (date -> rank) snapshots for one app in one chart."""
    for date, rank in ranks_by_date.items():
        upsert_snapshot_row(conn, date, country, platform, chart_type, rank, app_id)
    conn.commit()
