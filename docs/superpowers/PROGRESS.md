# Games Scouting Agent — Progress Snapshot

**Paused on:** 2026-04-16 (batch 2 complete)
**Status:** 12 of 22 tasks complete. Foundation + scrapers + all signal logic done. Reporting, jobs, and CI next.

---

## What's built

### Completed tasks (12/22)

| # | Task | Commit |
|---|------|--------|
| 1 | Repo bootstrap (git, Python 3.14, deps, scaffold) | `22bf007` |
|   | Docs (spec + plan committed) | `9f4eea2` |
| 2 | Config files & loader | `826edaf` |
| 3 | SQLite schema & db module | `8bd98f2` |
| 4 | Play Store scraper (via npm subprocess) | `66c3389` |
| 5 | App Store scraper (initial) | `6239b91` |
|   | App Store fix (legacy iTunes RSS with genre filter) | `e405972` |
|   | Batch 1 pause marker | `165f540` |
| 6 | VCR smoke tests on App Store scrapers | `a2c681a` |
| 7 | Genre filter (store genre + keyword overrides) | `81ca72e` |
| 8 | Fast Climber signal (≥20 rank jump in 7d) | `53c982e` |
| 9 | New Entrant signal (first seen within 14d) | `8866b18` |
| 10 | Sustained Climber signal (5-of-7 OR +15 net) | `7b57bdd` |
| 11 | Cross-platform matcher + section composer | `91ee4c3` |
| 12 | Metadata enrichment (scraper + genre_filter → db) | `505000f` |

### Test suite

41 tests passing, all offline (mocked or VCR cassettes):

```
tests/test_app_store_scraper.py     4 tests
tests/test_compose.py               2 tests
tests/test_config.py                3 tests
tests/test_cross_platform.py        3 tests
tests/test_db.py                    3 tests
tests/test_enrich.py                2 tests
tests/test_fast_climber.py          5 tests
tests/test_genre_filter.py          5 tests
tests/test_new_entrant.py           4 tests
tests/test_play_store_scraper.py    4 tests
tests/test_scrape_smoke.py          2 tests   (VCR cassette replay)
tests/test_sustained.py             4 tests
```

Run with: `source .venv/bin/activate && pytest -v`
CI-style offline run: `CI=true pytest -v` (VCR cassettes must exist; won't re-record)

### Live-tested endpoints (verified working)

- Play Store (via Node subprocess): `node scripts/fetch_play_chart.mjs US top_free 10` returns ranked games
- App Store (legacy iTunes RSS): `fetch_top_chart('US', 'top_free', 5)` returns ranked game IDs

### Repo layout on disk

```
games agent/
├── .github/              (not yet — Task 18/19/20)
├── .gitignore
├── .venv/                (Python 3.14 virtual env, local only)
├── config/
│   ├── countries.yaml
│   ├── genres.yaml
│   └── signals.yaml
├── docs/
│   └── superpowers/
│       ├── specs/2026-04-16-games-scouting-agent-design.md
│       ├── plans/2026-04-16-games-scouting-agent.md
│       └── PROGRESS.md   (this file)
├── node_modules/          (gitignored; Node deps for Play Store scraper)
├── package.json
├── pyproject.toml
├── README.md              (stub; full README is Task 22)
├── scripts/
│   └── fetch_play_chart.mjs
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── genre_filter.py         ← Task 7
│   ├── scrape/
│   │   ├── __init__.py
│   │   ├── app_store.py
│   │   └── play_store.py
│   ├── signals/                ← Tasks 8-12
│   │   ├── __init__.py
│   │   ├── compose.py
│   │   ├── cross_platform.py
│   │   ├── enrich.py
│   │   ├── fast_climber.py
│   │   ├── new_entrant.py
│   │   └── sustained.py
│   └── store/
│       ├── __init__.py
│       ├── db.py
│       └── schema.sql
└── tests/
    ├── __init__.py
    ├── conftest.py             ← Shared db fixture + seed_ranks helper
    ├── fixtures/cassettes/     ← VCR recordings (2 YAML files, ~440 KB total)
    ├── test_app_store_scraper.py
    ├── test_compose.py
    ├── test_config.py
    ├── test_cross_platform.py
    ├── test_db.py
    ├── test_enrich.py
    ├── test_fast_climber.py
    ├── test_genre_filter.py
    ├── test_new_entrant.py
    ├── test_play_store_scraper.py
    ├── test_scrape_smoke.py
    └── test_sustained.py
```

---

## Deviations from the plan that affect later tasks

### 1. Play Store: Node.js subprocess, not pure Python

**What changed:** The plan assumed the Python `google-play-scraper` library had `list()` / `collection` — it doesn't (only the JavaScript port does). We installed the npm library and call it from Python via `subprocess`.

**Files affected:**
- `package.json` (Node deps)
- `scripts/fetch_play_chart.mjs` (ESM script — v10+ of google-play-scraper is ESM-only)
- `src/scrape/play_store.py` uses `subprocess.run(['node', ...])` for `fetch_top_chart`
- App metadata (`fetch_app_metadata`) still uses the Python library — `app()` does work there

**Downstream impact:**
- **Task 18 (daily GitHub Actions workflow)** — must add `actions/setup-node@v4` step before the Python install. Example:
  ```yaml
  - uses: actions/setup-node@v4
    with:
      node-version: "22"
  - run: npm install
  ```
- **Task 20 (dry-run workflow)** — same Node setup needed.
- **Task 6 (VCR smoke tests)** — the Play Store live test cassette will not record because the subprocess doesn't go through Python's `requests`. The plan already flagged this as likely; the Play Store cassette test will be skipped in CI.

### 2. App Store: legacy iTunes RSS, not modern marketing-tools API

**What changed:** The plan used `rss.applemarketingtools.com/api/v2/...` but that endpoint (a) has no games-genre filter — it returns all top apps, and (b) uses `apps.json` not `games.json` as the last path segment. The legacy `itunes.apple.com/{country}/rss/.../genre=6014/json` endpoint does filter to games and still works.

**Files affected:**
- `src/scrape/app_store.py` — URL construction and response parsing changed (`feed.entry` instead of `feed.results`, app ID at `entry.id.attributes["im:id"]`)
- `tests/test_app_store_scraper.py` — fixture shape updated; new regression test asserts the URL uses `genre=6014`

**Risk:** The legacy endpoint is deprecated (though still live). If Apple turns it off, fallback is to use the modern `apps.json` endpoint and do per-app genre lookups via the iTunes Search API — ~8,000 extra calls/day. Not urgent; documented in the scraper module docstring.

**Downstream impact:**
- **Task 6 (VCR smoke tests)** — cassette will record the new URL shape; no code change to the test plan.

### 3. Python 3.14 instead of 3.12

**What changed:** Machine doesn't have `python3.12`; it has `python3` = 3.14.3. The `requires-python = ">=3.12"` in `pyproject.toml` is satisfied by 3.14, so this is a non-issue for code but worth noting.

**Downstream impact:**
- **CI workflows (Tasks 18/19/20)** — use `python-version: "3.12"` in `actions/setup-python` (not 3.14) for CI reproducibility. Works fine; the `>=3.12` floor is what matters.

---

## Where to resume

### Next up: Task 13 — Jinja templates

**Scope:** Build 4 HTML templates (base.html.j2, weekly.html.j2, archive.html.j2, _card.html.j2) with Tailwind CSS via CDN. Starts the reporting layer.

### After Task 13 — Tasks 14-22

- **Task 14:** HTML renderer (`build_game_view`, `render_weekly`, `render_archive`)
- **Task 15:** Slack headline composer + webhook poster
- **Task 16:** Daily job orchestrator — scrape all charts, retry, commit DB
- **Task 17:** Weekly job orchestrator — compute signals, enrich, render, post Slack
- **Task 18:** Daily GitHub Actions workflow *(needs `actions/setup-node@v4` added)*
- **Task 19:** Weekly GitHub Actions workflow
- **Task 20:** Dry-run workflow *(needs `actions/setup-node@v4` added)*
- **Task 21:** Logging + heartbeat polish
- **Task 22:** Full README + ops runbook

### Outstanding plan adjustments still required

- **Task 18 (daily CI workflow):** add `actions/setup-node@v4` + `npm install` steps before Python install
- **Task 20 (dry-run CI workflow):** same Node setup

No other plan content needs adjustment.

---

## How to pick up

1. `cd "/Users/apple/Desktop/games agent"`
2. `source .venv/bin/activate`
3. `pytest -v` — confirm 41 tests still pass
4. Open the plan: `docs/superpowers/plans/2026-04-16-games-scouting-agent.md`
5. Task 13 begins at the "### Task 13: Jinja templates" section

When resuming, the conversation can reference this PROGRESS.md to restore context.

---

## Open items / risks to revisit

- **Deprecated iTunes RSS:** May break with Apple's next cleanup pass. Fallback path is documented in `src/scrape/app_store.py` module docstring.
- **`google-play-scraper` npm v10.1.2 is ESM:** If the library ever reverts to CJS or changes its export shape, the `.mjs` script will need updating. Pinning to `^10.0.0` for now.
- **`package-lock.json` is gitignored** — not committed for determinism. Revisit if we want reproducible Node installs in CI (probably yes; CI will generate a fresh one each run, slight risk of drift).
- **Thresholds in `config/signals.yaml`** — educated guesses. Expect tuning after 2-3 real weekly reports.
- **Cold start** — no rank history yet. First Sustained Climber signals reliable ~14 days after daily job starts running.
