"""FastAPI route handlers for the Congressional Trading API."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Query, Response

from congressional_trading import config
from congressional_trading.db.database import get_connection
from congressional_trading.db.models import (
    HealthResponse,
    MemberResponse,
    MembersListResponse,
    TradeResponse,
    TradesListResponse,
    TradeSummaryResponse,
)
from congressional_trading.db.queries import get_health_stats, get_members, get_trades, get_trades_summary

router = APIRouter(prefix="/api/v1")


@router.get("/trades", response_model=TradesListResponse)
def list_trades(
    ticker: Annotated[str | None, Query(min_length=1, max_length=5, pattern=r"^[A-Za-z]+$")] = None,
    member: Annotated[str | None, Query(min_length=2, max_length=50)] = None,
    days: Annotated[int, Query(ge=1, le=730)] = 90,
    transaction_type: Annotated[str | None, Query(pattern=r"^(purchase|sale|sale_partial|exchange)$")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TradesListResponse:
    if not ticker and not member:
        return Response(
            content='{"error":"At least one of \'ticker\' or \'member\' must be provided","status":400}',
            status_code=400,
            media_type="application/json",
        )

    conn = get_connection()
    rows, total = get_trades(
        conn,
        ticker=ticker,
        member=member,
        days=days,
        transaction_type=transaction_type,
        limit=limit,
        offset=offset,
    )

    trades = []
    for r in rows:
        year = r["filing_year"]
        filing_url = config.PTR_PDF_URL_TEMPLATE.format(year=year, doc_id=r["filing_id"])
        trades.append(TradeResponse(
            filing_url=filing_url,
            **r,
        ))

    return TradesListResponse(trades=trades, total=total, limit=limit, offset=offset)


@router.get("/trades/summary", response_model=TradeSummaryResponse)
def trades_summary(
    ticker: Annotated[str, Query(min_length=1, max_length=5, pattern=r"^[A-Za-z]+$")],
    days: Annotated[int, Query(ge=1, le=730)] = 90,
) -> TradeSummaryResponse:
    conn = get_connection()
    result = get_trades_summary(conn, ticker=ticker, days=days)
    return TradeSummaryResponse(**result)


@router.get("/members", response_model=MembersListResponse)
def list_members(
    days: Annotated[int, Query(ge=1, le=730)] = 90,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MembersListResponse:
    conn = get_connection()
    rows, total = get_members(conn, days=days, limit=limit, offset=offset)
    members = [MemberResponse(**r) for r in rows]
    return MembersListResponse(members=members, total=total, limit=limit, offset=offset)


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse | Response:
    conn = get_connection()
    stats = get_health_stats(conn)

    # Get database file size
    db_path = config.DATABASE_PATH
    try:
        size_mb = round(os.path.getsize(db_path) / (1024 * 1024), 1)
    except OSError:
        size_mb = 0.0

    # Check if last scrape is too old
    last_scrape = stats["last_scrape"]
    if last_scrape:
        from datetime import datetime, timedelta, timezone

        try:
            last_dt = datetime.fromisoformat(last_scrape)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - last_dt > timedelta(hours=48):
                return Response(
                    status_code=503,
                    media_type="application/json",
                    content=HealthResponse(
                        status="unhealthy",
                        last_scrape=last_scrape,
                        total_filings=stats["total_filings"],
                        total_trades=stats["total_trades"],
                        database_size_mb=size_mb,
                        error="Last successful scrape older than 48 hours",
                    ).model_dump_json(),
                )
        except ValueError:
            pass

    return HealthResponse(
        status="ok",
        last_scrape=last_scrape,
        total_filings=stats["total_filings"],
        total_trades=stats["total_trades"],
        database_size_mb=size_mb,
    )
