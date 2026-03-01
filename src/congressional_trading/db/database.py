"""SQLite database connection and schema management."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from congressional_trading.config import DATABASE_PATH

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS filings (
    doc_id          TEXT PRIMARY KEY,
    member_first    TEXT NOT NULL,
    member_last     TEXT NOT NULL,
    member_prefix   TEXT,
    member_suffix   TEXT,
    state_district  TEXT NOT NULL,
    filing_date     TEXT NOT NULL,
    filing_year     INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    error_message   TEXT,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    filing_doc_id       TEXT NOT NULL REFERENCES filings(doc_id),
    ticker              TEXT,
    asset_description   TEXT NOT NULL,
    asset_type          TEXT,
    transaction_type    TEXT NOT NULL,
    transaction_date    TEXT,
    notification_date   TEXT,
    amount_range_low    INTEGER,
    amount_range_high   INTEGER,
    owner               TEXT NOT NULL DEFAULT 'self',
    description         TEXT,
    cap_gains_over_200  BOOLEAN,
    created_at          TEXT NOT NULL,
    UNIQUE(filing_doc_id, ticker, transaction_date, transaction_type, owner)
);

CREATE TABLE IF NOT EXISTS scraper_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL,
    completed_at    TEXT,
    status          TEXT NOT NULL,
    new_filings     INTEGER,
    new_trades      INTEGER,
    retried_filings INTEGER,
    error_message   TEXT
);

CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker);
CREATE INDEX IF NOT EXISTS idx_trades_transaction_date ON trades(transaction_date);
CREATE INDEX IF NOT EXISTS idx_trades_filing_doc_id ON trades(filing_doc_id);
CREATE INDEX IF NOT EXISTS idx_filings_member_last ON filings(member_last);
CREATE INDEX IF NOT EXISTS idx_filings_filing_date ON filings(filing_date);
CREATE INDEX IF NOT EXISTS idx_filings_status ON filings(status);
"""

_connection: sqlite3.Connection | None = None


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get or create the singleton database connection."""
    global _connection
    if _connection is not None:
        return _connection

    path = db_path or DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _configure_pragmas(conn)
    _init_schema(conn)
    _connection = conn
    logger.info("Database initialized at %s", path)
    return conn


def _configure_pragmas(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -64000")
    conn.execute("PRAGMA temp_store = MEMORY")


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def close_connection() -> None:
    """Close the singleton database connection."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


def reset_connection() -> None:
    """Reset the singleton connection (for testing)."""
    global _connection
    _connection = None
