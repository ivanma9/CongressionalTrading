# Congressional Trading Datastore

Scrapes, parses, and serves U.S. House financial disclosure (PTR) filings as a REST API with an interactive dashboard.

## Quick Start (Local)

```bash
# Prerequisites: Python 3.12+, uv, pdftotext (poppler)
brew install poppler  # macOS

# Install dependencies
uv sync

# Run the server
DATABASE_PATH=data/congressional_trades.db uv run uvicorn congressional_trading.main:app --reload --port 8080
```

- **Dashboard**: http://localhost:8080/dashboard
- **API docs**: http://localhost:8080/docs
- **Health check**: http://localhost:8080/api/v1/health

On first startup the scraper runs automatically if no recent scrape exists, pulling filings from 2020 to present.

## Production (Railway)

Deployed at: `https://congressional-trading-datastore-production-9fd6.up.railway.app`

```bash
# Prerequisites: Railway CLI, logged in
brew install railwayapp/tap/railway
railway login

# Link to the existing project
railway link --project glorious-mindfulness
railway service congressional-trading-datastore

# Deploy
railway up --detach

# Check logs
railway logs
```

The production service uses a persistent Railway volume mounted at `/data` for the SQLite database. No environment variable changes needed — the Dockerfile defaults are correct for Railway.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_PATH` | `/data/congressional_trades.db` | SQLite DB path. Set to `data/congressional_trades.db` for local dev. |
| `LOG_LEVEL` | `INFO` | Logging level |
| `SCRAPE_HOUR_UTC` | `6` | Hour (UTC) for the daily scrape cron job |
| `SCRAPE_START_YEAR` | `2020` | Earliest year to scrape filings from |

## API Endpoints

All endpoints are prefixed with `/api/v1`. Rate limited to 10 req/sec.

### Core

| Method | Path | Description |
|---|---|---|
| GET | `/trades` | List trades. Requires `ticker` or `member`. Params: `days`, `transaction_type`, `limit`, `offset` |
| GET | `/trades/summary` | Aggregate stats for a ticker. Params: `ticker` (required), `days` |
| GET | `/members` | Members with recent trading activity. Params: `days`, `limit`, `offset` |
| GET | `/health` | DB stats, last scrape time. Returns 503 if stale (>48h) |

### Charts / Dashboard

| Method | Path | Description |
|---|---|---|
| GET | `/trades/recent` | Recent trades for charting. Params: `days`, `member`, `ticker`, `transaction_type` |
| GET | `/trades/trending` | Most-traded tickers with buy/sell breakdown. Params: `days`, `limit` |
| GET | `/members/{member}/performance` | Member returns (30/60/90d) vs SPY with win rate |
| GET | `/tickers/{ticker}/activity` | Ticker price history with congressional trade markers |

### Dashboard UI

| Path | Description |
|---|---|
| `/dashboard` | Interactive HTML dashboard with charts (Plotly.js) |

## Database Schema

SQLite with WAL mode. Four tables:

- **filings** — One row per House PTR filing. Tracks member info, filing date/year, processing status, retry count.
- **trades** — Individual transactions parsed from filings. Ticker, asset description, transaction type/date, amount range, owner.
- **scraper_runs** — Audit log of scrape cycles with counts and timing.
- **price_cache** — Cached stock closing prices from yfinance (ticker + date).

## How the Scraper Works

1. Downloads annual ZIP index files from `disclosures-clerk.house.gov`
2. Parses the XML index to find PTR (Periodic Transaction Report) filings
3. Downloads each PDF, extracts text with `pdftotext -layout`
4. Parses columnar text into structured trade records
5. Validates dates (rejects impossible years from PDF misalignment) and amounts

Runs daily at `SCRAPE_HOUR_UTC` via APScheduler. Includes rate limiting (1s between requests), circuit breaker (pauses after 5 consecutive failures), and retry logic (up to 3 attempts per filing).

## Running Tests

```bash
uv pip install -e ".[dev]"
uv run pytest tests/unit/test_parser.py -v
```

## Project Structure

```
src/congressional_trading/
├── main.py              # FastAPI app, lifespan, static files
├── config.py            # Environment variables and constants
├── api/
│   ├── routes.py        # Core API endpoints
│   └── chart_routes.py  # Dashboard/chart endpoints
├── db/
│   ├── database.py      # SQLite connection, schema, pragmas
│   ├── queries.py       # All SQL queries
│   └── models.py        # Pydantic response models
├── parser/
│   ├── ptr_parser.py    # PDF text → structured trades
│   ├── patterns.py      # Regex constants
│   └── xml_index.py     # XML index parser
├── scraper/
│   ├── downloader.py    # PDF download + text extraction
│   └── scheduler.py     # APScheduler cron setup
└── services/
    └── price_service.py # yfinance price fetching + caching
```
