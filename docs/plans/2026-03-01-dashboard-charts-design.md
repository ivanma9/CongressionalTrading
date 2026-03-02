# Congressional Trading Dashboard — Chart Design

**Date:** 2026-03-01
**Status:** Approved
**Purpose:** Public transparency tool + personal data exploration

## Goals

1. **What are they buying/selling right now?** — Recent activity with adjustable time window
2. **Are they beating the market?** — Per-member and per-ticker performance vs S&P 500

## Data Source

- **Trade data:** SQLite DB at `congressional_trading.db`, scraped from `disclosures-clerk.house.gov`
  - 8,158 trades across 601 filings (2015–2026)
  - Fields: ticker, member, transaction_type, transaction_date, amount_range_low/high, owner
- **Price data:** Yahoo Finance via `yfinance` library (free, no API key)
  - Daily close prices, fetched on-demand and cached locally
  - S&P 500 tracked as `SPY`

## API Endpoints

### Existing
- `GET /api/trades` — Base trade query (already exists)

### New Chart Endpoints (`api/chart_routes.py`)

| Endpoint | Description |
|---|---|
| `GET /api/trades/recent?days=30` | Recent trades with optional filters (member, ticker, type) |
| `GET /api/trades/trending?days=30&limit=20` | Top tickers by trade count in window, with buy/sell breakdown |
| `GET /api/members/{member}/performance` | All trades for a member with post-trade price change and S&P comparison |
| `GET /api/tickers/{ticker}/activity` | Price history for a ticker with congressional trade markers and S&P comparison |

### Query Parameters (shared)
- `days` — Rolling window size (default: 30)
- `limit` — Max results for ranked lists (default: 20)
- `type` — Filter by transaction type: `purchase`, `sale`, `sale_partial`, `exchange`
- `member` — Filter by member name (partial match)
- `ticker` — Filter by ticker symbol

## Price Cache

New SQLite table in the same database:

```sql
CREATE TABLE IF NOT EXISTS price_cache (
    ticker TEXT NOT NULL,
    date TEXT NOT NULL,
    close REAL NOT NULL,
    PRIMARY KEY (ticker, date)
);
```

- Check cache first on every request; fetch from yfinance only for missing dates
- S&P 500 cached as ticker `SPY`
- yfinance bulk fetch: grab full history per ticker in one call, cache all returned dates
- Prices older than 1 trading day are considered final; today's price refreshed if market has closed since last fetch

## Frontend

Single-page HTML app served by FastAPI at `/dashboard`.
No build step — HTML + Plotly.js via CDN + minimal CSS.

### Tab 1: Recent Activity

- Rolling window dropdown at top: 30 / 60 / 90 / custom days
- Sortable, searchable table: date, member, ticker, buy/sell, amount range
- Below table: two horizontal bar charts side by side
  - "Most Bought" tickers in window
  - "Most Sold" tickers in window

### Tab 2: Trending Tickers

- Same window selector as Tab 1
- Stacked bar chart: top 20 tickers by trade count
  - Green = buy, Red = sell
- Hover tooltip shows member breakdown per ticker

### Tab 3: Member Performance

- Member dropdown selector (searchable)
- Timeline scatter plot:
  - X-axis: trade date
  - Y-axis: % return after N days (toggle 30/60/90)
  - Each dot = one trade
- Horizontal benchmark line: S&P 500 average return over same periods
- Summary stats panel: win rate, avg return vs S&P, total trades

### Tab 4: Ticker Deep Dive

- Ticker search/dropdown
- Line chart of price history with:
  - Green up-arrow markers at congressional buy dates
  - Red down-arrow markers at congressional sell dates
- S&P 500 performance line overlaid (normalized to same start)
- Side panel: list of members who traded this ticker and when

## Tech Stack

| Component | Technology |
|---|---|
| Backend | FastAPI (existing) |
| New routes | `api/chart_routes.py` |
| Price service | `services/price_service.py` using `yfinance` |
| Frontend | Single HTML file at `static/dashboard.html` |
| Charts | Plotly.js via CDN |
| Styling | Minimal custom CSS |
| Database | SQLite (existing) |

## File Structure (new files)

```
src/congressional_trading/
  api/
    chart_routes.py          # New chart-specific endpoints
  services/
    price_service.py         # yfinance fetching + cache management
static/
  dashboard.html             # Single-page dashboard app
```

## Implementation Notes

- No build step required — pure HTML/JS/CSS served as static files
- Plotly.js handles interactivity (hover, zoom, pan, filter) out of the box
- Price data is lazy-loaded and cached; first load for a ticker may be slow
- All chart endpoints return JSON; frontend renders via Plotly.js
- yfinance can be swapped for another provider later without changing the API contract
