"""Render Jinja templates into static HTML for GitHub Pages.

build_game_view: transforms a DB app row + signal hit + rating snapshots into the
    dict shape consumed by _card.html.j2.

render_weekly: writes /YYYY-MM-DD/index.html for one week.
render_archive: writes /index.html listing all reports reverse-chronologically.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).parent / "templates"

SIGNAL_LABELS = {
    "sustained": "Sustained Climber",
    "fast": "Fast Climber",
    "new": "New Entrant",
}


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def build_game_view(
    *,
    app_row: dict[str, Any],
    signal_hit: dict[str, Any],
    ratings_current: dict[str, Any] | None,
    ratings_last_week: dict[str, Any] | None,
    cross_platform: bool,
    play_pair_url: str | None = None,
    ios_pair_url: str | None = None,
) -> dict[str, Any]:
    screenshots = json.loads(app_row.get("screenshots") or "[]")
    signal = signal_hit["signal"]

    # Per-signal detail lines
    country = signal_hit.get("country")
    if signal == "fast":
        details = [f"{country} {app_row['platform']} top_free: "
                   f"#{signal_hit.get('previous_rank')} → #{signal_hit.get('current_rank')} "
                   f"(+{signal_hit.get('rank_jump')} in 7d)"]
    elif signal == "sustained":
        details = [f"{country} {app_row['platform']}: "
                   f"#{signal_hit.get('rank_start')} → #{signal_hit.get('current_rank')} "
                   f"(+{signal_hit.get('net_gain')} over 7d, rising {signal_hit.get('rising_days')} days)"]
    elif signal == "new":
        details = [f"First seen {signal_hit.get('first_seen_date')} in {country} at rank "
                   f"#{signal_hit.get('current_rank')}"]
    else:
        details = []

    rating_count_delta = None
    if ratings_current and ratings_last_week and ratings_current.get("rating_count") and ratings_last_week.get("rating_count"):
        rating_count_delta = ratings_current["rating_count"] - ratings_last_week["rating_count"]

    description_excerpt = None
    if app_row.get("description"):
        desc = app_row["description"].strip().replace("\n", " ")
        description_excerpt = (desc[:160] + "…") if len(desc) > 160 else desc

    play_url = app_row.get("store_url") if app_row["platform"] == "play" else play_pair_url
    ios_url = app_row.get("store_url") if app_row["platform"] == "ios" else ios_pair_url

    return {
        "title": app_row.get("title", ""),
        "developer": app_row.get("developer"),
        "icon_url": app_row.get("icon_url"),
        "genre_bucket": app_row.get("genre_bucket") or "",
        "release_date": app_row.get("release_date"),
        "signal_label": SIGNAL_LABELS.get(signal, signal),
        "signal_details": details,
        "rating_avg": (ratings_current or {}).get("rating_avg"),
        "rating_count": (ratings_current or {}).get("rating_count"),
        "rating_count_delta": rating_count_delta,
        "developer_pedigree": app_row.get("developer_pedigree"),
        "screenshots": screenshots[:3],
        "description_excerpt": description_excerpt,
        "play_url": play_url,
        "ios_url": ios_url,
        "cross_platform": cross_platform,
    }


def render_weekly(
    *,
    out_dir: Path,
    report_date: date,
    sections: dict[str, list[dict[str, Any]]],
    cross_platform_games: list[dict[str, Any]],
    totals: dict[str, int],
    heartbeat: dict[str, int],
    cold_start: dict[str, str] | None,
) -> Path:
    env = _env()
    template = env.get_template("weekly.html.j2")
    html = template.render(
        page_title=f"Week of {report_date.isoformat()}",
        generated_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        sections=sections,
        cross_platform_games=cross_platform_games,
        totals=totals,
        heartbeat=heartbeat,
        cold_start=cold_start,
    )
    week_dir = out_dir / report_date.isoformat()
    week_dir.mkdir(parents=True, exist_ok=True)
    index = week_dir / "index.html"
    index.write_text(html)
    return index


def render_archive(*, out_dir: Path, reports: list[dict[str, Any]]) -> Path:
    env = _env()
    template = env.get_template("archive.html.j2")
    html = template.render(
        page_title="Games Scouting — Archive",
        generated_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
        reports=reports,
    )
    index = out_dir / "index.html"
    index.write_text(html)
    return index
