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
