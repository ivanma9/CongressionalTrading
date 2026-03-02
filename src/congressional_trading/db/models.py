"""Pydantic response models for the API."""

from __future__ import annotations

from pydantic import BaseModel


class TradeResponse(BaseModel):
    id: int
    member_name: str
    member_state: str
    member_district: str
    ticker: str | None
    asset_description: str
    asset_type: str | None
    transaction_type: str
    transaction_date: str | None
    disclosure_date: str | None
    amount_range_low: int | None
    amount_range_high: int | None
    owner: str
    description: str | None
    cap_gains_over_200: bool | None
    filing_id: str
    filing_url: str


class TradesListResponse(BaseModel):
    trades: list[TradeResponse]
    total: int
    limit: int
    offset: int


class TradeSummaryResponse(BaseModel):
    ticker: str
    period_days: int
    total_trades: int
    purchases: int
    sales: int
    unique_members: int
    members: list[str]
    net_sentiment: str
    latest_trade_date: str | None


class MemberResponse(BaseModel):
    name: str
    state: str
    district: str
    trade_count: int
    latest_trade_date: str | None


class MembersListResponse(BaseModel):
    members: list[MemberResponse]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    status: str
    last_scrape: str | None = None
    total_filings: int
    total_trades: int
    database_size_mb: float
    error: str | None = None


# --- Chart response models ---


class RecentTradeItem(BaseModel):
    id: int
    member_name: str
    ticker: str | None
    transaction_type: str
    transaction_date: str | None
    amount_range_low: int | None
    amount_range_high: int | None
    owner: str


class RecentTradesResponse(BaseModel):
    trades: list[RecentTradeItem]
    days: int


class TrendingTickerItem(BaseModel):
    ticker: str
    total_trades: int
    buys: int
    sells: int
    members: str


class TrendingTickersResponse(BaseModel):
    tickers: list[TrendingTickerItem]
    days: int
    limit: int


class TradePerformanceItem(BaseModel):
    id: int
    ticker: str
    transaction_type: str
    transaction_date: str
    amount_range_low: int | None
    amount_range_high: int | None
    price_at_trade: float | None
    return_30d: float | None
    return_60d: float | None
    return_90d: float | None
    spy_return_30d: float | None
    spy_return_60d: float | None
    spy_return_90d: float | None


class MemberPerformanceResponse(BaseModel):
    member_name: str
    trades: list[TradePerformanceItem]
    total_trades: int
    win_rate_30d: float | None
    avg_return_30d: float | None
    avg_spy_return_30d: float | None


class PricePoint(BaseModel):
    date: str
    close: float


class TickerTradeMarker(BaseModel):
    date: str
    member_name: str
    transaction_type: str
    amount_range_low: int | None
    amount_range_high: int | None


class TickerActivityResponse(BaseModel):
    ticker: str
    prices: list[PricePoint]
    spy_prices: list[PricePoint]
    trades: list[TickerTradeMarker]
