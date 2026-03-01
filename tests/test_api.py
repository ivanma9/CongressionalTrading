"""Tests for the FastAPI API endpoints."""

import sqlite3
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from congressional_trading.api.routes import router
from congressional_trading.db.database import get_connection, reset_connection


@pytest.fixture(autouse=True)
def test_db(tmp_path):
    """Create a fresh test database for each test."""
    reset_connection()
    db_path = tmp_path / "test.db"

    with patch("congressional_trading.db.database.DATABASE_PATH", db_path), \
         patch("congressional_trading.config.DATABASE_PATH", db_path):
        conn = get_connection(db_path)
        _seed_test_data(conn)
        yield conn

    reset_connection()


@pytest.fixture
def client(test_db):
    """Create a test client without lifespan (no scheduler)."""
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c


def _seed_test_data(conn: sqlite3.Connection):
    """Insert test filings and trades with recent dates."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    # Use dates within the last 30 days to pass default 90-day filter
    trade_date_1 = (now - timedelta(days=10)).strftime("%Y-%m-%d")
    trade_date_2 = (now - timedelta(days=8)).strftime("%Y-%m-%d")
    trade_date_3 = (now - timedelta(days=5)).strftime("%Y-%m-%d")
    filing_date_1 = (now - timedelta(days=3)).strftime("%Y-%m-%d")
    filing_date_2 = (now - timedelta(days=2)).strftime("%Y-%m-%d")

    conn.execute(
        """INSERT INTO filings (doc_id, member_first, member_last, member_prefix,
           member_suffix, state_district, filing_date, filing_year, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("20026590", "Nancy", "Pelosi", "Hon.", None, "CA11", filing_date_1, now.year, "parsed", now_iso, now_iso),
    )
    conn.execute(
        """INSERT INTO filings (doc_id, member_first, member_last, member_prefix,
           member_suffix, state_district, filing_date, filing_year, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("20026591", "Dan", "Crenshaw", "Hon.", None, "TX02", filing_date_2, now.year, "parsed", now_iso, now_iso),
    )

    # Pelosi trades
    conn.execute(
        """INSERT INTO trades (filing_doc_id, ticker, asset_description, asset_type,
           transaction_type, transaction_date, notification_date, amount_range_low,
           amount_range_high, owner, cap_gains_over_200, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("20026590", "NVDA", "NVIDIA Corporation", "ST", "purchase", trade_date_1,
         filing_date_1, 1000001, 5000000, "spouse", True, now_iso),
    )
    conn.execute(
        """INSERT INTO trades (filing_doc_id, ticker, asset_description, asset_type,
           transaction_type, transaction_date, notification_date, amount_range_low,
           amount_range_high, owner, cap_gains_over_200, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("20026590", "AAPL", "Apple Inc.", "ST", "sale", trade_date_2,
         filing_date_1, 250001, 500000, "self", False, now_iso),
    )

    # Crenshaw trade
    conn.execute(
        """INSERT INTO trades (filing_doc_id, ticker, asset_description, asset_type,
           transaction_type, transaction_date, notification_date, amount_range_low,
           amount_range_high, owner, cap_gains_over_200, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("20026591", "NVDA", "NVIDIA Corporation", "ST", "sale", trade_date_3,
         filing_date_2, 50001, 100000, "self", None, now_iso),
    )

    # Insert a scraper run
    conn.execute(
        "INSERT INTO scraper_runs (started_at, completed_at, status, new_filings, new_trades) VALUES (?, ?, ?, ?, ?)",
        (now_iso, now_iso, "success", 2, 3),
    )

    conn.commit()


class TestTradesEndpoint:
    def test_trades_by_ticker(self, client):
        resp = client.get("/api/v1/trades?ticker=NVDA")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert all(t["ticker"] == "NVDA" for t in data["trades"])

    def test_trades_by_member(self, client):
        resp = client.get("/api/v1/trades?member=Pelosi")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert all("Pelosi" in t["member_name"] for t in data["trades"])

    def test_trades_requires_filter(self, client):
        resp = client.get("/api/v1/trades")
        assert resp.status_code == 400

    def test_trades_pagination(self, client):
        resp = client.get("/api/v1/trades?ticker=NVDA&limit=1&offset=0")
        data = resp.json()
        assert len(data["trades"]) == 1
        assert data["total"] == 2

    def test_trades_by_transaction_type(self, client):
        resp = client.get("/api/v1/trades?ticker=NVDA&transaction_type=purchase")
        data = resp.json()
        assert data["total"] == 1
        assert data["trades"][0]["transaction_type"] == "purchase"

    def test_trades_invalid_ticker(self, client):
        resp = client.get("/api/v1/trades?ticker=TOOLONG")
        assert resp.status_code == 422


class TestTradeSummaryEndpoint:
    def test_summary(self, client):
        resp = client.get("/api/v1/trades/summary?ticker=NVDA")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "NVDA"
        assert data["total_trades"] == 2
        assert data["purchases"] == 1
        assert data["sales"] == 1
        assert data["unique_members"] == 2
        assert data["net_sentiment"] == "neutral"

    def test_summary_requires_ticker(self, client):
        resp = client.get("/api/v1/trades/summary")
        assert resp.status_code == 422


class TestMembersEndpoint:
    def test_members_list(self, client):
        resp = client.get("/api/v1/members")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        names = [m["name"] for m in data["members"]]
        assert any("Pelosi" in n for n in names)

    def test_members_pagination(self, client):
        resp = client.get("/api/v1/members?limit=1")
        data = resp.json()
        assert len(data["members"]) == 1


class TestHealthEndpoint:
    def test_health_ok(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["total_trades"] == 3
