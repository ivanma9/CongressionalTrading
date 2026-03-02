"""Chart API endpoints for the Congressional Trading dashboard."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Query

from congressional_trading.db.database import get_connection
from congressional_trading.db.models import (
    MemberPerformanceResponse,
    RecentTradeItem,
    RecentTradesResponse,
    TickerActivityResponse,
    TickerTradeMarker,
    PricePoint,
    TradePerformanceItem,
    TrendingTickerItem,
    TrendingTickersResponse,
)
from congressional_trading.db.queries import (
    get_member_trades_for_performance,
    get_recent_trades,
    get_ticker_trades,
    get_trending_tickers,
)
from congressional_trading.services.price_service import (
    get_price_after_date,
    get_price_on_date,
    get_prices,
)

logger = logging.getLogger(__name__)

chart_router = APIRouter(prefix="/api/v1")


@chart_router.get("/trades/recent", response_model=RecentTradesResponse)
def recent_trades(
    days: Annotated[int, Query(ge=1, le=3650)] = 30,
    member: Annotated[str | None, Query(min_length=2, max_length=50)] = None,
    ticker: Annotated[str | None, Query(min_length=1, max_length=5, pattern=r"^[A-Za-z]+$")] = None,
    transaction_type: Annotated[str | None, Query(pattern=r"^(purchase|sale|sale_partial|exchange)$")] = None,
) -> RecentTradesResponse:
    conn = get_connection()
    rows = get_recent_trades(conn, days=days, member=member, ticker=ticker, transaction_type=transaction_type)
    trades = [RecentTradeItem(**r) for r in rows]
    return RecentTradesResponse(trades=trades, days=days)


@chart_router.get("/trades/trending", response_model=TrendingTickersResponse)
def trending_tickers(
    days: Annotated[int, Query(ge=1, le=3650)] = 60,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> TrendingTickersResponse:
    conn = get_connection()
    rows = get_trending_tickers(conn, days=days, limit=limit)
    tickers = [TrendingTickerItem(**r) for r in rows]
    return TrendingTickersResponse(tickers=tickers, days=days, limit=limit)


@chart_router.get("/members/{member}/performance", response_model=MemberPerformanceResponse)
def member_performance(
    member: str,
) -> MemberPerformanceResponse:
    conn = get_connection()
    rows = get_member_trades_for_performance(conn, member=member)

    if not rows:
        return MemberPerformanceResponse(
            member_name=member,
            trades=[],
            total_trades=0,
            win_rate_30d=None,
            avg_return_30d=None,
            avg_spy_return_30d=None,
        )

    member_name = rows[0]["member_name"]
    enriched = []
    wins_30d = 0
    returns_30d = []
    spy_returns_30d = []

    for r in rows:
        ticker = r["ticker"]
        date = r["transaction_date"]

        price_at_trade = get_price_on_date(conn, ticker, date)
        ret_30 = ret_60 = ret_90 = None
        spy_30 = spy_60 = spy_90 = None

        if price_at_trade and price_at_trade > 0:
            for days_offset, label in [(30, "30"), (60, "60"), (90, "90")]:
                future_price = get_price_after_date(conn, ticker, date, days_offset)
                spy_at_trade = get_price_on_date(conn, "SPY", date)
                spy_future = get_price_after_date(conn, "SPY", date, days_offset)

                if future_price:
                    ret = round((future_price - price_at_trade) / price_at_trade * 100, 2)
                    if r["transaction_type"] in ("sale", "sale_partial"):
                        ret = -ret
                    if label == "30":
                        ret_30 = ret
                    elif label == "60":
                        ret_60 = ret
                    else:
                        ret_90 = ret

                if spy_at_trade and spy_at_trade > 0 and spy_future:
                    spy_ret = round((spy_future - spy_at_trade) / spy_at_trade * 100, 2)
                    if label == "30":
                        spy_30 = spy_ret
                    elif label == "60":
                        spy_60 = spy_ret
                    else:
                        spy_90 = spy_ret

        if ret_30 is not None and ret_30 > 0:
            wins_30d += 1
        if ret_30 is not None:
            returns_30d.append(ret_30)
        if spy_30 is not None:
            spy_returns_30d.append(spy_30)

        enriched.append(TradePerformanceItem(
            id=r["id"],
            ticker=ticker,
            transaction_type=r["transaction_type"],
            transaction_date=date,
            amount_range_low=r["amount_range_low"],
            amount_range_high=r["amount_range_high"],
            price_at_trade=price_at_trade,
            return_30d=ret_30,
            return_60d=ret_60,
            return_90d=ret_90,
            spy_return_30d=spy_30,
            spy_return_60d=spy_60,
            spy_return_90d=spy_90,
        ))

    win_rate = round(wins_30d / len(returns_30d) * 100, 1) if returns_30d else None
    avg_ret = round(sum(returns_30d) / len(returns_30d), 2) if returns_30d else None
    avg_spy = round(sum(spy_returns_30d) / len(spy_returns_30d), 2) if spy_returns_30d else None

    return MemberPerformanceResponse(
        member_name=member_name,
        trades=enriched,
        total_trades=len(enriched),
        win_rate_30d=win_rate,
        avg_return_30d=avg_ret,
        avg_spy_return_30d=avg_spy,
    )


@chart_router.get("/tickers/{ticker}/activity", response_model=TickerActivityResponse)
def ticker_activity(
    ticker: str,
) -> TickerActivityResponse:
    conn = get_connection()
    trade_rows = get_ticker_trades(conn, ticker=ticker)

    if not trade_rows:
        return TickerActivityResponse(ticker=ticker.upper(), prices=[], spy_prices=[], trades=[])

    dates = [r["transaction_date"] for r in trade_rows if r["transaction_date"]]
    if not dates:
        return TickerActivityResponse(ticker=ticker.upper(), prices=[], spy_prices=[], trades=[])

    min_date = min(dates)
    max_date = max(dates)

    from datetime import datetime, timedelta
    start = (datetime.strptime(min_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
    end = (datetime.strptime(max_date, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")
    if end > today:
        end = today

    prices_raw = get_prices(conn, ticker, start, end)
    spy_raw = get_prices(conn, "SPY", start, end)

    prices = [PricePoint(date=p["date"], close=p["close"]) for p in prices_raw]
    spy_prices = [PricePoint(date=p["date"], close=p["close"]) for p in spy_raw]

    trades = [
        TickerTradeMarker(
            date=r["transaction_date"],
            member_name=r["member_name"],
            transaction_type=r["transaction_type"],
            amount_range_low=r["amount_range_low"],
            amount_range_high=r["amount_range_high"],
        )
        for r in trade_rows
    ]

    return TickerActivityResponse(
        ticker=ticker.upper(),
        prices=prices,
        spy_prices=spy_prices,
        trades=trades,
    )
