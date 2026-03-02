# Architecture

## Overview

Congressional Trading Datastore is a monolithic FastAPI application that scrapes, parses, and serves U.S. House financial disclosure data. It runs as a single container on Railway with a SQLite database on a persistent volume.

## System Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Railway (1 replica)                   │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │              FastAPI Application                   │  │
│  │                                                    │  │
│  │  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │  │
│  │  │ REST API │  │Dashboard │  │  APScheduler   │  │  │
│  │  │ /api/v1  │  │    UI    │  │  (daily cron)  │  │  │
│  │  └────┬─────┘  └──────────┘  └───────┬────────┘  │  │
│  │       │                               │           │  │
│  │  ┌────┴───────────────────────────────┴────────┐  │  │
│  │  │              Query Layer                     │  │  │
│  │  │         (db/queries.py)                      │  │  │
│  │  └────────────────┬────────────────────────────┘  │  │
│  │                   │                                │  │
│  └───────────────────┼────────────────────────────────┘  │
│                      │                                    │
│  ┌───────────────────┴────────────────────────────────┐  │
│  │           SQLite (WAL mode)                         │  │
│  │           /data/congressional_trades.db              │  │
│  │           Persistent Volume (5 GB)                  │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
          │                              │
          │ HTTP (users)                 │ HTTPS (scraper)
          ▼                              ▼
    Web Browsers              disclosures-clerk.house.gov
                              (ZIP indexes + PTR PDFs)
                                         │
                                         ▼
                                   yfinance API
                              (stock price lookups)
```

## Components

### API Layer (`api/`)

Two routers mounted on a single FastAPI app:

- **routes.py** — Core CRUD: `/trades`, `/trades/summary`, `/members`, `/health`
- **chart_routes.py** — Dashboard endpoints: `/trades/recent`, `/trades/trending`, `/members/{member}/performance`, `/tickers/{ticker}/activity`

Rate limited at 10 req/sec via slowapi (in-memory, single process).

### Parser (`parser/`)

Converts raw PDF text (from `pdftotext -layout`) into structured trade records:

1. `xml_index.py` — Parses annual XML index files to discover PTR filings
2. `ptr_parser.py` — Extracts trades from column-aligned PDF text
3. `patterns.py` — Regex constants for tickers, dates, amounts, etc.

Key validations: date range (rejects years <2008 or >current+1), date ordering, amount bracket matching.

### Scraper (`scraper/`)

- **scheduler.py** — APScheduler cron job, runs daily at `SCRAPE_HOUR_UTC`. File-lock prevents concurrent runs. Runs on startup if no scrape in last 24h.
- **downloader.py** — Downloads ZIP indexes and individual PDFs. Exponential backoff (1s→2s→4s), circuit breaker (pauses after 5 failures), rate limiting (1s between requests). Backs up DB before each cycle.

### Database (`db/`)

SQLite with WAL journal mode, 64MB cache, 5s busy timeout.

| Table | Purpose | Rows (current) |
|---|---|---|
| filings | One row per PTR filing | ~2,000 |
| trades | Individual transactions | ~24,000 |
| scraper_runs | Audit log of scrape cycles | ~50 |
| price_cache | Cached yfinance closing prices | grows on demand |

### Services (`services/`)

- **price_service.py** — Fetches historical stock prices via yfinance, caches in `price_cache` table. Used by performance and ticker activity endpoints.

### Frontend (`static/`)

Single-page `dashboard.html` using Plotly.js for charts. No build step — vanilla HTML/JS served as a static file.

## Data Flow

### Scrape Cycle

```
disclosures-clerk.house.gov
        │
        ▼
  ZIP download (per year, 2020–present)
        │
        ▼
  XML index parse → filter PTRs → insert new filings
        │
        ▼
  For each pending filing:
    PDF download → pdftotext -layout → ptr_parser → trades
        │
        ▼
  Insert trades into SQLite
```

### Request Flow

```
User request → FastAPI → slowapi rate check → route handler → queries.py → SQLite → JSON response
```

## Design Decisions

| Decision | Rationale |
|---|---|
| SQLite over Postgres | Single-writer workload (scraper), low query volume, zero ops overhead, fits in Railway volume |
| Monolith over microservices | One team, one data source, <25K rows — no need to split |
| In-process scheduler over external cron | Simpler deployment, no extra Railway service needed |
| pdftotext over Python PDF libs | Most reliable extraction of column-aligned government PDFs |
| yfinance over paid APIs | Free, sufficient for daily closing prices, cached to avoid repeated calls |
| In-memory rate limiting over Redis | Single process, single replica — no shared state needed |

## Scaling Considerations

The current architecture handles the workload comfortably. If scaling is needed:

- **Multiple workers** → Switch rate limiter to Redis (already in the Railway project)
- **Larger dataset** → SQLite handles millions of rows fine with proper indexes (already in place)
- **Faster scraping** → Currently rate-limited to 1 req/s to be polite to House servers; not a bottleneck
- **High read traffic** → Add CDN/caching layer in front of Railway
