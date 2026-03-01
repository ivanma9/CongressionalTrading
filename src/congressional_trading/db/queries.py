"""Data access layer — raw SQL queries against SQLite."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone


def get_trades(
    conn: sqlite3.Connection,
    *,
    ticker: str | None = None,
    member: str | None = None,
    days: int = 90,
    transaction_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Query trades with filters. Returns (rows, total_count)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    conditions = ["t.transaction_date >= ?"]
    params: list = [cutoff]

    if ticker:
        conditions.append("UPPER(t.ticker) = UPPER(?)")
        params.append(ticker)
    if member:
        conditions.append("UPPER(f.member_last) LIKE UPPER(?)")
        params.append(f"%{member}%")
    if transaction_type:
        conditions.append("t.transaction_type = ?")
        params.append(transaction_type)

    where = " AND ".join(conditions)

    count_sql = f"""
        SELECT COUNT(*) FROM trades t
        JOIN filings f ON t.filing_doc_id = f.doc_id
        WHERE {where}
    """
    total = conn.execute(count_sql, params).fetchone()[0]

    query_sql = f"""
        SELECT
            t.id,
            f.member_first || ' ' || f.member_last AS member_name,
            SUBSTR(f.state_district, 1, 2) AS member_state,
            SUBSTR(f.state_district, 3) AS member_district,
            t.ticker,
            t.asset_description,
            t.asset_type,
            t.transaction_type,
            t.transaction_date,
            t.notification_date AS disclosure_date,
            t.amount_range_low,
            t.amount_range_high,
            t.owner,
            t.description,
            t.cap_gains_over_200,
            t.filing_doc_id AS filing_id
        FROM trades t
        JOIN filings f ON t.filing_doc_id = f.doc_id
        WHERE {where}
        ORDER BY t.transaction_date DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    rows = conn.execute(query_sql, params).fetchall()
    return [dict(r) for r in rows], total


def get_trades_summary(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    days: int = 90,
) -> dict:
    """Get aggregate trading summary for a ticker."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    sql = """
        SELECT
            COUNT(*) AS total_trades,
            SUM(CASE WHEN t.transaction_type = 'purchase' THEN 1 ELSE 0 END) AS purchases,
            SUM(CASE WHEN t.transaction_type IN ('sale', 'sale_partial') THEN 1 ELSE 0 END) AS sales,
            COUNT(DISTINCT f.member_last) AS unique_members,
            MAX(t.transaction_date) AS latest_trade_date
        FROM trades t
        JOIN filings f ON t.filing_doc_id = f.doc_id
        WHERE UPPER(t.ticker) = UPPER(?)
          AND t.transaction_date >= ?
    """
    row = conn.execute(sql, [ticker, cutoff]).fetchone()

    members_sql = """
        SELECT DISTINCT f.member_last
        FROM trades t
        JOIN filings f ON t.filing_doc_id = f.doc_id
        WHERE UPPER(t.ticker) = UPPER(?)
          AND t.transaction_date >= ?
        ORDER BY f.member_last
    """
    members = [r[0] for r in conn.execute(members_sql, [ticker, cutoff]).fetchall()]

    purchases = row["purchases"] or 0
    sales = row["sales"] or 0
    if purchases > sales:
        sentiment = "bullish"
    elif sales > purchases:
        sentiment = "bearish"
    else:
        sentiment = "neutral"

    return {
        "ticker": ticker.upper(),
        "period_days": days,
        "total_trades": row["total_trades"] or 0,
        "purchases": purchases,
        "sales": sales,
        "unique_members": row["unique_members"] or 0,
        "members": members,
        "net_sentiment": sentiment,
        "latest_trade_date": row["latest_trade_date"],
    }


def get_members(
    conn: sqlite3.Connection,
    *,
    days: int = 90,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """List members with recent trading activity."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    count_sql = """
        SELECT COUNT(DISTINCT f.member_last || f.member_first)
        FROM trades t
        JOIN filings f ON t.filing_doc_id = f.doc_id
        WHERE t.transaction_date >= ?
    """
    total = conn.execute(count_sql, [cutoff]).fetchone()[0]

    sql = """
        SELECT
            f.member_first || ' ' || f.member_last AS name,
            SUBSTR(f.state_district, 1, 2) AS state,
            SUBSTR(f.state_district, 3) AS district,
            COUNT(t.id) AS trade_count,
            MAX(t.transaction_date) AS latest_trade_date
        FROM trades t
        JOIN filings f ON t.filing_doc_id = f.doc_id
        WHERE t.transaction_date >= ?
        GROUP BY f.member_last, f.member_first, f.state_district
        ORDER BY trade_count DESC
        LIMIT ? OFFSET ?
    """
    rows = conn.execute(sql, [cutoff, limit, offset]).fetchall()
    return [dict(r) for r in rows], total


def get_health_stats(conn: sqlite3.Connection) -> dict:
    """Get health check stats."""
    total_filings = conn.execute(
        "SELECT COUNT(*) FROM filings WHERE status = 'parsed'"
    ).fetchone()[0]
    total_trades = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]

    last_run = conn.execute(
        "SELECT completed_at FROM scraper_runs WHERE status = 'success' "
        "ORDER BY completed_at DESC LIMIT 1"
    ).fetchone()
    last_scrape = last_run[0] if last_run else None

    return {
        "total_filings": total_filings,
        "total_trades": total_trades,
        "last_scrape": last_scrape,
    }


# --- Write operations for scraper ---

def insert_filing(conn: sqlite3.Connection, filing: dict) -> None:
    """Insert a new filing record."""
    conn.execute(
        """INSERT OR IGNORE INTO filings
           (doc_id, member_first, member_last, member_prefix, member_suffix,
            state_district, filing_date, filing_year, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
        (
            filing["doc_id"],
            filing["first"],
            filing["last"],
            filing.get("prefix"),
            filing.get("suffix"),
            filing["state_district"],
            filing["filing_date"],
            filing["filing_year"],
            _now(),
            _now(),
        ),
    )


def insert_trades(conn: sqlite3.Connection, doc_id: str, trades: list[dict]) -> int:
    """Insert trades for a filing. Returns count of inserted rows."""
    inserted = 0
    for t in trades:
        cur = conn.execute(
            """INSERT OR IGNORE INTO trades
               (filing_doc_id, ticker, asset_description, asset_type,
                transaction_type, transaction_date, notification_date,
                amount_range_low, amount_range_high, owner, description,
                cap_gains_over_200, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                doc_id,
                t.get("ticker"),
                t["asset_description"],
                t.get("asset_type"),
                t["transaction_type"],
                t.get("transaction_date"),
                t.get("notification_date"),
                t.get("amount_range_low"),
                t.get("amount_range_high"),
                t.get("owner", "self"),
                t.get("description"),
                t.get("cap_gains_over_200"),
                _now(),
            ),
        )
        inserted += cur.rowcount
    return inserted


def update_filing_status(
    conn: sqlite3.Connection,
    doc_id: str,
    status: str,
    error_message: str | None = None,
) -> None:
    """Update filing status and optionally increment retry count."""
    if status == "error":
        conn.execute(
            """UPDATE filings SET status = ?, error_message = ?,
               retry_count = retry_count + 1, updated_at = ? WHERE doc_id = ?""",
            (status, error_message, _now(), doc_id),
        )
    else:
        conn.execute(
            """UPDATE filings SET status = ?, error_message = ?, updated_at = ?
               WHERE doc_id = ?""",
            (status, error_message, _now(), doc_id),
        )


def get_pending_filings(conn: sqlite3.Connection) -> list[dict]:
    """Get filings that need processing (pending or retryable errors)."""
    rows = conn.execute(
        """SELECT doc_id, member_first, member_last, filing_year
           FROM filings
           WHERE status = 'pending'
              OR (status IN ('error', 'parse_error') AND retry_count < ?)
           ORDER BY created_at""",
        (3,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_existing_doc_ids(conn: sqlite3.Connection) -> set[str]:
    """Get all doc_ids already in the database."""
    rows = conn.execute("SELECT doc_id FROM filings").fetchall()
    return {r[0] for r in rows}


def insert_scraper_run(conn: sqlite3.Connection, status: str = "running") -> int:
    """Insert a new scraper run and return its id."""
    cur = conn.execute(
        "INSERT INTO scraper_runs (started_at, status) VALUES (?, ?)",
        (_now(), status),
    )
    conn.commit()
    return cur.lastrowid


def update_scraper_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    status: str,
    new_filings: int = 0,
    new_trades: int = 0,
    retried_filings: int = 0,
    error_message: str | None = None,
) -> None:
    """Update a scraper run record."""
    conn.execute(
        """UPDATE scraper_runs
           SET completed_at = ?, status = ?, new_filings = ?,
               new_trades = ?, retried_filings = ?, error_message = ?
           WHERE id = ?""",
        (_now(), status, new_filings, new_trades, retried_filings, error_message, run_id),
    )
    conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
