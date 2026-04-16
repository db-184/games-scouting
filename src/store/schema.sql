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
