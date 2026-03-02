"""Stock price service with SQLite caching and yfinance backend."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta, timezone

import yfinance as yf

logger = logging.getLogger(__name__)


def get_prices(
    conn: sqlite3.Connection,
    ticker: str,
    start_date: str,
    end_date: str | None = None,
) -> list[dict]:
    """Get daily closing prices for a ticker, using cache when available."""
    end = end_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cached = _get_cached_prices(conn, ticker, start_date, end)

    if cached:
        cached_dates = {r["date"] for r in cached}
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
        all_business_days = set()
        d = start_dt
        while d <= end_dt:
            if d.weekday() < 5:
                all_business_days.add(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)

        missing = all_business_days - cached_dates
        if len(missing) < len(all_business_days) * 0.1:
            return cached

    _fetch_and_cache(conn, ticker, start_date, end)
    return _get_cached_prices(conn, ticker, start_date, end)


def get_price_on_date(
    conn: sqlite3.Connection,
    ticker: str,
    date: str,
) -> float | None:
    """Get closing price on or nearest before a date (within 5 business days)."""
    row = conn.execute(
        "SELECT close FROM price_cache WHERE ticker = ? AND date = ?",
        (ticker.upper(), date),
    ).fetchone()
    if row:
        return row["close"]

    start = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=10)).strftime("%Y-%m-%d")
    _fetch_and_cache(conn, ticker, start, date)

    row = conn.execute(
        "SELECT close FROM price_cache WHERE ticker = ? AND date <= ? ORDER BY date DESC LIMIT 1",
        (ticker.upper(), date),
    ).fetchone()
    return row["close"] if row else None


def get_price_after_date(
    conn: sqlite3.Connection,
    ticker: str,
    date: str,
    days_after: int,
) -> float | None:
    """Get closing price approximately days_after trading days from date."""
    target = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=days_after)).strftime("%Y-%m-%d")
    end = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=days_after + 10)).strftime("%Y-%m-%d")

    row = conn.execute(
        "SELECT close FROM price_cache WHERE ticker = ? AND date >= ? AND date <= ? ORDER BY date ASC LIMIT 1",
        (ticker.upper(), target, end),
    ).fetchone()
    if row:
        return row["close"]

    start = date
    _fetch_and_cache(conn, ticker, start, end)

    row = conn.execute(
        "SELECT close FROM price_cache WHERE ticker = ? AND date >= ? AND date <= ? ORDER BY date ASC LIMIT 1",
        (ticker.upper(), target, end),
    ).fetchone()
    return row["close"] if row else None


def _get_cached_prices(
    conn: sqlite3.Connection,
    ticker: str,
    start: str,
    end: str,
) -> list[dict]:
    rows = conn.execute(
        "SELECT date, close FROM price_cache WHERE ticker = ? AND date >= ? AND date <= ? ORDER BY date",
        (ticker.upper(), start, end),
    ).fetchall()
    return [dict(r) for r in rows]


def _fetch_and_cache(
    conn: sqlite3.Connection,
    ticker: str,
    start: str,
    end: str,
) -> None:
    try:
        tk = yf.Ticker(ticker)
        end_plus = (datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        df = tk.history(start=start, end=end_plus, auto_adjust=True)
        if df.empty:
            logger.warning("No price data for %s from %s to %s", ticker, start, end)
            return

        rows = []
        for idx, row in df.iterrows():
            d = idx.strftime("%Y-%m-%d")
            rows.append((ticker.upper(), d, round(float(row["Close"]), 4)))

        conn.executemany(
            "INSERT OR REPLACE INTO price_cache (ticker, date, close) VALUES (?, ?, ?)",
            rows,
        )
        conn.commit()
        logger.info("Cached %d prices for %s", len(rows), ticker)
    except Exception:
        logger.exception("Failed to fetch prices for %s", ticker)
