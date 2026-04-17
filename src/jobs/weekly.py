"""Weekly job: compute signals, enrich, render HTML, post Slack headline."""
from __future__ import annotations

import logging
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.report.render import build_game_view, render_archive, render_weekly
from src.report.slack import compose_headline, post_headline
from src.signals.compose import compose_sections
from src.signals.cross_platform import match_cross_platform
from src.signals.enrich import enrich_qualifying_apps
from src.signals.fast_climber import find_fast_climbers
from src.signals.new_entrant import find_new_entrants
from src.signals.sustained import find_sustained_climbers

log = logging.getLogger(__name__)


def run_weekly(
    *,
    conn: sqlite3.Connection,
    as_of: date,
    config: dict[str, Any],
    out_dir: Path,
    base_url: str,  # e.g. "https://user.github.io/games-scouting"
    slack_webhook_url: str | None,
) -> dict[str, Any]:
    as_of_str = as_of.isoformat()

    # 1. Compute raw signal hits
    fast_hits = [_tag(h, "fast", score=h["rank_jump"]) for h in find_fast_climbers(conn, as_of=as_of_str, config=config["signals"])]
    new_hits = [_tag(h, "new", score=-h["current_rank"]) for h in find_new_entrants(conn, as_of=as_of_str, config=config["signals"])]
    sustained_hits = [_tag(h, "sustained", score=h["net_gain"]) for h in find_sustained_climbers(conn, as_of=as_of_str, config=config["signals"])]

    # 2. Compose sections with priority dedup
    max_per = config["signals"]["report"]["max_games_per_section"]
    sections_raw = compose_sections(
        fast=fast_hits, new=new_hits, sustained=sustained_hits, max_per_section=max_per,
    )

    # 3. Enrich all qualifying apps (fetch fresh metadata + ratings + genre classification)
    qualifying = [item for items in sections_raw.values() for item in items]
    enrich_qualifying_apps(conn, qualifying, as_of=as_of_str, genres_cfg=config["genres"])

    # 4. Filter by watchlist genre: a qualifying app without a matching genre_bucket is excluded
    sections_filtered = {k: _filter_by_genre(conn, items) for k, items in sections_raw.items()}

    # 5. Build cross-platform matches from the enriched candidate set
    enriched_rows = conn.execute(
        "SELECT app_id, platform, title, developer FROM apps WHERE last_seen = ?", (as_of_str,)
    ).fetchall()
    pairs = match_cross_platform([dict(r) for r in enriched_rows])
    cross_lookup = {(play_id, "play") for play_id, _ in pairs} | {(ios_id, "ios") for _, ios_id in pairs}

    # 6. Build view models
    views: dict[str, list[dict[str, Any]]] = {}
    for section_key, items in sections_filtered.items():
        section_views = []
        for item in items:
            app_row = conn.execute(
                "SELECT * FROM apps WHERE app_id = ? AND platform = ?",
                (item["app_id"], item["platform"]),
            ).fetchone()
            if app_row is None:
                continue
            ratings_current = conn.execute(
                "SELECT rating_avg, rating_count FROM app_ratings_history WHERE snapshot_date = ? AND app_id = ? AND platform = ?",
                (as_of_str, item["app_id"], item["platform"]),
            ).fetchone()
            last_week = (as_of - timedelta(days=7)).isoformat()
            ratings_last_week = conn.execute(
                "SELECT rating_count FROM app_ratings_history WHERE snapshot_date = ? AND app_id = ? AND platform = ?",
                (last_week, item["app_id"], item["platform"]),
            ).fetchone()
            section_views.append(build_game_view(
                app_row=dict(app_row),
                signal_hit=item,
                ratings_current=dict(ratings_current) if ratings_current else None,
                ratings_last_week=dict(ratings_last_week) if ratings_last_week else None,
                cross_platform=(item["app_id"], item["platform"]) in cross_lookup,
            ))
        views[section_key] = section_views

    cross_platform_games = [v for section in views.values() for v in section if v.get("cross_platform")]

    totals = {
        "sustained": len(views["sustained"]),
        "fast": len(views["fast"]),
        "new": len(views["new"]),
        "cross_platform": len(cross_platform_games),
    }

    # 7. Heartbeat: how many distinct daily snapshots exist in the last 7 days?
    heartbeat_rows = conn.execute(
        """SELECT COUNT(DISTINCT snapshot_date) FROM chart_snapshots
           WHERE snapshot_date >= ? AND snapshot_date <= ?""",
        ((as_of - timedelta(days=6)).isoformat(), as_of_str),
    ).fetchone()
    heartbeat = {"snapshots_this_week": heartbeat_rows[0]}

    # 8. Cold start flag — less than 14 days of history total
    days_of_history = conn.execute(
        "SELECT COUNT(DISTINCT snapshot_date) FROM chart_snapshots"
    ).fetchone()[0]
    cold_start = None
    if days_of_history < 14:
        full_from = (as_of + timedelta(days=14 - days_of_history)).isoformat()
        cold_start = {"full_from_date": full_from}

    # 9. Render report
    render_weekly(
        out_dir=out_dir,
        report_date=as_of,
        sections=views,
        cross_platform_games=cross_platform_games,
        totals=totals,
        heartbeat=heartbeat,
        cold_start=cold_start,
    )

    # 10. Build archive listing (scan existing weekly dirs)
    weekly_dirs = sorted([d for d in out_dir.iterdir() if d.is_dir() and len(d.name) == 10], reverse=True)
    archive_reports = [
        {"slug": d.name, "date": d.name, "totals": totals if d.name == as_of_str else _read_totals_from_html(d)}
        for d in weekly_dirs
    ]
    render_archive(out_dir=out_dir, reports=archive_reports)

    # 11. Post to Slack
    if slack_webhook_url:
        highlight = _pick_highlight(views, cross_platform_games)
        text = compose_headline(
            report_date=as_of_str,
            totals=totals,
            highlight=highlight,
            full_report_url=f"{base_url}/{as_of_str}/",
            archive_url=f"{base_url}/",
        )
        post_headline(slack_webhook_url, text)

    return {"totals": totals, "heartbeat": heartbeat, "cold_start": cold_start}


def _tag(hit: dict[str, Any], signal: str, *, score: float) -> dict[str, Any]:
    return hit | {"signal": signal, "score": score}


def _filter_by_genre(conn: sqlite3.Connection, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not items:
        return []
    kept = []
    for item in items:
        row = conn.execute(
            "SELECT genre_bucket FROM apps WHERE app_id = ? AND platform = ?",
            (item["app_id"], item["platform"]),
        ).fetchone()
        if row and row["genre_bucket"]:
            kept.append(item)
    return kept


def _read_totals_from_html(week_dir: Path) -> dict[str, int]:
    # For prior weeks we don't want to re-render; pull totals from a sidecar JSON if present,
    # else fall back to zeros. Keeps the archive cheap to rebuild.
    sidecar = week_dir / "totals.json"
    if sidecar.exists():
        import json
        return json.loads(sidecar.read_text())
    return {"sustained": 0, "fast": 0, "new": 0, "cross_platform": 0}


def _pick_highlight(views: dict[str, list[dict[str, Any]]], cross_platform_games: list[dict[str, Any]]) -> dict[str, str] | None:
    # Priority: cross-platform sustained > sustained > fast > new
    xp_sustained = [v for v in cross_platform_games if v["signal_label"].startswith("Sustained")]
    candidates = xp_sustained or views["sustained"] or views["fast"] or views["new"]
    if not candidates:
        return None
    pick = candidates[0]
    return {
        "title": pick["title"],
        "signal_label": pick["signal_label"],
        "detail": " · ".join(pick["signal_details"]) if pick["signal_details"] else pick["signal_label"],
    }


def main() -> None:
    import os
    from src.config import load_config
    from src.store.db import connect, init_schema

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    repo_root = Path(__file__).parent.parent.parent
    cfg = load_config(repo_root / "config")
    db_path = repo_root / "data" / "scouting.sqlite"
    conn = connect(db_path)
    init_schema(conn, repo_root / "src" / "store" / "schema.sql")

    out_dir = repo_root / "docs"  # published via GitHub Pages from /docs on main
    out_dir.mkdir(exist_ok=True)

    cfg_dict = {
        "countries": cfg.countries,
        "signals": cfg.signals,
        "genres": cfg.genres,
    }

    # Also write a sidecar totals.json for archive rendering
    result = run_weekly(
        conn=conn,
        as_of=date.today(),
        config=cfg_dict,
        out_dir=out_dir,
        base_url=os.environ["REPORT_BASE_URL"],
        slack_webhook_url=os.environ.get("SLACK_WEBHOOK_URL"),
    )
    import json as _json
    (out_dir / date.today().isoformat() / "totals.json").write_text(_json.dumps(result["totals"]))


if __name__ == "__main__":
    main()
