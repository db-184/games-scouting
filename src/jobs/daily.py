"""Daily job: scrape all top charts and persist to SQLite.

Policy (spec §9.1):
  - Per-chart retries (3x, exponential backoff) handled here.
  - Single-chart failures are logged, skipped, job continues.
  - If >30% of charts fail overall, exit with non-zero to flag CI red.
  - If >50% of a single platform's charts return 0 results, hard-fail.
"""
from __future__ import annotations

import logging
import sqlite3
import time
from datetime import date
from typing import Any

from src.scrape.app_store import fetch_top_chart as ios_fetch_top_chart, polite_sleep as ios_sleep
from src.scrape.play_store import fetch_top_chart as play_fetch_top_chart, polite_sleep as play_sleep
from src.store.db import upsert_snapshot_row

log = logging.getLogger(__name__)

CHART_TYPES_DEFAULT = ("top_free", "top_grossing", "top_new")


def _fetch_with_retry(fetch_fn, *, attempts: int = 3, backoff: float = 2.0, **kwargs):
    last_exc = None
    for i in range(attempts):
        try:
            return fetch_fn(**kwargs)
        except Exception as e:  # noqa: BLE001
            last_exc = e
            if i < attempts - 1:
                time.sleep(backoff ** i)
    raise last_exc


def run_daily(
    *,
    conn: sqlite3.Connection,
    as_of: date,
    config: dict[str, Any],
    chart_types: tuple[str, ...] = CHART_TYPES_DEFAULT,
) -> dict[str, int]:
    date_str = as_of.isoformat()
    charts_ok = 0
    charts_failed = 0
    platform_empty_count: dict[str, int] = {"play": 0, "ios": 0}
    platform_total_count: dict[str, int] = {"play": 0, "ios": 0}

    plans = []
    for country in config["countries"]["play_store"]:
        for chart_type in chart_types:
            plans.append(("play", country, chart_type))
    for country in config["countries"]["app_store"]:
        for chart_type in chart_types:
            plans.append(("ios", country, chart_type))

    for platform, country, chart_type in plans:
        platform_total_count[platform] += 1
        try:
            fetch_fn = play_fetch_top_chart if platform == "play" else ios_fetch_top_chart
            result = _fetch_with_retry(
                fetch_fn,
                country=country,
                chart_type=chart_type,
                num=200 if platform == "play" else 100,
            )
            for row in result:
                upsert_snapshot_row(conn, date_str, country, platform, chart_type, row["rank"], row["app_id"])
            conn.commit()
            charts_ok += 1
            (play_sleep if platform == "play" else ios_sleep)()
        except RuntimeError as e:
            # Scraper returned empty: signals possible shape-change failure
            log.warning("empty result for %s/%s/%s: %s", platform, country, chart_type, e)
            platform_empty_count[platform] += 1
            charts_failed += 1
        except Exception as e:  # noqa: BLE001
            log.warning("fetch failed for %s/%s/%s: %s", platform, country, chart_type, e)
            charts_failed += 1

    # Spec §9.1: hard-fail if >50% of a platform's charts returned empty
    for platform, empty in platform_empty_count.items():
        total = platform_total_count[platform]
        if total > 0 and empty / total > 0.5:
            raise SystemExit(
                f"[hard-fail] {platform}: {empty}/{total} charts empty — scraper likely broken"
            )

    # Spec §9.1: hard-fail if >30% of charts failed overall
    total_charts = charts_ok + charts_failed
    if total_charts > 0 and charts_failed / total_charts > 0.3:
        raise SystemExit(
            f"[hard-fail] {charts_failed}/{total_charts} charts failed (>30% threshold)"
        )

    log.info("daily done: %d ok, %d failed", charts_ok, charts_failed)
    return {"charts_ok": charts_ok, "charts_failed": charts_failed}


def main() -> None:
    """CLI entry — invoked by GitHub Actions."""
    import yaml
    from pathlib import Path
    from src.config import load_config
    from src.store.db import connect, init_schema

    repo_root = Path(__file__).parent.parent.parent
    from src.logging_setup import configure
    configure(repo_root, "daily")
    config = load_config(repo_root / "config")
    db_path = repo_root / "data" / "scouting.sqlite"
    db_path.parent.mkdir(exist_ok=True)
    conn = connect(db_path)
    init_schema(conn, repo_root / "src" / "store" / "schema.sql")

    cfg_dict = {
        "countries": config.countries,
        "signals": config.signals,
        "genres": config.genres,
    }
    run_daily(conn=conn, as_of=date.today(), config=cfg_dict)


if __name__ == "__main__":
    main()
