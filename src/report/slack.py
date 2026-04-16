"""Compose and post the weekly Slack headline.

We use the simplest possible payload ({"text": "..."}) — no Block Kit — because:
  - incoming webhooks don't need Block Kit for text-with-links
  - plain text renders the same across desktop/mobile/web
  - keeps the payload trivial to debug
"""
from __future__ import annotations

import logging

import requests

log = logging.getLogger(__name__)


def compose_headline(
    *,
    report_date: str,
    totals: dict[str, int],
    highlight: dict[str, str] | None,
    full_report_url: str,
    archive_url: str,
) -> str:
    lines = [
        f"🎮 Weekly Games Scouting Report — {report_date}",
        "",
        "This week's movers in casual/mass-market:",
        f"• {totals['sustained']} Sustained Climbers",
        f"• {totals['fast']} Fast Climbers",
        f"• {totals['new']} New Entrants",
    ]
    if totals.get("cross_platform"):
        lines.append(f"• {totals['cross_platform']} ⚡ Cross-platform signals")

    if highlight:
        lines += [
            "",
            f"Highlight: \"{highlight['title']}\" — {highlight['detail']}",
        ]

    lines += [
        "",
        f"📊 Full report → {full_report_url}",
        f"📁 Archive → {archive_url}",
    ]
    return "\n".join(lines)


def post_headline(webhook_url: str, text: str) -> None:
    resp = requests.post(webhook_url, json={"text": text}, timeout=15)
    if resp.status_code >= 300:
        raise RuntimeError(f"Slack webhook failed: {resp.status_code} {resp.text}")
    log.info("slack headline posted, %d bytes", len(text))
