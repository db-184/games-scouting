# Games Scouting Agent

Weekly Monday 10 AM IST scouting report on casual/mass-market games climbing
the Play Store and App Store charts across 8 markets (IN, US, JP, KR, CN, DE, GB, BR).
Posts a headline to Slack `#new-games`, full report hosted on GitHub Pages.

- Design spec: [docs/superpowers/specs/2026-04-16-games-scouting-agent-design.md](docs/superpowers/specs/2026-04-16-games-scouting-agent-design.md)
- Implementation plan: [docs/superpowers/plans/2026-04-16-games-scouting-agent.md](docs/superpowers/plans/2026-04-16-games-scouting-agent.md)

## How it works

Two GitHub Actions cron jobs:

- `daily-snapshot.yml` — runs 03:00 IST every day, scrapes all top charts
  (Play Store via Node.js subprocess, App Store via legacy iTunes RSS),
  commits updated SQLite DB + logs.
- `weekly-report.yml` — runs Monday 10:00 IST, computes velocity signals
  (Fast Climber / New Entrant / Sustained Climber), filters to watchlist
  genres (match-3, hypercasual, hybrid-casual, word & trivia, casual sim),
  renders HTML report into `docs/` (served by GitHub Pages), posts Slack
  headline.

Data sources are all free: legacy Apple iTunes RSS feeds (with genre=6014
for games), iTunes Search API, npm `google-play-scraper` library (via
Node.js subprocess for charts, Python port for individual app metadata).

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
# Python + Node setup
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
npm install

# Run tests (offline, mocked + VCR cassettes)
pytest

# Run daily snapshot against local DB (hits live APIs)
python -m src.jobs.daily

# Run weekly report (posts to Slack if webhook set)
SLACK_WEBHOOK_URL="<hook>" REPORT_BASE_URL="https://example.com" python -m src.jobs.weekly
```

## Operations

**Monitoring:** GitHub Actions emails you on failed runs. Weekly report's
HTML header shows X/7 snapshot completeness for the week (heartbeat).

**Silent scraper breakage:** the daily job hard-fails if >50% of a platform's
charts return empty results, so scraper library layout changes are caught
within 24 hours, not the following Monday.

**Tuning thresholds:** edit `config/signals.yaml` and open a PR. Run the
**Dry-run weekly** workflow (Actions tab) to preview a report before merging.

**Genre mapping fixes:** edit `config/genres.yaml`. The current mapping is
a hand-curated first pass; casual/hypercasual labels in both stores are
notoriously sloppy and the keyword heuristic catches many cases.

**Logs:** each daily and weekly run writes a dated log to `logs/` and commits
it. Review in GitHub for operational history.

## Scope

In: watchlist genres (match-3, hypercasual, hybrid-casual, word & trivia,
casual sim), 7 Play + 8 iOS countries, three velocity signals.

Out: paid data sources, mid-core/core genres, install and revenue
estimates, ad creative analysis, social-media buzz, real-money gaming.

## Repository layout

```
.github/workflows/   CI jobs (daily, weekly, dry-run)
config/              Countries, genres, signal thresholds (YAML)
data/                SQLite DB (committed, ~10 MB/year)
docs/                Published GitHub Pages site (weekly reports + archive)
docs/superpowers/    Design spec + implementation plan
logs/                Dated run logs (committed)
scripts/             fetch_play_chart.mjs (Node.js helper for Play Store)
src/
  config.py          Config loader
  genre_filter.py    Store-genre → watchlist-bucket mapper
  logging_setup.py   Dual stdout + file logging
  scrape/            Play Store (Node subprocess) + App Store (iTunes RSS)
  signals/           Fast Climber / New Entrant / Sustained / Cross-platform / Compose / Enrich
  store/             SQLite schema + access layer
  report/            Jinja templates, HTML renderer, Slack poster
  jobs/              Daily and weekly orchestrators
tests/               48+ offline tests (mocked + VCR cassettes)
```
