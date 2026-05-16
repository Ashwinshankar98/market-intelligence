import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "intelligence.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_connection()
    conn.executescript("""

    CREATE TABLE IF NOT EXISTS events (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        source        TEXT NOT NULL,
        event_type    TEXT NOT NULL,
        headline      TEXT NOT NULL,
        summary       TEXT,
        url           TEXT,
        tickers       TEXT,
        raw_keywords  TEXT,
        published_at  TEXT,
        scanned_at    TEXT NOT NULL DEFAULT (datetime('now')),
        passed_tier1  INTEGER DEFAULT 0,
        quick_score   REAL,
        passed_tier2  INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS signals (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id        INTEGER REFERENCES events(id),
        score           REAL NOT NULL,
        event_category  TEXT,
        primary_ticker  TEXT,
        sector          TEXT,
        headline        TEXT NOT NULL,
        headline_hash   TEXT,
        reasoning_chain TEXT,
        options_plays   TEXT,
        act_by_hours    INTEGER,
        catalyst_date   TEXT,
        iv_environment  TEXT,
        risk_level      TEXT,
        ripple_tickers  TEXT,
        telegram_sent   INTEGER DEFAULT 0,
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS sector_activity (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        sector      TEXT NOT NULL,
        signal_count INTEGER DEFAULT 0,
        avg_score   REAL,
        week_start  TEXT NOT NULL,
        updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS weekly_synthesis (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        week_start      TEXT NOT NULL,
        top_sectors     TEXT,
        keyword_weights TEXT,
        insights        TEXT,
        signals_reviewed INTEGER,
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- URL dedup — prevents same article being fetched twice
    CREATE TABLE IF NOT EXISTS processed_urls (
        url         TEXT PRIMARY KEY,
        processed_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- Headline dedup — prevents same story from different sources being re-analysed
    CREATE TABLE IF NOT EXISTS processed_headlines (
        headline_hash TEXT PRIMARY KEY,
        processed_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    """)
    conn.commit()
    conn.close()
    print(f"[DB] Intelligence DB initialised at {DB_PATH}")

if __name__ == "__main__":
    init_db()