# Games Scouting Agent — Progress Snapshot

**Paused on:** 2026-04-16
**Status:** 5 of 22 tasks complete. Foundation + scrapers done. Signal logic next.

---

## What's built

### Completed tasks (5/22)

| # | Task | Commit |
|---|------|--------|
| 1 | Repo bootstrap (git, Python 3.14, deps, scaffold) | `22bf007` |
|   | Docs (spec + plan committed) | `9f4eea2` |
| 2 | Config files & loader | `826edaf` |
| 3 | SQLite schema & db module | `8bd98f2` |
| 4 | Play Store scraper (via npm subprocess) | `66c3389` |
| 5 | App Store scraper (initial) | `6239b91` |
|   | App Store fix (legacy iTunes RSS with genre filter) | `e405972` |

### Test suite

14 tests passing, all offline (mocked):

```
tests/test_app_store_scraper.py     4 tests
tests/test_config.py                3 tests
tests/test_db.py                    3 tests
tests/test_play_store_scraper.py    4 tests
```

Run with: `source .venv/bin/activate && pytest -v`

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
│   ├── scrape/
│   │   ├── __init__.py
│   │   ├── app_store.py
│   │   └── play_store.py
│   └── store/
│       ├── __init__.py
│       ├── db.py
│       └── schema.sql
└── tests/
    ├── __init__.py
    ├── test_app_store_scraper.py
    ├── test_config.py
    ├── test_db.py
    └── test_play_store_scraper.py
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

### Next up: Task 6 — VCR smoke tests

**Scope:** Recorded-HTTP-fixture tests using `vcrpy` to detect changes in the shape of external API responses without hitting the live network in CI.

**Adjustments from plan given deviations above:**
- App Store cassette path: records against legacy `itunes.apple.com` URLs (no plan change; the URL is already correct in the updated scraper).
- Play Store cassette: the plan already said "may not record cleanly"; even more true now since subprocess doesn't go through `requests`. The test should skip gracefully in CI when the cassette is absent.

### After Task 6 — Task 7 onward

Signals (7-11), enrichment (12), rendering (13-15), orchestrators (16-17), CI (18-20), polish (21-22). Most of this is pure Python with no external surprises. The plan as written should work; the only consequential changes needed are:

- **Task 18 (daily CI workflow):** add `actions/setup-node@v4` step + `npm install` before `python -m src.jobs.daily`. The plan's YAML needs those two lines inserted.
- **Task 20 (dry-run CI workflow):** same Node setup.
- **Task 17 (weekly job orchestrator):** no change — does not touch the Play Store scraper directly.

No other plan content is affected.

---

## How to pick up

1. `cd "/Users/apple/Desktop/games agent"`
2. `source .venv/bin/activate`
3. `pytest -v` — confirm 14 tests still pass
4. Open the plan: `docs/superpowers/plans/2026-04-16-games-scouting-agent.md`
5. Task 6 begins at the "### Task 6: VCR smoke tests for scrapers" section

When resuming, the conversation can reference this PROGRESS.md to restore context.

---

## Open items / risks to revisit

- **Deprecated iTunes RSS:** May break with Apple's next cleanup pass. Fallback path is documented in `src/scrape/app_store.py` module docstring.
- **`google-play-scraper` npm v10.1.2 is ESM:** If the library ever reverts to CJS or changes its export shape, the `.mjs` script will need updating. Pinning to `^10.0.0` for now.
- **`package-lock.json` is gitignored** — not committed for determinism. Revisit if we want reproducible Node installs in CI (probably yes; CI will generate a fresh one each run, slight risk of drift).
- **Thresholds in `config/signals.yaml`** — educated guesses. Expect tuning after 2-3 real weekly reports.
- **Cold start** — no rank history yet. First Sustained Climber signals reliable ~14 days after daily job starts running.
