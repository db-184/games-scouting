# Games Scouting Agent — Design Spec

**Date:** 2026-04-16
**Owner:** product.tools@bebetta.in
**Status:** Approved, pending implementation plan

---

## 1. Purpose

An automated agent that surfaces mobile games climbing the Play Store and App Store charts each week, to support **publishing-pipeline scouting** — identifying genres, mechanics, and themes worth greenlighting, licensing, or localizing.

The agent delivers a weekly scouting report every **Monday at 10:00 AM IST** to the company Slack channel `#new-games`, with a short headline message linking to a richer hosted report on GitHub Pages.

---

## 2. Scope

### 2.1 Platforms
Both Google Play Store (Android) and Apple App Store (iOS), with a **unified cross-platform view** — the agent detects when a title is rising on both stores and flags this as a stronger signal.

### 2.2 Markets (countries)

- **Play Store (7):** IN, US, JP, KR, DE, UK, BR
  - China is excluded (no Play Store in mainland China)
- **App Store (8):** IN, US, JP, KR, CN, DE, UK, BR

India is the anchor market; global top markets are tracked alongside.

### 2.3 Genre watchlist

The agent filters to casual/mass-market genres:

- Match-3 / puzzle
- Hypercasual (ad-monetized, simple loops)
- Hybrid-casual (casual gameplay + meta progression)
- Word & trivia
- Casual simulation (farming, merge, idle)

Games outside these genres are still stored in the database (for future mapping tweaks) but excluded from the report.

### 2.4 Out of scope

- Mid-core / core genres (RPG, strategy, shooter, card, action)
- Real-money skill gaming
- Paid data sources (Sensor Tower, data.ai, AppMagic, AppFollow paid tiers)
- Revenue and install estimates (not available free)
- Ad creative analysis
- Social-media buzz tracking (TikTok, YouTube)

---

## 3. Signals — what "climbing rapidly" means

Three signal types run in parallel; every surfaced game is tagged with exactly one (highest-priority signal wins).

### 3.1 Fast Climber
- Rank jumped **≥20 positions** in any watched chart over the last **7 days**
- Current rank must be inside **Top 100**
- Ranked by jump magnitude; tie-breaker = higher current rank
- *Intent:* catches games catching fire right now

### 3.2 New Entrant
- First appeared in **Top 200** (Play) or **Top 100** (iOS) within the last **14 days**
- Must still be charting on report day
- Extra weight if release date is **<90 days old** (genuinely new, not a re-release)
- *Intent:* fresh titles breaking through that weren't on our radar

### 3.3 Sustained Climber
- Rank improved on **≥5 of the last 7 days**, OR net **+15 ranks** over 7 days with no >3-day reversal
- *Intent:* organic word-of-mouth, not a paid-UA spike — the strongest publishing signal

### 3.4 Cross-platform tag
- A title is cross-platform matched by fuzzy dev + title match
- If a game satisfies any signal on **both** Play and App Store in the same week, it receives a `⚡ Cross-platform` tag
- The tag is **additive** to the game's signal-section listing — the cross-platform appendix in the report (§5.2) is a filtered view of games already listed in their respective sections, not a separate dedup bucket

### 3.5 Priority & dedup
- A game appears in **one** section only
- Priority: Sustained > Fast Climber > New Entrant
- Each section shows up to **10 games**, sorted by signal strength

### 3.6 Thresholds are config
All numeric thresholds above live in `config/signals.yaml` and can be tuned without code changes. Expect tuning in the first month of operation.

---

## 4. Per-game information in the report

For each surfaced game, the report card includes:

### Identity
- Title
- Developer / publisher name
- Icon
- Store links (Play and/or App Store)

### Chart signal — the "why it's here"
- Signal type (Fast Climber / New Entrant / Sustained Climber)
- Current rank + rank change vs. last week
- Country and chart where it's climbing
- Cross-platform flag (if applicable)

### Game profile
- Genre / sub-genre (mapped to watchlist bucket)
- Release date (global; in-market if different)
- Price model (free + IAP / paid / subscription)

### Traction proxies
- Average rating (stars)
- Rating count
- Rating count change week-over-week (free-tier proxy for install momentum)

### Publishing lens
- Developer pedigree — other titles by the same dev, whether any also chart
- Screenshots (2–3 thumbnails)
- Short description excerpt

### Explicitly excluded
- Size, minimum OS, languages supported *(per-device metadata, low signal value)*
- Top review themes / auto-summarized reviews
- Update frequency / last-updated date / release cadence

---

## 5. Delivery

### 5.1 Slack headline (weekly, Monday 10 AM IST)

Posted to `#new-games`. Short and skimmable; links to the full hosted report.

Example:

```
🎮 Weekly Games Scouting Report — Mon 21 Apr 2026

This week's movers in casual/mass-market:
• 8 Sustained Climbers
• 6 Fast Climbers
• 11 New Entrants
• 2 ⚡ Cross-platform signals

Highlight: "MergeFarm Tycoon" — sustained climb across IN+BR,
4.6★, solo-dev studio with one prior hit.

📊 Full report → https://<owner>.github.io/<repo>/2026-04-21/
📁 Archive → https://<owner>.github.io/<repo>/
```

The "Highlight" is auto-selected: strongest signal in the report (cross-platform Sustained > Sustained > rest).

### 5.2 Hosted report (GitHub Pages)

Published to `https://<owner>.github.io/<repo>/YYYY-MM-DD/`, plus archive index at `/`.

**Layout:**
- Header: week-of date, total counts, methodology link, data-quality banner (if any)
- Section 1: Sustained Climbers (most important first)
- Section 2: Fast Climbers
- Section 3: New Entrants
- Appendix: Cross-platform signals (if any present)

**Per-game card** renders the fields listed in §4.

**Archive index** (`/index.html`):
- Reverse-chronological list of all weekly reports
- Simple filter by genre and signal type across history

**Styling:** Clean, minimal. Tailwind via CDN (no build step).

**Access:** Public URL, not indexed / not advertised beyond Slack.

---

## 6. Architecture

### 6.1 Repository

A single GitHub repository contains code, database, report templates, and published site.

### 6.2 Workflows (two)

**Daily snapshot** (`daily-snapshot.yml`)
- Schedule: cron, ~03:00 IST every day
- Scrapes all charts across all countries + platforms
- Updates SQLite DB, commits back to `main`
- Runtime: ~2–5 minutes

**Weekly report** (`weekly-report.yml`)
- Schedule: cron, 10:00 IST every Monday
- Reads last 7–14 days of snapshots from SQLite
- Computes signals, filters to watchlist genres
- Fetches fresh metadata for qualifying games
- Renders HTML report, publishes to `gh-pages`
- Posts Slack headline with permalink
- Runtime: ~5–10 minutes

Both run comfortably inside GitHub Actions' free 2,000-minute monthly allowance.

### 6.3 Data flow

```
Daily ~3 AM IST:
  fetch top charts (Play: 7 countries, iOS: 8 countries, 3 chart types each)
    → parse → store in SQLite → commit DB

Weekly Mon 10 AM IST:
  read last 7–14 days from SQLite
    → compute Fast / New / Sustained signals
    → filter to watchlist genres
    → fetch fresh metadata for qualifying games
    → render HTML (weekly page + archive index)
    → publish to gh-pages
    → post Slack webhook
```

### 6.4 Data sources (all free)

**Play Store:**
- `google-play-scraper` Python library — top charts (`list()`) + metadata (`app()`)
- Top 200 per chart type per country

**App Store:**
- Apple's official RSS feeds: `rss.applemarketingtools.com/api/v2/{country}/apps/{top-free|top-paid|top-grossing}/100/games.json` — top 100, sanctioned
- iTunes Search API for metadata (dev, ratings, screenshots, description) — free, no key

**Secrets required:**
- `SLACK_WEBHOOK_URL` (GitHub Actions secret) — that's it

### 6.5 Storage

SQLite committed to the repo in `data/scouting.sqlite`.

**Tables:**
- `chart_snapshots` — (date, country, platform, chart_type, rank, app_id) — powers velocity signals
- `apps` — (app_id, platform, title, developer, genre, release_date, icon_url, …) — metadata, opportunistically refreshed
- `app_ratings_history` — (date, app_id, rating_avg, rating_count) — weekly rating-count delta

Data volume: ~10 MB/year. SQLite-in-repo is appropriate at this scale; every commit is a free backup.

---

## 7. Module boundaries

```
src/
├── scrape/           # external-facing, failure-prone (isolated)
│   ├── play_store.py
│   └── app_store.py
├── store/            # DB schema, connections, queries
│   ├── schema.sql
│   └── db.py
├── signals/          # pure logic over DB — easy to unit-test
│   ├── fast_climber.py
│   ├── new_entrant.py
│   ├── sustained.py
│   └── cross_platform.py
├── report/           # read-only; never scrapes or mutates
│   ├── templates/    # Jinja HTML
│   ├── render.py
│   └── slack.py
├── genre_filter.py   # store-genre → watchlist-bucket mapping
└── jobs/             # thin orchestrators — no business logic
    ├── daily.py
    └── weekly.py
```

**Principles:**
- Each module has one job; units can be understood and tested independently
- Scraping is isolated so flakiness doesn't leak into logic or reporting
- Signals and genre filtering are pure over the DB — deterministic and testable
- Reporting is read-only

### 7.1 Config files

```
config/
├── countries.yaml    # countries per platform
├── genres.yaml       # store-genre → watchlist-bucket map (hand-curated)
└── signals.yaml      # all numeric thresholds
```

---

## 8. Cold start

Signals depend on rank history that the agent itself builds up day by day.

| Week after deploy | What works |
|-------------------|------------|
| Week 1 | Only New Entrant signal (needs release date only); report shows cold-start banner |
| Week 2 | Fast Climber begins working (~7d of history available) |
| Week 3+ | Sustained Climber works fully; report is complete |

Reports from weeks 1 and 2 still ship — thinner, with a banner explaining the cold-start state.

**Optional seed:** a one-time scrape of free public sources that expose current ranks (not history) can reduce false "new entrants" in week 1. Default is to skip seeding and let the agent warm up naturally.

---

## 9. Failure handling

### 9.1 Daily scrape

- Each (country × platform × chart) fetch wrapped in 3 retries with exponential backoff
- Single-chart failures after retries are logged and skipped; the rest of the run continues
- If **>30%** of charts fail in one run, the job hard-fails (GitHub shows red X)
- If **>50%** of a single platform's charts return 0 results, treat as hard failure — this pattern signals the scraper library or RSS feed is broken (e.g., Play Store layout change), distinct from a one-off chart hiccup

### 9.2 Weekly report

- If daily data is missing on >2 of the last 7 days, the report adds a "⚠ incomplete week" banner in both Slack and the HTML header
- Slack post is the final step — if it fails, the report is still published; Actions run goes red

### 9.3 Scraping resilience

`google-play-scraper` is the fragile link. When it breaks, empty results surge; the "0 results" check catches this within 24 hours instead of waiting for Monday.

---

## 10. Observability (free)

- **GitHub Actions email alerts** — primary monitor; GitHub emails on failed runs
- **Weekly heartbeat in HTML header** — "X/7 daily snapshots captured this week"; surfaces silent gaps visually
- **Structured logs** — each run writes a dated log to `logs/`, committed to the repo for historical review

No paid tools (no Sentry/Datadog).

---

## 11. Testing

- **Unit tests** on signal computation using fixture SQLite DBs with known histories *(where most bugs will live)*
- **Unit tests** on genre mapping; grow the corpus whenever a miscategorized game is spotted
- **Smoke tests** on scrapers using recorded HTTP fixtures (e.g., `vcrpy`) to catch changes in `google-play-scraper` return shape without hitting the network in CI
- **Dry-run workflow** (`workflow_dispatch`) runs the full weekly pipeline but posts to a test Slack channel and writes the report to a preview path — use before rolling out threshold changes
- **No tests hit live Play/App Store** in CI (too flaky)

---

## 12. Runtime stack

- Python 3.12
- Dependencies (lean, ~5): `google-play-scraper`, `requests`, `jinja2`, `pyyaml`, `slack-sdk` (or plain `requests`)
- `sqlite3` from stdlib
- Hosting: GitHub Actions (compute) + GitHub Pages (report hosting) + GitHub (storage)
- Total recurring cost: **$0**

---

## 13. Known unknowns / risks

- **`google-play-scraper` maintenance:** actively maintained today, but a layout change could silently break scraping. Mitigated by 0-result checks and weekly heartbeat.
- **Genre mapping drift:** both stores categorize "hypercasual" inconsistently ("Arcade", "Casual", etc.). A hand-curated mapping + keyword heuristics handle the first pass; expect manual tuning in the first month.
- **Cross-platform dedup:** fuzzy title+dev matching will have false negatives (titles differ slightly across stores) and occasional false positives (two unrelated devs with the same game name). Acceptable at this scale; can tighten later.
- **No install/revenue data:** rating-count delta is a proxy for engagement momentum, not downloads. Good enough for scouting, not for financial modeling.
- **Threshold tuning:** the numbers in §3 are educated guesses. Expect to tune after 2–3 weeks of real output.

---

## 14. Explicitly deferred

- Real-money / skill gaming coverage (separate regulatory considerations)
- Mid-core and core genres (outside current publishing focus)
- Ad creative sampling (requires paid data source)
- Social-media buzz signals (TikTok, YouTube)
- Paid data sources of any kind
- Multi-recipient Slack targeting beyond `#new-games`
- Email or other delivery channels
