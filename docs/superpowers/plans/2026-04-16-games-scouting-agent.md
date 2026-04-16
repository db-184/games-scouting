# Games Scouting Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a free-tier automated agent that scrapes Play Store + App Store charts daily, detects games climbing rapidly in casual/mass-market genres, and publishes a weekly Monday 10 AM IST report to Slack `#new-games` with full details hosted on GitHub Pages.

**Architecture:** One Python repo, two GitHub Actions crons (daily snapshot, weekly report). SQLite stored in-repo as the history store. Modules split by responsibility: `scrape/`, `store/`, `signals/`, `report/`, `jobs/`. All data sources free (`google-play-scraper` library, Apple RSS feeds, iTunes Search API).

**Tech Stack:** Python 3.12, `google-play-scraper`, `requests`, `jinja2`, `pyyaml`, `slack-sdk`, `pytest`, `vcrpy` (recorded HTTP fixtures), `sqlite3` (stdlib), GitHub Actions, GitHub Pages.

**Spec reference:** `docs/superpowers/specs/2026-04-16-games-scouting-agent-design.md`

---

## Roadmap (22 tasks)

| # | Task | Layer |
|---|------|-------|
| 1 | Repo bootstrap (git, Python, deps) | Foundation |
| 2 | Config files & loader | Foundation |
| 3 | SQLite schema & db module | Foundation |
| 4 | Play Store scraper | Scraping |
| 5 | App Store scraper | Scraping |
| 6 | VCR smoke tests for scrapers | Scraping |
| 7 | Genre filter (store genre → watchlist bucket) | Filtering |
| 8 | Fast Climber signal | Signals |
| 9 | New Entrant signal | Signals |
| 10 | Sustained Climber signal | Signals |
| 11 | Cross-platform matcher + signal priority dedup | Signals |
| 12 | Metadata enrichment for qualifying games | Signals |
| 13 | Jinja templates (weekly page, archive index, card partial) | Report |
| 14 | HTML renderer | Report |
| 15 | Slack headline composer + poster | Report |
| 16 | Daily job orchestrator | Jobs |
| 17 | Weekly job orchestrator | Jobs |
| 18 | Daily GitHub Actions workflow | CI |
| 19 | Weekly GitHub Actions workflow | CI |
| 20 | Dry-run workflow (manual trigger) | CI |
| 21 | Logging + heartbeat banner | Observability |
| 22 | README + ops runbook | Docs |

---

## Task 1: Repo bootstrap

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `README.md` (stub — full content in Task 22)
- Create: `src/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Initialize git repo**

Run from `/Users/apple/Desktop/games agent/`:

```bash
cd "/Users/apple/Desktop/games agent"
git init -b main
```

Expected: "Initialized empty Git repository in .../games agent/.git/"

- [ ] **Step 2: Create `.gitignore`**

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.pytest_cache/
.coverage
htmlcov/

# macOS
.DS_Store

# Editors
.vscode/
.idea/

# Local env
.env
.env.local

# Build artifacts
dist/
build/

# Keep these:
# data/scouting.sqlite is committed intentionally (see spec §6.5)
# logs/*.log are committed intentionally (see spec §10)
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[project]
name = "games-scouting-agent"
version = "0.1.0"
description = "Weekly scouting report for rising mobile games in casual/mass-market genres"
requires-python = ">=3.12"
dependencies = [
    "google-play-scraper>=1.2.7",
    "requests>=2.32.0",
    "jinja2>=3.1.4",
    "pyyaml>=6.0.2",
    "slack-sdk>=3.33.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-cov>=5.0.0",
    "vcrpy>=6.0.0",
    "ruff>=0.6.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.ruff]
line-length = 100
target-version = "py312"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["src*"]
```

- [ ] **Step 4: Create stub `README.md`**

```markdown
# Games Scouting Agent

Weekly report on mobile games climbing the charts in casual/mass-market genres.

See [design spec](docs/superpowers/specs/2026-04-16-games-scouting-agent-design.md).

Full operations documentation added in Task 22.
```

- [ ] **Step 5: Create empty package markers**

Create empty files: `src/__init__.py`, `tests/__init__.py`.

- [ ] **Step 6: Set up virtual env and install deps**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

Expected: dependencies resolve and install without error.

- [ ] **Step 7: Sanity test — pytest runs with no tests yet**

```bash
pytest
```

Expected: "no tests ran" (exit 5) is acceptable, or success with zero tests.

- [ ] **Step 8: Commit**

```bash
git add .gitignore pyproject.toml README.md src/__init__.py tests/__init__.py
git commit -m "chore: bootstrap Python project with deps and test scaffold"
```

---

## Task 2: Config files & loader

**Files:**
- Create: `config/countries.yaml`
- Create: `config/genres.yaml`
- Create: `config/signals.yaml`
- Create: `src/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Create `config/countries.yaml`**

```yaml
play_store:
  - IN
  - US
  - JP
  - KR
  - DE
  - GB  # google-play-scraper uses ISO codes; GB = United Kingdom
  - BR
app_store:
  - IN
  - US
  - JP
  - KR
  - CN
  - DE
  - GB
  - BR
```

- [ ] **Step 2: Create `config/genres.yaml`**

Initial mapping — expand as misclassifications surface (see spec §13).

```yaml
# Maps raw store genre identifiers to our watchlist buckets.
# Buckets: match3, hypercasual, hybrid_casual, word_trivia, casual_sim
# Any genre not listed here is excluded from the report.

play_store:
  # google-play-scraper returns genreId like "GAME_PUZZLE", "GAME_WORD", etc.
  GAME_PUZZLE: match3
  GAME_WORD: word_trivia
  GAME_TRIVIA: word_trivia
  GAME_EDUCATIONAL: word_trivia
  GAME_CASUAL: hypercasual  # first-pass; refined by keyword heuristic in src/genre_filter.py
  GAME_ARCADE: hypercasual
  GAME_SIMULATION: casual_sim

app_store:
  # iTunes Search API returns primaryGenreName like "Games", secondary via "genres" array
  # We key on the sub-genre strings iTunes returns
  "Puzzle": match3
  "Word": word_trivia
  "Trivia": word_trivia
  "Casual": hypercasual
  "Arcade": hypercasual
  "Simulation": casual_sim

# Hybrid-casual is detected by keyword heuristic, not store genre (keyword rules in src/genre_filter.py).

# Title/description keyword overrides applied after store-genre mapping:
keyword_overrides:
  match3:
    - "match-3"
    - "match 3"
    - "tile match"
  hypercasual:
    - "hyper casual"
    - ".io"
  hybrid_casual:
    - "merge"
    - "idle"
    - "tycoon"
    - "clicker"
  casual_sim:
    - "farm"
    - "cafe"
    - "restaurant"
    - "city builder"
```

- [ ] **Step 3: Create `config/signals.yaml`**

Thresholds from spec §3. All tunable.

```yaml
fast_climber:
  min_rank_jump: 20
  window_days: 7
  max_current_rank: 100

new_entrant:
  max_window_days: 14
  play_store_chart_ceiling: 200
  app_store_chart_ceiling: 100
  recent_release_bonus_days: 90

sustained_climber:
  min_rising_days_out_of: [5, 7]  # ≥5 of last 7 days rank improved
  alt_net_gain_threshold: 15      # OR net +15 over 7d
  max_reversal_streak: 3          # with no >3-day reversal

report:
  max_games_per_section: 10
  sections_priority_order:        # game is placed in highest-priority section it qualifies for
    - sustained
    - fast
    - new
```

- [ ] **Step 4: Write the failing test**

Create `tests/test_config.py`:

```python
from pathlib import Path
from src.config import load_config

CONFIG_DIR = Path(__file__).parent.parent / "config"


def test_load_countries():
    cfg = load_config(CONFIG_DIR)
    assert "IN" in cfg.countries["play_store"]
    assert "CN" in cfg.countries["app_store"]
    assert "CN" not in cfg.countries["play_store"]  # spec §2.2


def test_load_signals_thresholds():
    cfg = load_config(CONFIG_DIR)
    assert cfg.signals["fast_climber"]["min_rank_jump"] == 20
    assert cfg.signals["new_entrant"]["max_window_days"] == 14


def test_load_genres_mapping():
    cfg = load_config(CONFIG_DIR)
    assert cfg.genres["play_store"]["GAME_PUZZLE"] == "match3"
    assert "match-3" in cfg.genres["keyword_overrides"]["match3"]
```

- [ ] **Step 5: Run test to verify it fails**

```bash
pytest tests/test_config.py -v
```

Expected: ImportError for `src.config` — module doesn't exist yet.

- [ ] **Step 6: Implement `src/config.py`**

```python
"""Loads YAML configs from the config/ directory as a typed container."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Config:
    countries: dict[str, list[str]]
    genres: dict[str, Any]
    signals: dict[str, Any]


def load_config(config_dir: Path) -> Config:
    with (config_dir / "countries.yaml").open() as f:
        countries = yaml.safe_load(f)
    with (config_dir / "genres.yaml").open() as f:
        genres = yaml.safe_load(f)
    with (config_dir / "signals.yaml").open() as f:
        signals = yaml.safe_load(f)
    return Config(countries=countries, genres=genres, signals=signals)
```

- [ ] **Step 7: Run test to verify it passes**

```bash
pytest tests/test_config.py -v
```

Expected: 3 passed.

- [ ] **Step 8: Commit**

```bash
git add config/ src/config.py tests/test_config.py
git commit -m "feat: config files and loader for countries, genres, signal thresholds"
```

---

## Task 3: SQLite schema & db module

**Files:**
- Create: `src/store/__init__.py` (empty)
- Create: `src/store/schema.sql`
- Create: `src/store/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Create `src/store/schema.sql`**

Tables per spec §6.5.

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS chart_snapshots (
    snapshot_date TEXT NOT NULL,  -- ISO date YYYY-MM-DD
    country       TEXT NOT NULL,
    platform      TEXT NOT NULL,  -- 'play' | 'ios'
    chart_type    TEXT NOT NULL,  -- 'top_free' | 'top_grossing' | 'top_new'
    rank          INTEGER NOT NULL,
    app_id        TEXT NOT NULL,
    PRIMARY KEY (snapshot_date, country, platform, chart_type, app_id)
);

CREATE INDEX IF NOT EXISTS idx_snap_app      ON chart_snapshots(app_id, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_snap_platform ON chart_snapshots(platform, snapshot_date);

CREATE TABLE IF NOT EXISTS apps (
    app_id       TEXT NOT NULL,
    platform     TEXT NOT NULL,
    title        TEXT NOT NULL,
    developer    TEXT,
    genre_raw    TEXT,         -- raw store genre string
    genre_bucket TEXT,         -- mapped watchlist bucket, NULL if excluded
    release_date TEXT,         -- ISO YYYY-MM-DD
    icon_url     TEXT,
    description  TEXT,
    price_tier   TEXT,         -- 'free_iap' | 'paid' | 'subscription'
    screenshots  TEXT,         -- JSON array of URLs
    store_url    TEXT,
    last_seen    TEXT NOT NULL,
    PRIMARY KEY (app_id, platform)
);

CREATE TABLE IF NOT EXISTS app_ratings_history (
    snapshot_date TEXT NOT NULL,
    app_id        TEXT NOT NULL,
    platform      TEXT NOT NULL,
    rating_avg    REAL,
    rating_count  INTEGER,
    PRIMARY KEY (snapshot_date, app_id, platform)
);
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_db.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_db.py -v
```

Expected: ImportError for `src.store.db`.

- [ ] **Step 4: Implement `src/store/db.py`**

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_db.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/store/ tests/test_db.py
git commit -m "feat: SQLite schema and db access layer"
```

---

## Task 4: Play Store scraper

**Files:**
- Create: `src/scrape/__init__.py` (empty)
- Create: `src/scrape/play_store.py`
- Create: `tests/test_play_store_scraper.py`

- [ ] **Step 1: Write failing tests**

```python
from unittest.mock import patch

from src.scrape.play_store import fetch_top_chart, fetch_app_metadata


def test_fetch_top_chart_returns_ranked_app_ids():
    fake_response = [
        {"appId": "com.a", "title": "A"},
        {"appId": "com.b", "title": "B"},
        {"appId": "com.c", "title": "C"},
    ]
    with patch("src.scrape.play_store.gps_list", return_value=fake_response):
        result = fetch_top_chart(country="IN", chart_type="top_free", num=3)
    assert result == [
        {"rank": 1, "app_id": "com.a"},
        {"rank": 2, "app_id": "com.b"},
        {"rank": 3, "app_id": "com.c"},
    ]


def test_fetch_top_chart_empty_result_raises():
    """An empty chart means the scraper is likely broken (spec §9.1, §9.3)."""
    import pytest
    with patch("src.scrape.play_store.gps_list", return_value=[]):
        with pytest.raises(RuntimeError, match="empty"):
            fetch_top_chart(country="IN", chart_type="top_free", num=200)


def test_fetch_app_metadata_maps_fields():
    raw = {
        "appId": "com.a",
        "title": "Game A",
        "developer": "Studio X",
        "genreId": "GAME_PUZZLE",
        "genre": "Puzzle",
        "released": "Feb 12, 2026",
        "icon": "https://example.com/icon.png",
        "description": "A puzzle game.",
        "free": True,
        "offersIAP": True,
        "screenshots": ["https://example.com/s1.png"],
        "url": "https://play.google.com/store/apps/details?id=com.a",
        "score": 4.5,
        "ratings": 1234,
    }
    with patch("src.scrape.play_store.gps_app", return_value=raw):
        meta = fetch_app_metadata("com.a", country="IN")
    assert meta["app_id"] == "com.a"
    assert meta["title"] == "Game A"
    assert meta["developer"] == "Studio X"
    assert meta["genre_raw"] == "GAME_PUZZLE"
    assert meta["release_date"] == "2026-02-12"  # parsed
    assert meta["price_tier"] == "free_iap"
    assert meta["rating_avg"] == 4.5
    assert meta["rating_count"] == 1234
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_play_store_scraper.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/scrape/play_store.py`**

```python
"""Play Store scraping via the google-play-scraper library.

All network calls go through gps_list/gps_app aliases so tests can mock them.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

from google_play_scraper import app as gps_app
from google_play_scraper import collection as gps_collection
from google_play_scraper import list as gps_list

CHART_MAP = {
    "top_free": (gps_collection.TOP_FREE, "GAME"),
    "top_grossing": (gps_collection.GROSSING, "GAME"),
    "top_new": (gps_collection.TOP_FREE, "GAME"),  # no dedicated "new" collection — see note
}

# Note: google-play-scraper does not expose a "top new" collection directly.
# For the "new entrant" signal, we rely on per-app release_date comparison at signal-time
# rather than a dedicated scrape. CHART_MAP keeps 'top_new' as an alias of top_free
# for schema compatibility; the signal logic does the real work.


def fetch_top_chart(country: str, chart_type: str, num: int = 200) -> list[dict[str, Any]]:
    collection, category = CHART_MAP[chart_type]
    raw = gps_list(
        collection=collection,
        category=category,
        country=country.lower(),
        lang="en",
        num=num,
    )
    if not raw:
        raise RuntimeError(f"Play Store returned empty result for {country}/{chart_type}")
    return [{"rank": i + 1, "app_id": row["appId"]} for i, row in enumerate(raw)]


def fetch_app_metadata(app_id: str, country: str) -> dict[str, Any]:
    raw = gps_app(app_id, country=country.lower(), lang="en")
    return {
        "app_id": app_id,
        "platform": "play",
        "title": raw.get("title", ""),
        "developer": raw.get("developer"),
        "genre_raw": raw.get("genreId"),
        "release_date": _parse_play_date(raw.get("released")),
        "icon_url": raw.get("icon"),
        "description": raw.get("description"),
        "price_tier": _price_tier(raw),
        "screenshots_json": json.dumps(raw.get("screenshots", [])[:3]),
        "store_url": raw.get("url"),
        "rating_avg": raw.get("score"),
        "rating_count": raw.get("ratings"),
    }


def _parse_play_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%b %d, %Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _price_tier(raw: dict[str, Any]) -> str:
    if not raw.get("free", True):
        return "paid"
    if raw.get("offersIAP"):
        return "free_iap"
    return "free_iap"  # free + no IAP still maps to free_iap bucket; paid is the only other case


def polite_sleep(seconds: float = 0.2) -> None:
    time.sleep(seconds)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_play_store_scraper.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/scrape/__init__.py src/scrape/play_store.py tests/test_play_store_scraper.py
git commit -m "feat: play store scraper for top charts and app metadata"
```

---

## Task 5: App Store scraper

**Files:**
- Create: `src/scrape/app_store.py`
- Create: `tests/test_app_store_scraper.py`

- [ ] **Step 1: Write failing tests**

```python
from unittest.mock import patch, MagicMock

from src.scrape.app_store import fetch_top_chart, fetch_app_metadata


def _rss_fixture():
    return {
        "feed": {
            "results": [
                {"id": "111", "name": "Game A"},
                {"id": "222", "name": "Game B"},
                {"id": "333", "name": "Game C"},
            ]
        }
    }


def test_fetch_top_chart_parses_apple_rss():
    mock = MagicMock()
    mock.json.return_value = _rss_fixture()
    mock.raise_for_status.return_value = None
    with patch("src.scrape.app_store.requests.get", return_value=mock):
        result = fetch_top_chart(country="IN", chart_type="top_free", num=3)
    assert result == [
        {"rank": 1, "app_id": "111"},
        {"rank": 2, "app_id": "222"},
        {"rank": 3, "app_id": "333"},
    ]


def test_fetch_top_chart_empty_raises():
    mock = MagicMock()
    mock.json.return_value = {"feed": {"results": []}}
    mock.raise_for_status.return_value = None
    import pytest
    with patch("src.scrape.app_store.requests.get", return_value=mock):
        with pytest.raises(RuntimeError, match="empty"):
            fetch_top_chart(country="IN", chart_type="top_free", num=100)


def test_fetch_app_metadata_maps_itunes_fields():
    itunes_raw = {
        "results": [{
            "trackId": 111,
            "trackName": "Game A",
            "artistName": "Studio X",
            "primaryGenreName": "Games",
            "genres": ["Games", "Puzzle", "Entertainment"],
            "releaseDate": "2026-02-12T00:00:00Z",
            "artworkUrl512": "https://example.com/icon.png",
            "description": "A puzzle game.",
            "price": 0.0,
            "screenshotUrls": ["https://example.com/s1.png"],
            "trackViewUrl": "https://apps.apple.com/app/id111",
            "averageUserRating": 4.5,
            "userRatingCount": 1234,
        }]
    }
    mock = MagicMock()
    mock.json.return_value = itunes_raw
    mock.raise_for_status.return_value = None
    with patch("src.scrape.app_store.requests.get", return_value=mock):
        meta = fetch_app_metadata("111", country="IN")
    assert meta["app_id"] == "111"
    assert meta["title"] == "Game A"
    assert meta["developer"] == "Studio X"
    assert meta["genre_raw"] == "Puzzle"  # first non-"Games" sub-genre
    assert meta["release_date"] == "2026-02-12"
    assert meta["price_tier"] == "free_iap"
    assert meta["rating_count"] == 1234
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_app_store_scraper.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/scrape/app_store.py`**

```python
"""App Store scraping via Apple's official RSS marketing feeds and iTunes Search API.

Both endpoints are free, no key required, and officially sanctioned for consumer use.
"""
from __future__ import annotations

import json
import time
from typing import Any

import requests

RSS_BASE = "https://rss.applemarketingtools.com/api/v2"
ITUNES_LOOKUP = "https://itunes.apple.com/lookup"

CHART_RSS_MAP = {
    "top_free": "top-free",
    "top_grossing": "top-grossing",
    "top_new": "top-free",  # Apple RSS has no dedicated "new games" feed — see play_store.py note
}

REQUEST_TIMEOUT = 20
USER_AGENT = "games-scouting-agent/0.1"


def fetch_top_chart(country: str, chart_type: str, num: int = 100) -> list[dict[str, Any]]:
    feed_slug = CHART_RSS_MAP[chart_type]
    url = f"{RSS_BASE}/{country.lower()}/apps/{feed_slug}/{num}/games.json"
    resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    data = resp.json()
    results = data.get("feed", {}).get("results", [])
    if not results:
        raise RuntimeError(f"App Store returned empty result for {country}/{chart_type}")
    return [{"rank": i + 1, "app_id": row["id"]} for i, row in enumerate(results)]


def fetch_app_metadata(app_id: str, country: str) -> dict[str, Any]:
    params = {"id": app_id, "country": country.lower(), "entity": "software"}
    resp = requests.get(
        ITUNES_LOOKUP,
        params=params,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("results"):
        raise RuntimeError(f"iTunes lookup returned no result for id={app_id} country={country}")
    raw = data["results"][0]
    return {
        "app_id": app_id,
        "platform": "ios",
        "title": raw.get("trackName", ""),
        "developer": raw.get("artistName"),
        "genre_raw": _primary_sub_genre(raw),
        "release_date": _parse_itunes_date(raw.get("releaseDate")),
        "icon_url": raw.get("artworkUrl512") or raw.get("artworkUrl100"),
        "description": raw.get("description"),
        "price_tier": "paid" if raw.get("price", 0) > 0 else "free_iap",
        "screenshots_json": json.dumps((raw.get("screenshotUrls") or [])[:3]),
        "store_url": raw.get("trackViewUrl"),
        "rating_avg": raw.get("averageUserRating"),
        "rating_count": raw.get("userRatingCount"),
    }


def _primary_sub_genre(raw: dict[str, Any]) -> str | None:
    genres = raw.get("genres") or []
    for g in genres:
        if g != "Games":
            return g
    return raw.get("primaryGenreName")


def _parse_itunes_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    # Format: "2026-02-12T00:00:00Z" — just take the date part
    return date_str[:10]


def polite_sleep(seconds: float = 0.2) -> None:
    time.sleep(seconds)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_app_store_scraper.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/scrape/app_store.py tests/test_app_store_scraper.py
git commit -m "feat: app store scraper using Apple RSS feeds and iTunes Search API"
```

---

## Task 6: VCR smoke tests for scrapers

**Purpose:** Catch changes in `google-play-scraper` return shape or Apple RSS format *in CI* without hitting the live network.

**Files:**
- Create: `tests/fixtures/cassettes/.gitkeep` (directory marker)
- Create: `tests/test_scrape_smoke.py`
- Modify: `pyproject.toml` (already has vcrpy in dev deps from Task 1)

- [ ] **Step 1: Write the cassette-recording tests**

```python
"""Smoke tests using recorded HTTP fixtures via vcrpy.

First run (online): records fresh cassettes from real APIs.
Subsequent runs (offline): replay cassettes, detect shape changes.

To refresh a cassette after an API change:
    rm tests/fixtures/cassettes/<name>.yaml
    pytest tests/test_scrape_smoke.py  # will re-record

CI runs always use record_mode='none' so they fail loudly on shape changes.
"""
import os
from pathlib import Path

import pytest
import vcr

from src.scrape.app_store import fetch_top_chart as ios_fetch_top, fetch_app_metadata as ios_meta
from src.scrape.play_store import fetch_top_chart as play_fetch_top

CASSETTE_DIR = Path(__file__).parent / "fixtures" / "cassettes"

# In CI, never re-record — we want failures if the API shape has changed.
# Locally, allow recording when a cassette is missing.
record_mode = "none" if os.environ.get("CI") else "once"

my_vcr = vcr.VCR(
    cassette_library_dir=str(CASSETTE_DIR),
    record_mode=record_mode,
    match_on=["method", "scheme", "host", "port", "path", "query"],
    filter_headers=["authorization", "cookie"],
)


@my_vcr.use_cassette("ios_top_free_us.yaml")
def test_ios_top_free_us_returns_100_games():
    result = ios_fetch_top(country="US", chart_type="top_free", num=100)
    assert len(result) == 100
    assert all("rank" in r and "app_id" in r for r in result)


@my_vcr.use_cassette("ios_metadata_sample.yaml")
def test_ios_metadata_has_required_fields():
    # Use a stable long-lived app ID — Apple's own Clips (id1212699939) or similar
    # Replace with a stable game ID when recording
    meta = ios_meta("1212699939", country="US")
    required = {"title", "developer", "genre_raw", "release_date", "icon_url",
                "description", "price_tier", "screenshots_json", "store_url",
                "rating_avg", "rating_count"}
    assert required <= meta.keys()


@pytest.mark.skipif(
    not (CASSETTE_DIR / "play_top_free_us.yaml").exists() and record_mode == "none",
    reason="cassette must be recorded locally first",
)
@my_vcr.use_cassette("play_top_free_us.yaml")
def test_play_top_free_us_returns_games():
    # google-play-scraper doesn't use requests directly — vcrpy may not intercept.
    # This test exists for structural assertion; if the library changes its HTTP backend,
    # we'll see a recorded-vs-live mismatch. Skipped in CI if cassette missing.
    result = play_fetch_top(country="US", chart_type="top_free", num=50)
    assert len(result) >= 1
```

- [ ] **Step 2: Record cassettes locally (one-time)**

```bash
source .venv/bin/activate
pytest tests/test_scrape_smoke.py -v
```

Expected (first run): cassettes recorded into `tests/fixtures/cassettes/*.yaml`. Tests pass.

If `google-play-scraper` doesn't route through `requests` (it uses its own HTTP), the `play_top_free_us.yaml` cassette may not record cleanly — in that case, skip the Play Store cassette test and rely on the unit test from Task 4 with its mocked `gps_list`. Leave the test in place; it will be skipped automatically in CI when the cassette is missing.

- [ ] **Step 3: Verify replay works offline**

```bash
CI=true pytest tests/test_scrape_smoke.py -v
```

Expected: tests pass using recorded cassettes only.

- [ ] **Step 4: Commit cassettes + tests**

```bash
git add tests/fixtures/cassettes/ tests/test_scrape_smoke.py
git commit -m "test: VCR smoke tests to detect scraper return-shape changes"
```

---

## Task 7: Genre filter

**Files:**
- Create: `src/genre_filter.py`
- Create: `tests/test_genre_filter.py`

- [ ] **Step 1: Write failing tests**

```python
from src.genre_filter import classify_bucket

GENRES_CFG = {
    "play_store": {
        "GAME_PUZZLE": "match3",
        "GAME_CASUAL": "hypercasual",
        "GAME_SIMULATION": "casual_sim",
    },
    "app_store": {
        "Puzzle": "match3",
        "Casual": "hypercasual",
        "Simulation": "casual_sim",
    },
    "keyword_overrides": {
        "hybrid_casual": ["merge", "idle", "tycoon"],
        "match3": ["match-3", "match 3"],
    },
}


def test_classify_bucket_uses_store_genre():
    assert classify_bucket(
        platform="play",
        genre_raw="GAME_PUZZLE",
        title="Block Puzzle Duel",
        description="",
        genres_cfg=GENRES_CFG,
    ) == "match3"


def test_classify_bucket_falls_back_to_keyword_override():
    # genre GAME_CASUAL would map to hypercasual, but "merge" keyword upgrades to hybrid_casual
    assert classify_bucket(
        platform="play",
        genre_raw="GAME_CASUAL",
        title="MergeFarm Tycoon",
        description="Merge cute animals and expand your farm.",
        genres_cfg=GENRES_CFG,
    ) == "hybrid_casual"


def test_classify_bucket_returns_none_for_unmapped_genre():
    assert classify_bucket(
        platform="play",
        genre_raw="GAME_RACING",
        title="Speed Kings",
        description="",
        genres_cfg=GENRES_CFG,
    ) is None


def test_classify_bucket_returns_none_when_no_genre_and_no_keywords():
    assert classify_bucket(
        platform="play",
        genre_raw=None,
        title="Mystery Game",
        description="A mystery awaits.",
        genres_cfg=GENRES_CFG,
    ) is None


def test_classify_bucket_app_store_genre():
    assert classify_bucket(
        platform="ios",
        genre_raw="Puzzle",
        title="Candy Match Saga",
        description="",
        genres_cfg=GENRES_CFG,
    ) == "match3"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_genre_filter.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/genre_filter.py`**

```python
"""Maps raw store-genre strings to watchlist buckets.

Strategy:
1. Look up the raw genre in the store's genre map → base bucket (or None).
2. Scan title + description for keyword overrides. An override "upgrades" or sets the bucket.
   Rationale: both stores categorize "hypercasual" and "hybrid-casual" inconsistently
   (everything lands in "Arcade" or "Casual"); keywords are a second pass.

Returns the bucket name (e.g., "match3") or None if the game should be excluded from the report.
"""
from __future__ import annotations

from typing import Any


def classify_bucket(
    *,
    platform: str,  # "play" | "ios"
    genre_raw: str | None,
    title: str,
    description: str | None,
    genres_cfg: dict[str, Any],
) -> str | None:
    store_key = "play_store" if platform == "play" else "app_store"
    base = genres_cfg.get(store_key, {}).get(genre_raw) if genre_raw else None

    haystack = f"{title or ''} {description or ''}".lower()

    # Keyword overrides win over store-genre base mapping, because store genres
    # lump hybrid-casual into casual/arcade buckets.
    for bucket, keywords in (genres_cfg.get("keyword_overrides") or {}).items():
        for kw in keywords:
            if kw.lower() in haystack:
                return bucket

    return base
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_genre_filter.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/genre_filter.py tests/test_genre_filter.py
git commit -m "feat: genre filter mapping store genres + keyword heuristics to watchlist buckets"
```

---

## Task 8: Fast Climber signal

**Files:**
- Create: `src/signals/__init__.py` (empty)
- Create: `src/signals/fast_climber.py`
- Create: `tests/test_fast_climber.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create shared test fixtures**

`tests/conftest.py`:

```python
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
```

- [ ] **Step 2: Write failing tests**

`tests/test_fast_climber.py`:

```python
from src.signals.fast_climber import find_fast_climbers
from tests.conftest import seed_ranks

SIGNALS_CFG = {
    "fast_climber": {
        "min_rank_jump": 20,
        "window_days": 7,
        "max_current_rank": 100,
    }
}


def test_climber_with_big_jump_is_found(db):
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-08": 85,
        "2026-04-15": 30,  # +55 jump in 7d, current rank 30 ≤ 100
    })
    result = find_fast_climbers(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert len(result) == 1
    assert result[0]["app_id"] == "com.a"
    assert result[0]["rank_jump"] == 55
    assert result[0]["current_rank"] == 30


def test_small_jump_is_filtered_out(db):
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-08": 50,
        "2026-04-15": 40,  # only +10
    })
    result = find_fast_climbers(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert result == []


def test_game_outside_top_100_is_filtered(db):
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-08": 180,
        "2026-04-15": 150,  # jumped +30 but current rank 150 > 100
    })
    result = find_fast_climbers(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert result == []


def test_multiple_climbers_sorted_by_jump_magnitude(db):
    seed_ranks(db, "com.a", "play", "IN", "top_free", {"2026-04-08": 60, "2026-04-15": 35})   # +25
    seed_ranks(db, "com.b", "play", "IN", "top_free", {"2026-04-08": 90, "2026-04-15": 20})   # +70
    seed_ranks(db, "com.c", "play", "IN", "top_free", {"2026-04-08": 80, "2026-04-15": 40})   # +40
    result = find_fast_climbers(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert [r["app_id"] for r in result] == ["com.b", "com.c", "com.a"]


def test_per_chart_per_country_unique(db):
    # Same app climbing in two countries — each surfaces separately
    seed_ranks(db, "com.a", "play", "IN", "top_free", {"2026-04-08": 60, "2026-04-15": 30})
    seed_ranks(db, "com.a", "play", "BR", "top_free", {"2026-04-08": 70, "2026-04-15": 40})
    result = find_fast_climbers(db, as_of="2026-04-15", config=SIGNALS_CFG)
    countries = sorted(r["country"] for r in result)
    assert countries == ["BR", "IN"]
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_fast_climber.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement `src/signals/fast_climber.py`**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_fast_climber.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/signals/__init__.py src/signals/fast_climber.py tests/conftest.py tests/test_fast_climber.py
git commit -m "feat: fast climber signal — detects games jumping ≥20 ranks in 7 days"
```

---

## Task 9: New Entrant signal

**Files:**
- Create: `src/signals/new_entrant.py`
- Create: `tests/test_new_entrant.py`

- [ ] **Step 1: Write failing tests**

```python
from src.signals.new_entrant import find_new_entrants
from src.store.db import upsert_app
from tests.conftest import seed_ranks

SIGNALS_CFG = {
    "new_entrant": {
        "max_window_days": 14,
        "play_store_chart_ceiling": 200,
        "app_store_chart_ceiling": 100,
        "recent_release_bonus_days": 90,
    }
}


def _register_app(db, app_id, platform, release_date=None, genre_bucket="match3"):
    upsert_app(
        db, app_id, platform,
        title=f"Game {app_id}", developer="Dev", genre_raw="GAME_PUZZLE",
        genre_bucket=genre_bucket, release_date=release_date,
        icon_url=None, description=None, price_tier="free_iap",
        screenshots_json="[]", store_url=None, last_seen="2026-04-15",
    )
    db.commit()


def test_app_first_seen_within_window_is_new_entrant(db):
    _register_app(db, "com.a", "play", release_date="2026-04-05")
    # first and only appearance on 2026-04-12 (within 14 days of 2026-04-15)
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-12": 150,
        "2026-04-15": 120,
    })
    result = find_new_entrants(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert len(result) == 1
    assert result[0]["app_id"] == "com.a"
    assert result[0]["first_seen_date"] == "2026-04-12"
    assert result[0]["recent_release"] is True  # released 2026-04-05, 10 days before as_of


def test_app_first_seen_before_window_is_not_new(db):
    _register_app(db, "com.a", "play", release_date="2025-01-01")
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-03-01": 180,  # first seen >14 days before 2026-04-15
        "2026-04-15": 150,
    })
    result = find_new_entrants(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert result == []


def test_app_not_currently_charting_is_excluded(db):
    _register_app(db, "com.a", "play", release_date="2026-04-01")
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-10": 180,
        # not present on as_of 2026-04-15
    })
    result = find_new_entrants(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert result == []


def test_ios_uses_100_ceiling_not_200(db):
    _register_app(db, "123", "ios", release_date="2026-04-05")
    # rank 120 is allowed in Play (ceiling 200) but NOT in iOS (ceiling 100)
    seed_ranks(db, "123", "ios", "US", "top_free", {
        "2026-04-12": 120,
        "2026-04-15": 120,
    })
    result = find_new_entrants(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_new_entrant.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/signals/new_entrant.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_new_entrant.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/signals/new_entrant.py tests/test_new_entrant.py
git commit -m "feat: new entrant signal — games first seen in charts within last 14 days"
```

---

## Task 10: Sustained Climber signal

**Files:**
- Create: `src/signals/sustained.py`
- Create: `tests/test_sustained.py`

- [ ] **Step 1: Write failing tests**

```python
from src.signals.sustained import find_sustained_climbers
from tests.conftest import seed_ranks

SIGNALS_CFG = {
    "sustained_climber": {
        "min_rising_days_out_of": [5, 7],   # ≥5 of last 7 days rank improved
        "alt_net_gain_threshold": 15,
        "max_reversal_streak": 3,
    }
}


def test_rising_5_of_7_days_qualifies(db):
    # ranks: day-by-day. Lower number = better rank. Improving means current < previous.
    # 7-day series ending 2026-04-15: 90 → 85 → 83 → 80 → 78 → 75 → 73 → 71
    # Improved on 7 out of 7 days (relative to prior day).
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-08": 90, "2026-04-09": 85, "2026-04-10": 83, "2026-04-11": 80,
        "2026-04-12": 78, "2026-04-13": 75, "2026-04-14": 73, "2026-04-15": 71,
    })
    result = find_sustained_climbers(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert len(result) == 1
    assert result[0]["app_id"] == "com.a"


def test_volatile_rise_fails_5_of_7_rule(db):
    # Rises day 1, flat most days, rises day 7 — only 2 rising days
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-08": 90, "2026-04-09": 85, "2026-04-10": 85, "2026-04-11": 85,
        "2026-04-12": 85, "2026-04-13": 85, "2026-04-14": 85, "2026-04-15": 80,
    })
    result = find_sustained_climbers(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert result == []


def test_alt_path_net_gain_15_with_minor_dip_qualifies(db):
    # Net +20 over 7d, dip of 2 days (within max_reversal_streak=3)
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-08": 80, "2026-04-09": 78, "2026-04-10": 80, "2026-04-11": 82,
        "2026-04-12": 75, "2026-04-13": 70, "2026-04-14": 65, "2026-04-15": 60,
    })
    # Net: 80 → 60 = +20. Reversal streak max = 2 (days 10–11). Rising days >= 5 not required here.
    result = find_sustained_climbers(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert any(r["app_id"] == "com.a" for r in result)


def test_long_reversal_disqualifies(db):
    # Net gain but with a 4-day reversal streak — disqualified
    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-08": 80, "2026-04-09": 85, "2026-04-10": 88, "2026-04-11": 90,
        "2026-04-12": 92, "2026-04-13": 88, "2026-04-14": 70, "2026-04-15": 60,
    })
    # 4 consecutive days of rising rank numbers (worsening): 09→10→11→12
    result = find_sustained_climbers(db, as_of="2026-04-15", config=SIGNALS_CFG)
    assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_sustained.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/signals/sustained.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_sustained.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/signals/sustained.py tests/test_sustained.py
git commit -m "feat: sustained climber signal — filters paid-UA spikes from organic growth"
```

---

## Task 11: Cross-platform matcher + signal priority dedup

**Files:**
- Create: `src/signals/cross_platform.py`
- Create: `src/signals/compose.py`
- Create: `tests/test_cross_platform.py`
- Create: `tests/test_compose.py`

- [ ] **Step 1: Write failing tests for cross-platform matching**

`tests/test_cross_platform.py`:

```python
from src.signals.cross_platform import match_cross_platform

CANDIDATES = [
    {"app_id": "com.sunflower.mergefarm", "platform": "play", "title": "MergeFarm Tycoon", "developer": "Sunflower Studios"},
    {"app_id": "1111",                    "platform": "ios",  "title": "MergeFarm Tycoon", "developer": "Sunflower Studios"},
    {"app_id": "com.other.game",          "platform": "play", "title": "Other Game",       "developer": "Other Studio"},
]


def test_fuzzy_match_on_title_and_developer():
    pairs = match_cross_platform(CANDIDATES)
    assert len(pairs) == 1
    play_id, ios_id = pairs[0]
    assert play_id == "com.sunflower.mergefarm"
    assert ios_id == "1111"


def test_title_mismatch_does_not_match():
    candidates = [
        {"app_id": "com.a", "platform": "play", "title": "Alpha",    "developer": "X"},
        {"app_id": "999",   "platform": "ios",  "title": "Omega",    "developer": "X"},
    ]
    assert match_cross_platform(candidates) == []


def test_developer_mismatch_does_not_match():
    candidates = [
        {"app_id": "com.a", "platform": "play", "title": "Candy Crush", "developer": "X"},
        {"app_id": "999",   "platform": "ios",  "title": "Candy Crush", "developer": "Y"},
    ]
    assert match_cross_platform(candidates) == []
```

- [ ] **Step 2: Write failing tests for compose (dedup + priority)**

`tests/test_compose.py`:

```python
from src.signals.compose import compose_sections

# Each signal list is already sorted by strength.

FAST = [
    {"app_id": "com.a", "platform": "play", "signal": "fast", "score": 60},
    {"app_id": "com.b", "platform": "play", "signal": "fast", "score": 40},
]

NEW = [
    {"app_id": "com.a", "platform": "play", "signal": "new", "score": 10},  # dup — fast wins
    {"app_id": "com.c", "platform": "play", "signal": "new", "score": 20},
]

SUSTAINED = [
    {"app_id": "com.b", "platform": "play", "signal": "sustained", "score": 30},  # dup — sustained > fast
]


def test_compose_priority_sustained_over_fast_over_new():
    sections = compose_sections(fast=FAST, new=NEW, sustained=SUSTAINED, max_per_section=10)
    # com.b should be in sustained (bumped out of fast)
    assert {x["app_id"] for x in sections["sustained"]} == {"com.b"}
    # com.a stays in fast
    assert {x["app_id"] for x in sections["fast"]} == {"com.a"}
    # com.c stays in new
    assert {x["app_id"] for x in sections["new"]} == {"com.c"}


def test_compose_respects_max_per_section():
    fast = [{"app_id": f"com.{i}", "platform": "play", "signal": "fast", "score": 100 - i} for i in range(20)]
    sections = compose_sections(fast=fast, new=[], sustained=[], max_per_section=10)
    assert len(sections["fast"]) == 10
    # top 10 by score preserved
    assert sections["fast"][0]["app_id"] == "com.0"
    assert sections["fast"][9]["app_id"] == "com.9"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_cross_platform.py tests/test_compose.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement `src/signals/cross_platform.py`**

```python
"""Fuzzy cross-platform matching: does the same game appear on Play and iOS?

Matching is lenient on minor differences (casing, punctuation, trailing "HD"/"Free")
but requires both title AND developer to agree above thresholds.

Uses only stdlib (difflib) to avoid adding dependencies.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

TITLE_THRESHOLD = 0.85
DEV_THRESHOLD = 0.85


def _normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\b(hd|free|lite|premium)\b", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def match_cross_platform(candidates: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Return pairs of (play_app_id, ios_app_id) that appear to be the same game."""
    play = [c for c in candidates if c["platform"] == "play"]
    ios = [c for c in candidates if c["platform"] == "ios"]
    pairs: list[tuple[str, str]] = []
    for p in play:
        for i in ios:
            if (_similar(p["title"], i["title"]) >= TITLE_THRESHOLD
                and _similar(p.get("developer") or "", i.get("developer") or "") >= DEV_THRESHOLD):
                pairs.append((p["app_id"], i["app_id"]))
    return pairs
```

- [ ] **Step 5: Implement `src/signals/compose.py`**

```python
"""Combines the three signal outputs into report sections with priority-based dedup.

Priority (spec §3.5): sustained > fast > new.
A game appearing in multiple lists is placed only in its highest-priority section.
Within each section, items are sorted by the caller (by score) and truncated to max_per_section.
"""
from __future__ import annotations

from typing import Any


def compose_sections(
    *,
    fast: list[dict[str, Any]],
    new: list[dict[str, Any]],
    sustained: list[dict[str, Any]],
    max_per_section: int,
) -> dict[str, list[dict[str, Any]]]:
    seen: set[tuple[str, str]] = set()  # (app_id, platform)

    def _claim(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for item in items:
            key = (item["app_id"], item["platform"])
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
            if len(out) >= max_per_section:
                break
        return out

    # Claim in priority order
    sustained_out = _claim(sustained)
    fast_out = _claim(fast)
    new_out = _claim(new)

    return {
        "sustained": sustained_out,
        "fast": fast_out,
        "new": new_out,
    }
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_cross_platform.py tests/test_compose.py -v
```

Expected: 5 passed total.

- [ ] **Step 7: Commit**

```bash
git add src/signals/cross_platform.py src/signals/compose.py tests/test_cross_platform.py tests/test_compose.py
git commit -m "feat: cross-platform matcher and section composer with priority dedup"
```

---

## Task 12: Metadata enrichment for qualifying games

**Files:**
- Create: `src/signals/enrich.py`
- Create: `tests/test_enrich.py`

- [ ] **Step 1: Write failing tests**

```python
from unittest.mock import patch

from src.signals.enrich import enrich_qualifying_apps
from src.store.db import upsert_app


def test_enrich_refreshes_metadata_for_signal_hits(db):
    candidates = [
        {"app_id": "com.a", "platform": "play"},
        {"app_id": "123",   "platform": "ios"},
    ]

    play_meta = {
        "app_id": "com.a", "platform": "play", "title": "A", "developer": "X",
        "genre_raw": "GAME_PUZZLE", "release_date": "2026-04-01", "icon_url": "u",
        "description": "match-3 game", "price_tier": "free_iap",
        "screenshots_json": "[]", "store_url": "https://play/",
        "rating_avg": 4.5, "rating_count": 1000,
    }
    ios_meta = {
        "app_id": "123", "platform": "ios", "title": "A", "developer": "X",
        "genre_raw": "Puzzle", "release_date": "2026-04-01", "icon_url": "u",
        "description": "match-3 game", "price_tier": "free_iap",
        "screenshots_json": "[]", "store_url": "https://apps/",
        "rating_avg": 4.6, "rating_count": 900,
    }

    with patch("src.signals.enrich.play_fetch_app_metadata", return_value=play_meta), \
         patch("src.signals.enrich.ios_fetch_app_metadata", return_value=ios_meta):
        enrich_qualifying_apps(db, candidates, as_of="2026-04-15", genres_cfg={
            "play_store": {"GAME_PUZZLE": "match3"},
            "app_store": {"Puzzle": "match3"},
            "keyword_overrides": {},
        })

    rows = db.execute("SELECT app_id, platform, genre_bucket, developer FROM apps ORDER BY platform").fetchall()
    assert len(rows) == 2
    assert rows[0]["genre_bucket"] == "match3"
    assert rows[1]["genre_bucket"] == "match3"


def test_enrich_tolerates_individual_failures(db):
    candidates = [
        {"app_id": "com.good", "platform": "play"},
        {"app_id": "com.bad",  "platform": "play"},
    ]

    def _side_effect(app_id, country):
        if app_id == "com.bad":
            raise RuntimeError("iTunes 404")
        return {
            "app_id": app_id, "platform": "play", "title": "OK", "developer": "X",
            "genre_raw": "GAME_PUZZLE", "release_date": None, "icon_url": None,
            "description": None, "price_tier": "free_iap", "screenshots_json": "[]",
            "store_url": None, "rating_avg": 4.0, "rating_count": 100,
        }

    with patch("src.signals.enrich.play_fetch_app_metadata", side_effect=_side_effect):
        enrich_qualifying_apps(db, candidates, as_of="2026-04-15", genres_cfg={
            "play_store": {"GAME_PUZZLE": "match3"},
            "app_store": {},
            "keyword_overrides": {},
        })

    rows = db.execute("SELECT app_id FROM apps").fetchall()
    assert [r["app_id"] for r in rows] == ["com.good"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_enrich.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/signals/enrich.py`**

```python
"""For each app that qualified for a signal, fetch fresh metadata and update the apps table.

Tolerant of per-app failures — one bad lookup shouldn't break the whole report.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from src.genre_filter import classify_bucket
from src.scrape.app_store import fetch_app_metadata as ios_fetch_app_metadata
from src.scrape.play_store import fetch_app_metadata as play_fetch_app_metadata
from src.store.db import upsert_app, upsert_rating_snapshot

log = logging.getLogger(__name__)


def enrich_qualifying_apps(
    conn: sqlite3.Connection,
    candidates: list[dict[str, Any]],
    *,
    as_of: str,
    genres_cfg: dict[str, Any],
    country_for_lookup: str = "US",  # iTunes metadata varies slightly by country; US is stable
) -> None:
    seen: set[tuple[str, str]] = set()
    for c in candidates:
        key = (c["app_id"], c["platform"])
        if key in seen:
            continue
        seen.add(key)

        try:
            if c["platform"] == "play":
                meta = play_fetch_app_metadata(c["app_id"], country=country_for_lookup)
            else:
                meta = ios_fetch_app_metadata(c["app_id"], country=country_for_lookup)
        except Exception as e:
            log.warning("metadata fetch failed for %s/%s: %s", c["platform"], c["app_id"], e)
            continue

        bucket = classify_bucket(
            platform=c["platform"],
            genre_raw=meta.get("genre_raw"),
            title=meta.get("title", ""),
            description=meta.get("description"),
            genres_cfg=genres_cfg,
        )

        upsert_app(
            conn,
            app_id=c["app_id"],
            platform=c["platform"],
            title=meta["title"],
            developer=meta.get("developer"),
            genre_raw=meta.get("genre_raw"),
            genre_bucket=bucket,
            release_date=meta.get("release_date"),
            icon_url=meta.get("icon_url"),
            description=meta.get("description"),
            price_tier=meta.get("price_tier"),
            screenshots_json=meta.get("screenshots_json"),
            store_url=meta.get("store_url"),
            last_seen=as_of,
        )
        upsert_rating_snapshot(
            conn,
            snapshot_date=as_of,
            app_id=c["app_id"],
            platform=c["platform"],
            rating_avg=meta.get("rating_avg"),
            rating_count=meta.get("rating_count"),
        )
    conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_enrich.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/signals/enrich.py tests/test_enrich.py
git commit -m "feat: enrich qualifying apps with fresh metadata and genre classification"
```

---

## Task 13: Jinja templates

**Files:**
- Create: `src/report/__init__.py` (empty)
- Create: `src/report/templates/base.html.j2`
- Create: `src/report/templates/weekly.html.j2`
- Create: `src/report/templates/archive.html.j2`
- Create: `src/report/templates/_card.html.j2`

- [ ] **Step 1: Create `src/report/templates/base.html.j2`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ page_title }} — Games Scouting</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
</style>
</head>
<body class="bg-slate-50 text-slate-900 max-w-5xl mx-auto p-6">
<header class="mb-8 border-b border-slate-200 pb-4">
  <a href="../index.html" class="text-sm text-slate-500 hover:text-slate-800">← Archive</a>
  <h1 class="text-3xl font-semibold mt-2">{{ page_title }}</h1>
  {% block subheader %}{% endblock %}
</header>
<main>
{% block content %}{% endblock %}
</main>
<footer class="mt-12 pt-6 border-t border-slate-200 text-xs text-slate-500">
  Generated {{ generated_at }} • <a href="../index.html" class="underline">Archive</a>
</footer>
</body>
</html>
```

- [ ] **Step 2: Create `src/report/templates/_card.html.j2`**

```html
{# Macro: render one game card. `game` dict fields documented in src/report/render.py. #}
{% macro render_card(game) %}
<article class="bg-white rounded-lg shadow-sm border border-slate-200 p-4 mb-4">
  <div class="flex items-start gap-4">
    {% if game.icon_url %}
      <img src="{{ game.icon_url }}" alt="" class="w-16 h-16 rounded-lg">
    {% endif %}
    <div class="flex-1">
      <div class="flex items-center gap-2 flex-wrap">
        <h3 class="font-semibold text-lg">{{ game.title }}</h3>
        {% if game.cross_platform %}
          <span class="inline-block px-2 py-0.5 bg-amber-100 text-amber-800 text-xs rounded">⚡ Cross-platform</span>
        {% endif %}
      </div>
      <div class="text-sm text-slate-600">by {{ game.developer or "Unknown" }}</div>
      <div class="text-sm text-slate-500">
        {{ game.genre_bucket|title }}{% if game.release_date %} · Released {{ game.release_date }}{% endif %}
      </div>
    </div>
  </div>

  <div class="mt-3 text-sm">
    <div><span class="font-medium">Signal:</span> {{ game.signal_label }}</div>
    {% for detail in game.signal_details %}
      <div class="text-slate-700">{{ detail }}</div>
    {% endfor %}
  </div>

  <div class="mt-3 text-sm text-slate-700">
    ★ {{ "%.1f"|format(game.rating_avg) if game.rating_avg else "—" }}
    · {{ "{:,}".format(game.rating_count) if game.rating_count else "—" }} ratings
    {% if game.rating_count_delta %} (+{{ "{:,}".format(game.rating_count_delta) }} this week){% endif %}
  </div>

  {% if game.developer_pedigree %}
    <div class="mt-3 text-sm">
      <span class="font-medium">Other titles by dev:</span>
      <span class="text-slate-700">{{ game.developer_pedigree }}</span>
    </div>
  {% endif %}

  {% if game.screenshots %}
    <div class="mt-3 flex gap-2 overflow-x-auto">
      {% for ss in game.screenshots %}
        <img src="{{ ss }}" alt="" class="h-40 rounded">
      {% endfor %}
    </div>
  {% endif %}

  {% if game.description_excerpt %}
    <p class="mt-3 text-sm text-slate-700 italic">"{{ game.description_excerpt }}"</p>
  {% endif %}

  <div class="mt-3 flex gap-3 text-sm">
    {% if game.play_url %}<a class="text-blue-700 hover:underline" href="{{ game.play_url }}">Play Store →</a>{% endif %}
    {% if game.ios_url %}<a class="text-blue-700 hover:underline" href="{{ game.ios_url }}">App Store →</a>{% endif %}
  </div>
</article>
{% endmacro %}
```

- [ ] **Step 3: Create `src/report/templates/weekly.html.j2`**

```html
{% extends "base.html.j2" %}
{% from "_card.html.j2" import render_card %}

{% block subheader %}
<p class="text-slate-600 mt-1">
  {{ totals.sustained }} Sustained Climbers ·
  {{ totals.fast }} Fast Climbers ·
  {{ totals.new }} New Entrants ·
  {{ totals.cross_platform }} ⚡ Cross-platform
</p>
{% if heartbeat.snapshots_this_week < 7 %}
  <div class="mt-3 inline-block bg-amber-50 border border-amber-200 text-amber-900 text-sm px-3 py-2 rounded">
    ⚠ Incomplete week — {{ heartbeat.snapshots_this_week }}/7 daily snapshots captured.
    Signals may be noisier than usual.
  </div>
{% endif %}
{% if cold_start %}
  <div class="mt-3 inline-block bg-sky-50 border border-sky-200 text-sky-900 text-sm px-3 py-2 rounded">
    ❄ Cold start — this report is based on less than 2 weeks of history.
    Sustained Climber signal will be reliable from {{ cold_start.full_from_date }}.
  </div>
{% endif %}
{% endblock %}

{% block content %}

{% for section_key, section in [('sustained', 'Sustained Climbers'), ('fast', 'Fast Climbers'), ('new', 'New Entrants')] %}
<section class="mb-10">
  <h2 class="text-xl font-semibold mb-4">{{ section }} ({{ sections[section_key]|length }})</h2>
  {% if sections[section_key] %}
    {% for game in sections[section_key] %}
      {{ render_card(game) }}
    {% endfor %}
  {% else %}
    <p class="text-slate-500 italic">No games in this category this week.</p>
  {% endif %}
</section>
{% endfor %}

{% if cross_platform_games %}
<section class="mb-10">
  <h2 class="text-xl font-semibold mb-4">⚡ Cross-platform signals ({{ cross_platform_games|length }})</h2>
  <p class="text-sm text-slate-600 mb-4">These games are already listed in their signal sections above. Listed here as a filtered view.</p>
  {% for game in cross_platform_games %}
    {{ render_card(game) }}
  {% endfor %}
</section>
{% endif %}

{% endblock %}
```

- [ ] **Step 4: Create `src/report/templates/archive.html.j2`**

```html
{% extends "base.html.j2" %}

{% block subheader %}
<p class="text-slate-600 mt-1">Weekly reports, most recent first.</p>
{% endblock %}

{% block content %}
<ul class="space-y-2">
  {% for report in reports %}
    <li>
      <a class="text-blue-700 hover:underline" href="{{ report.slug }}/">{{ report.date }}</a>
      <span class="text-slate-500 text-sm">
        — {{ report.totals.sustained }} sustained,
        {{ report.totals.fast }} fast,
        {{ report.totals.new }} new
        {% if report.totals.cross_platform %}, {{ report.totals.cross_platform }} ⚡{% endif %}
      </span>
    </li>
  {% else %}
    <li class="text-slate-500 italic">No reports yet.</li>
  {% endfor %}
</ul>
{% endblock %}
```

- [ ] **Step 5: Smoke-verify templates parse**

```bash
python -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('src/report/templates'))
for name in ['base.html.j2', '_card.html.j2', 'weekly.html.j2', 'archive.html.j2']:
    env.get_template(name)  # raises on syntax error
print('OK')
"
```

Expected: prints `OK`.

- [ ] **Step 6: Commit**

```bash
git add src/report/__init__.py src/report/templates/
git commit -m "feat: Jinja templates for weekly report, archive index, and game card"
```

---

## Task 14: HTML renderer

**Files:**
- Create: `src/report/render.py`
- Create: `tests/test_render.py`

- [ ] **Step 1: Write failing tests**

```python
from datetime import date
from pathlib import Path

from src.report.render import build_game_view, render_weekly, render_archive


def test_build_game_view_combines_signal_and_app_fields():
    app_row = {
        "app_id": "com.a", "platform": "play", "title": "Game A", "developer": "Studio X",
        "genre_bucket": "match3", "genre_raw": "GAME_PUZZLE", "release_date": "2026-04-01",
        "icon_url": "u", "description": "A match-3 puzzle game with cute graphics and a long story.",
        "price_tier": "free_iap", "screenshots": '["s1", "s2"]',
        "store_url": "https://play/",
    }
    signal_hit = {
        "app_id": "com.a", "platform": "play", "country": "IN",
        "signal": "sustained", "current_rank": 30, "rank_start": 84, "net_gain": 54,
    }
    ratings_current = {"rating_avg": 4.6, "rating_count": 12800}
    ratings_last_week = {"rating_count": 9600}

    view = build_game_view(
        app_row=app_row,
        signal_hit=signal_hit,
        ratings_current=ratings_current,
        ratings_last_week=ratings_last_week,
        cross_platform=False,
    )
    assert view["title"] == "Game A"
    assert view["signal_label"].startswith("Sustained")
    assert view["rating_count_delta"] == 3200
    assert view["screenshots"] == ["s1", "s2"]
    assert view["play_url"] == "https://play/"


def test_render_weekly_writes_html(tmp_path):
    sections = {"sustained": [], "fast": [], "new": []}
    out = render_weekly(
        out_dir=tmp_path,
        report_date=date(2026, 4, 20),
        sections=sections,
        cross_platform_games=[],
        totals={"sustained": 0, "fast": 0, "new": 0, "cross_platform": 0},
        heartbeat={"snapshots_this_week": 7},
        cold_start=None,
    )
    html = Path(out).read_text()
    assert "Sustained Climbers" in html
    assert "No games in this category" in html


def test_render_archive_lists_reports(tmp_path):
    reports = [
        {"slug": "2026-04-20", "date": "2026-04-20", "totals": {"sustained": 2, "fast": 1, "new": 3, "cross_platform": 0}},
        {"slug": "2026-04-13", "date": "2026-04-13", "totals": {"sustained": 0, "fast": 0, "new": 1, "cross_platform": 0}},
    ]
    path = render_archive(out_dir=tmp_path, reports=reports)
    html = Path(path).read_text()
    assert "2026-04-20" in html
    assert "2026-04-13" in html
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_render.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/report/render.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_render.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/report/render.py tests/test_render.py
git commit -m "feat: HTML renderer for weekly report and archive index"
```

---

## Task 15: Slack headline composer + poster

**Files:**
- Create: `src/report/slack.py`
- Create: `tests/test_slack.py`

- [ ] **Step 1: Write failing tests**

```python
from unittest.mock import patch, MagicMock

from src.report.slack import compose_headline, post_headline


def test_compose_headline_contains_totals_and_link():
    msg = compose_headline(
        report_date="2026-04-20",
        totals={"sustained": 8, "fast": 6, "new": 11, "cross_platform": 2},
        highlight={
            "title": "MergeFarm Tycoon",
            "signal_label": "Sustained Climber",
            "detail": "sustained climb across IN+BR, 4.6★, solo-dev studio with one prior hit",
        },
        full_report_url="https://user.github.io/games-scouting/2026-04-20/",
        archive_url="https://user.github.io/games-scouting/",
    )
    assert "8 Sustained Climbers" in msg
    assert "11 New Entrants" in msg
    assert "MergeFarm Tycoon" in msg
    assert "https://user.github.io/games-scouting/2026-04-20/" in msg


def test_compose_headline_no_highlight_when_empty():
    msg = compose_headline(
        report_date="2026-04-20",
        totals={"sustained": 0, "fast": 0, "new": 0, "cross_platform": 0},
        highlight=None,
        full_report_url="https://example.com/",
        archive_url="https://example.com/archive/",
    )
    assert "Highlight" not in msg
    assert "0 Sustained" in msg


def test_post_headline_sends_to_webhook():
    mock_resp = MagicMock(status_code=200, text="ok")
    with patch("src.report.slack.requests.post", return_value=mock_resp) as mp:
        post_headline("https://hooks.slack.com/services/FAKE", "hello")
    assert mp.call_count == 1
    _, kwargs = mp.call_args
    assert kwargs["json"] == {"text": "hello"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_slack.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/report/slack.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_slack.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/report/slack.py tests/test_slack.py
git commit -m "feat: slack headline composer and webhook poster"
```

---

## Task 16: Daily job orchestrator

**Files:**
- Create: `src/jobs/__init__.py` (empty)
- Create: `src/jobs/daily.py`
- Create: `tests/test_jobs_daily.py`

- [ ] **Step 1: Write failing test**

```python
from unittest.mock import patch
from datetime import date

from src.jobs.daily import run_daily


def test_run_daily_handles_per_chart_failure_without_aborting(db, tmp_path):
    """One failing chart should be logged and skipped; others should still persist."""
    good_result = [{"rank": 1, "app_id": "com.good"}, {"rank": 2, "app_id": "com.good2"}]

    def play_side_effect(country, chart_type, num):
        if country == "BR":
            raise RuntimeError("Play scraper broke for BR")
        return good_result

    with patch("src.jobs.daily.play_fetch_top_chart", side_effect=play_side_effect), \
         patch("src.jobs.daily.ios_fetch_top_chart", return_value=good_result):
        config = {
            "countries": {"play_store": ["IN", "BR"], "app_store": ["IN"]},
            "signals": {},  # not used by daily
            "genres": {},
        }
        stats = run_daily(
            conn=db,
            as_of=date(2026, 4, 15),
            config=config,
            chart_types=("top_free",),
        )

    rows = db.execute("SELECT COUNT(*) FROM chart_snapshots").fetchone()[0]
    # 1 successful Play (IN) × 2 games + 1 failed Play (BR) × 0 + 1 iOS (IN) × 2 = 4
    assert rows == 4
    assert stats["charts_ok"] == 2
    assert stats["charts_failed"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_jobs_daily.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/jobs/daily.py`**

```python
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
            result = _fetch_with_retry(fetch_fn, country=country, chart_type=chart_type, num=200 if platform == "play" else 100)
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
            raise SystemExit(f"[hard-fail] {platform}: {empty}/{total} charts empty — scraper likely broken")

    # Spec §9.1: hard-fail if >30% of charts failed overall
    total_charts = charts_ok + charts_failed
    if total_charts > 0 and charts_failed / total_charts > 0.3:
        raise SystemExit(f"[hard-fail] {charts_failed}/{total_charts} charts failed (>30% threshold)")

    log.info("daily done: %d ok, %d failed", charts_ok, charts_failed)
    return {"charts_ok": charts_ok, "charts_failed": charts_failed}


def main() -> None:
    """CLI entry — invoked by GitHub Actions."""
    import yaml
    from pathlib import Path
    from src.config import load_config
    from src.store.db import connect, init_schema

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    repo_root = Path(__file__).parent.parent.parent
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_jobs_daily.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/jobs/__init__.py src/jobs/daily.py tests/test_jobs_daily.py
git commit -m "feat: daily job orchestrator with retry, partial-failure tolerance, hard-fail thresholds"
```

---

## Task 17: Weekly job orchestrator

**Files:**
- Create: `src/jobs/weekly.py`
- Create: `tests/test_jobs_weekly.py`

- [ ] **Step 1: Write failing test**

```python
"""End-to-end test for weekly job: seed DB, run job, verify HTML + Slack were produced."""
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.jobs.weekly import run_weekly
from src.store.db import upsert_app, upsert_rating_snapshot
from tests.conftest import seed_ranks


def test_run_weekly_produces_html_and_slack(db, tmp_path):
    # Seed: one game that will qualify as Sustained Climber
    upsert_app(
        db, "com.a", "play",
        title="Merge Farm", developer="Studio X",
        genre_raw="GAME_SIMULATION", genre_bucket="casual_sim",
        release_date="2026-03-01", icon_url="u",
        description="merge farming tycoon game", price_tier="free_iap",
        screenshots_json="[]", store_url="https://play/",
        last_seen="2026-04-15",
    )
    upsert_rating_snapshot(db, "2026-04-15", "com.a", "play", 4.5, 10000)
    db.commit()

    seed_ranks(db, "com.a", "play", "IN", "top_free", {
        "2026-04-08": 90, "2026-04-09": 85, "2026-04-10": 80,
        "2026-04-11": 75, "2026-04-12": 70, "2026-04-13": 65,
        "2026-04-14": 60, "2026-04-15": 55,
    })

    config = {
        "countries": {"play_store": ["IN"], "app_store": []},
        "signals": {
            "fast_climber": {"min_rank_jump": 20, "window_days": 7, "max_current_rank": 100},
            "new_entrant": {"max_window_days": 14, "play_store_chart_ceiling": 200,
                            "app_store_chart_ceiling": 100, "recent_release_bonus_days": 90},
            "sustained_climber": {"min_rising_days_out_of": [5, 7], "alt_net_gain_threshold": 15,
                                  "max_reversal_streak": 3},
            "report": {"max_games_per_section": 10},
        },
        "genres": {
            "play_store": {"GAME_SIMULATION": "casual_sim"},
            "app_store": {},
            "keyword_overrides": {"hybrid_casual": ["merge", "tycoon"]},
        },
    }

    # Skip network calls for enrichment; DB already has the app row
    with patch("src.jobs.weekly.enrich_qualifying_apps") as mock_enrich, \
         patch("src.jobs.weekly.post_headline") as mock_slack:
        mock_enrich.return_value = None
        result = run_weekly(
            conn=db,
            as_of=date(2026, 4, 15),
            config=config,
            out_dir=tmp_path,
            base_url="https://u.github.io/gs",
            slack_webhook_url="https://hooks.slack.com/fake",
        )

    # HTML report written
    report_html = tmp_path / "2026-04-15" / "index.html"
    assert report_html.exists()
    assert "Merge Farm" in report_html.read_text()
    # Archive index written
    assert (tmp_path / "index.html").exists()
    # Slack posted
    assert mock_slack.call_count == 1
    # Totals returned
    assert result["totals"]["sustained"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_jobs_weekly.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `src/jobs/weekly.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_jobs_weekly.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/jobs/weekly.py tests/test_jobs_weekly.py
git commit -m "feat: weekly job — compute signals, enrich, render report, post Slack"
```

---

## Task 18: Daily GitHub Actions workflow

**Files:**
- Create: `.github/workflows/daily-snapshot.yml`

- [ ] **Step 1: Create the workflow**

```yaml
name: Daily snapshot

on:
  schedule:
    # 03:00 IST = 21:30 UTC (previous day)
    - cron: "30 21 * * *"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  snapshot:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    concurrency:
      group: snapshot
      cancel-in-progress: false
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Run daily snapshot
        env:
          CI: "true"
        run: python -m src.jobs.daily

      - name: Run scraper smoke tests
        env:
          CI: "true"
        run: pytest tests/test_scrape_smoke.py -v

      - name: Commit DB + logs
        run: |
          git config user.name  "games-scouting-bot"
          git config user.email "games-scouting-bot@users.noreply.github.com"
          git add data/ logs/ || true
          if ! git diff --staged --quiet; then
            git commit -m "chore(snapshot): $(date -u +%Y-%m-%d) daily chart snapshot"
            git push
          else
            echo "No changes to commit."
          fi
```

- [ ] **Step 2: Commit workflow**

```bash
git add .github/workflows/daily-snapshot.yml
git commit -m "ci: daily snapshot workflow (cron 03:00 IST)"
```

---

## Task 19: Weekly GitHub Actions workflow

**Files:**
- Create: `.github/workflows/weekly-report.yml`

- [ ] **Step 1: Create workflow**

```yaml
name: Weekly report

on:
  schedule:
    # Monday 10:00 IST = Monday 04:30 UTC
    - cron: "30 4 * * 1"
  workflow_dispatch:

permissions:
  contents: write
  pages: write
  id-token: write

jobs:
  report:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    concurrency:
      group: report
      cancel-in-progress: false
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Compute base URL
        id: base
        run: |
          # Repo slug: owner/repo → base URL of github pages
          OWNER=$(echo "$GITHUB_REPOSITORY" | cut -d/ -f1 | tr '[:upper:]' '[:lower:]')
          REPO=$(echo "$GITHUB_REPOSITORY"  | cut -d/ -f2)
          echo "url=https://${OWNER}.github.io/${REPO}" >> $GITHUB_OUTPUT

      - name: Run weekly report
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
          REPORT_BASE_URL: ${{ steps.base.outputs.url }}
          CI: "true"
        run: python -m src.jobs.weekly

      - name: Commit report
        run: |
          git config user.name  "games-scouting-bot"
          git config user.email "games-scouting-bot@users.noreply.github.com"
          git add docs/ logs/ || true
          if ! git diff --staged --quiet; then
            git commit -m "chore(report): $(date -u +%Y-%m-%d) weekly scouting report"
            git push
          fi
```

- [ ] **Step 2: Commit workflow**

```bash
git add .github/workflows/weekly-report.yml
git commit -m "ci: weekly report workflow (cron Mon 10:00 IST)"
```

---

## Task 20: Dry-run workflow

**Files:**
- Create: `.github/workflows/dry-run.yml`

- [ ] **Step 1: Create workflow**

```yaml
name: Dry-run weekly (manual only)

on:
  workflow_dispatch:
    inputs:
      test_webhook_url:
        description: "Slack webhook to post to (leave empty to skip Slack)"
        required: false
        type: string

jobs:
  dry_run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"
      - run: pip install -e ".[dev]"
      - name: Run weekly report into preview dir
        env:
          SLACK_WEBHOOK_URL: ${{ inputs.test_webhook_url }}
          REPORT_BASE_URL: "https://example.invalid/preview"
          CI: "true"
        run: |
          mkdir -p docs-preview
          cp -R data data-preview 2>/dev/null || true
          REPORT_OUT_OVERRIDE=docs-preview python -m src.jobs.weekly
      - name: Upload preview as artifact
        uses: actions/upload-artifact@v4
        with:
          name: weekly-preview
          path: docs-preview/
```

Note: the dry-run uses the env var `REPORT_OUT_OVERRIDE` — we need to plumb that through. Do it now in `src/jobs/weekly.py::main`:

- [ ] **Step 2: Update `main()` in `src/jobs/weekly.py` to honor `REPORT_OUT_OVERRIDE`**

In `src/jobs/weekly.py`, inside `main()`, change:

```python
    out_dir = repo_root / "docs"  # published via GitHub Pages from /docs on main
    out_dir.mkdir(exist_ok=True)
```

to:

```python
    out_dir_path = os.environ.get("REPORT_OUT_OVERRIDE", str(repo_root / "docs"))
    out_dir = Path(out_dir_path)
    out_dir.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/dry-run.yml src/jobs/weekly.py
git commit -m "ci: manual dry-run workflow for testing weekly pipeline safely"
```

---

## Task 21: Logging + heartbeat polish

**Files:**
- Modify: `src/jobs/daily.py` — add log-to-file
- Modify: `src/jobs/weekly.py` — add log-to-file

- [ ] **Step 1: Add logging helper**

Create `src/logging_setup.py`:

```python
"""Structured logging to both stdout and a dated file under logs/."""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path


def configure(repo_root: Path, job_name: str) -> None:
    logs_dir = repo_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / f"{date.today().isoformat()}-{job_name}.log"

    fmt = "%(asctime)s %(levelname)s %(name)s %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.FileHandler(log_file, mode="a", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
```

- [ ] **Step 2: Wire into daily and weekly mains**

In `src/jobs/daily.py::main()`, replace:

```python
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
```

with:

```python
    from src.logging_setup import configure
    configure(repo_root, "daily")
```

Same edit in `src/jobs/weekly.py::main()`, using `"weekly"` as the job name.

- [ ] **Step 3: Verify logs still appear during tests**

```bash
pytest tests/test_jobs_daily.py tests/test_jobs_weekly.py -v
```

Expected: tests still pass. Logs only get written when `main()` is invoked (via workflow), so tests are unaffected.

- [ ] **Step 4: Commit**

```bash
git add src/logging_setup.py src/jobs/daily.py src/jobs/weekly.py
git commit -m "feat: persistent dated logs in logs/ directory"
```

---

## Task 22: README + ops runbook

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rewrite README**

```markdown
# Games Scouting Agent

Weekly Monday 10 AM IST scouting report on casual/mass-market games climbing
the Play Store and App Store charts across 8 markets (IN, US, JP, KR, CN, DE, GB, BR).
Posts a headline to Slack `#new-games`, full report hosted on GitHub Pages.

- Design spec: [docs/superpowers/specs/2026-04-16-games-scouting-agent-design.md](docs/superpowers/specs/2026-04-16-games-scouting-agent-design.md)
- Implementation plan: [docs/superpowers/plans/2026-04-16-games-scouting-agent.md](docs/superpowers/plans/2026-04-16-games-scouting-agent.md)

## How it works

Two GitHub Actions cron jobs:

- `daily-snapshot.yml` — runs 03:00 IST every day, scrapes all top charts,
  commits updated SQLite DB + logs.
- `weekly-report.yml` — runs Monday 10:00 IST, computes velocity signals
  (Fast Climber / New Entrant / Sustained Climber), filters to watchlist
  genres (match-3, hypercasual, hybrid-casual, word & trivia, casual sim),
  renders HTML report into `docs/` (served by GitHub Pages), posts Slack
  headline.

Data sources are all free: Apple's official RSS feeds, iTunes Search API,
and the `google-play-scraper` Python library.

## Setup

1. Create a GitHub repo and push this code.
2. Add a secret: **`SLACK_WEBHOOK_URL`** = incoming webhook for `#new-games`.
   (Settings → Secrets and variables → Actions → New repository secret.)
3. Enable GitHub Pages: Settings → Pages → Source = "Deploy from a branch" →
   Branch = `main` / folder = `/docs`.
4. That's it. First daily run triggers the next scheduled tick; to seed
   immediately, trigger `daily-snapshot.yml` manually via the Actions tab.

## Cold start

Signals depend on rank history the agent builds up itself.

- Week 1: only New Entrant works (everything else has no history yet)
- Week 2: Fast Climber starts working
- Week 3+: Sustained Climber works, report is complete

Reports still ship during cold start with a banner explaining the state.

## Local development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Run daily snapshot against local DB
python -m src.jobs.daily

# Run weekly report (posts to Slack if webhook set)
SLACK_WEBHOOK_URL="<hook>" REPORT_BASE_URL="https://example.com" python -m src.jobs.weekly
```

## Operations

**Monitoring:** GitHub Actions emails you on failed runs. Weekly report's
HTML header shows X/7 snapshot completeness for the week (heartbeat).

**Silent scraper breakage:** the daily job hard-fails if >50% of a platform's
charts return empty results, so `google-play-scraper` layout changes are
caught within 24 hours, not the following Monday.

**Tuning thresholds:** edit `config/signals.yaml` and open a PR. Run the
**Dry-run weekly** workflow (Actions tab) to preview a report before merging.

**Genre mapping fixes:** edit `config/genres.yaml`. The current mapping is
a hand-curated first pass; casual/hypercasual labels in both stores are
notoriously sloppy and the keyword heuristic catches many cases.

## Scope

In: watchlist genres (match-3, hypercasual, hybrid-casual, word & trivia,
casual sim), 7 Play + 8 iOS countries, three velocity signals.

Out: paid data sources, mid-core/core genres, install and revenue
estimates, ad creative analysis, social-media buzz, real-money gaming.

## Repository layout

```
.github/workflows/   CI jobs (daily, weekly, dry-run)
config/              Countries, genres, signal thresholds
data/                SQLite DB (committed)
docs/                Published GitHub Pages site (weekly reports + archive)
docs/superpowers/    Design spec + implementation plan
logs/                Dated run logs (committed)
src/
  scrape/            External-facing scrapers (Play, iOS)
  store/             SQLite schema + access layer
  signals/           Fast Climber / New Entrant / Sustained / Cross-platform
  report/            Jinja templates, HTML renderer, Slack poster
  jobs/              Daily and weekly orchestrators
tests/
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with setup, operations, cold start, and layout notes"
```

---

## Self-review checklist (for the implementer, after Task 22)

Before declaring done, verify:

- [ ] All 22 tasks committed as separate commits
- [ ] `pytest` passes cleanly locally
- [ ] `pytest -m "not vcr" tests/` passes without internet
- [ ] `CI=true pytest tests/test_scrape_smoke.py` passes using only recorded cassettes
- [ ] Both workflows visible in GitHub Actions tab with valid schedules
- [ ] `SLACK_WEBHOOK_URL` secret exists in repo settings
- [ ] GitHub Pages serves from `main:/docs`
- [ ] Manual dry-run via `workflow_dispatch` produces an artifact
- [ ] Trigger `daily-snapshot.yml` manually once; verify DB commit appears
- [ ] Week-3 report renders without cold-start banner (verify after ~14 days of daily runs)
