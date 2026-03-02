# Bounty Submission: Congressional Trading Datastore

## The Customer

**Retail investors using Ghostfolio (an open-source portfolio tracker) who want congressional trading intelligence on the stocks they already hold.**

Ghostfolio helps self-directed investors track their portfolios, but it has zero visibility into what elected officials are doing with the same securities. This matters because members of Congress sit on committees that regulate the industries they invest in — they vote on defense spending while holding Raytheon, set tech policy while trading NVIDIA, and shape healthcare regulation while buying pharmaceutical stocks. The STOCK Act requires disclosure, but the data is locked inside PDFs on a government website that no retail investor realistically checks.

Our customer is the Ghostfolio user who holds a position in NVDA and wants to know: "Did any congress member just buy or sell this stock? Are insiders bullish or bearish? Is there unusual trading activity around upcoming legislation?" Today they can't ask these questions without hours of manual research across government websites. The Congressional Trading Datastore makes this a single API call.

## The Feature(s)

The Congressional Trading Datastore is a **standalone data service** that adds a completely new data source — U.S. House financial disclosures — to the Ghostfolio/AgentForge ecosystem. It is a separate repository and deployment because congressional trading data requires PDF scraping, regex parsing, and a daily batch pipeline that is fundamentally different from Ghostfolio's portfolio tracking or AgentForge's AI agent work.

### 1. Automated PTR Scraping & Parsing Pipeline

A scheduled scraper discovers new Periodic Transaction Reports from `disclosures-clerk.house.gov`, downloads PDFs, extracts text with `pdftotext -layout` (preserving column alignment critical for parsing), and runs regex-based extraction to produce structured trade records.

Each trade record includes: ticker, asset description, asset type (stock/ETF/option/bond), transaction type (purchase/sale/exchange), transaction date, notification date, amount range ($1K–$50M brackets), owner (self/spouse/joint/dependent), and capital gains flag.

The pipeline runs daily at 6 AM UTC via APScheduler with production-grade reliability:
- Exponential backoff with jitter (1s → 2s → 4s) on download failures
- Circuit breaker: pauses for 1 hour after 5 consecutive failures
- Per-filing error isolation: one bad PDF doesn't block the rest
- Retry logic: up to 3 attempts per filing with persistent error tracking
- Rate limiting: 1-second delay between requests to respect government servers
- PDF security: 10MB size limit, magic bytes validation, download timeout

### 2. Stateful Trade Database with Full CRUD

All parsed data lives in a SQLite database (WAL mode, 64MB cache) with four tables:

| Table | Purpose | CRUD Operations |
|-------|---------|----------------|
| `filings` | Metadata for each House disclosure filing | **Create**: `insert_filing()` on new discovery. **Read**: joined into trade responses. **Update**: `update_filing_status()` tracks pending → parsed → error with retry counts. |
| `trades` | Individual stock transactions (~24K rows) | **Create**: `insert_trades()` with upsert logic (deduplicates on filing+ticker+date+type+owner). **Read**: exposed via 8 REST API endpoints with filtering, pagination, and aggregation. |
| `scraper_runs` | Audit log of scrape cycles | **Create**: logged on each run start. **Update**: completed with counts and status. **Read**: used by health check. |
| `price_cache` | Cached stock closing prices from Yahoo Finance | **Create**: fetched on demand and cached. **Read**: used for performance calculations. |

### 3. Stock Price Integration & Performance Analytics

A price service fetches historical closing prices from Yahoo Finance, caches them locally, and calculates trade returns (30/60/90-day) versus the S&P 500 benchmark. This enables the killer feature: **scoring congress members' trading track records against the market** — the exact data point that reveals whether elected officials are benefiting from information asymmetry.

### 4. REST API (How the Agent Accesses the Data)

All data is exposed through the open source project's FastAPI REST API at `/api/v1/*`, which is how the AgentForge agent accesses congressional trading data:

| Agent Action | API Endpoint | What It Returns |
|---|---|---|
| Look up trades for a stock | `GET /api/v1/trades?ticker=AAPL` | Congressional trades with member, date, amount, type |
| Search by congress member | `GET /api/v1/trades?member=Pelosi` | All trades by a specific member |
| Get summary statistics | `GET /api/v1/trades/summary?ticker=NVDA` | Buy/sell counts, unique members, net sentiment |
| Get trade volume trends | `GET /api/v1/trades/trending` | Top traded tickers by volume over time |
| Evaluate member performance | `GET /api/v1/members/{name}/performance` | Trade returns vs S&P 500 |
| Check ticker activity | `GET /api/v1/tickers/{ticker}/activity` | Price history with trade overlay markers |
| List active members | `GET /api/v1/members` | Members with most recent trading activity |
| System health check | `GET /api/v1/health` | DB stats, last scrape time, filing counts |

The API includes input validation (Pydantic), rate limiting (10 req/s via slowapi), pagination, and full Swagger documentation at `/docs`.

### 5. Interactive Dashboard

A single-page Plotly.js dashboard at `/dashboard` visualizes trending tickers, recent trades, and member performance — useful for visual exploration and demo purposes.

## The Data Source

### Primary: U.S. House of Representatives Financial Disclosure Reports

- **Source**: `disclosures-clerk.house.gov/public_disc`
- **Format**: PDF files (Periodic Transaction Reports) indexed via annual XML/ZIP archives
- **What it contains**: Every stock trade by every sitting House member — ticker, amount bracket, buy/sell/exchange, transaction date, disclosure date, and asset owner
- **Why it matters for this domain**: This is the single authoritative source for congressional stock trading activity. No other public dataset provides this information in structured form. It is directly relevant to the Ghostfolio portfolio tracking domain because it answers the question "what are lawmakers doing with the same securities I hold?"
- **Scope**: ~24,000 trades across ~2,000 filings from 2020 to present
- **Update frequency**: Daily scrape at 6 AM UTC
- **Data handling**: Missing/invalid data is handled cleanly — PDFs that fail parsing are marked with error status, retry count tracked, and retried with exponential backoff (up to 3 attempts)

### Secondary: Yahoo Finance (yfinance)

- **Source**: Yahoo Finance API via the `yfinance` Python library
- **Purpose**: Historical stock closing prices for performance calculations (trade returns vs S&P 500)
- **Caching**: All prices stored in a local `price_cache` SQLite table, only fetched when >10% of business days are missing from cache

## The Impact

### Domain-Specific Value

This data source fills a critical gap in the open-source personal finance ecosystem. Ghostfolio and similar portfolio trackers are excellent at showing you *your* positions, but they have no awareness of what powerful market participants — specifically, elected officials with access to non-public information — are doing with the same securities.

Congressional trading data is uniquely valuable in this domain because:

1. **Information asymmetry is the core concern.** Congress members receive classified briefings, sit on regulatory committees, and shape legislation that directly affects stock prices. Multiple academic studies have documented that congressional portfolios systematically outperform the market. This isn't general market data — it's a signal that directly informs investment risk assessment.

2. **The STOCK Act created a disclosure obligation but not transparency.** The law requires disclosure within 45 days, but the data is published as unstructured PDFs on a government website with no API, no search, and no alerts. Converting this into a queryable data source is a genuine public service.

3. **No existing open-source solution provides this data via API.** Commercial services like Quiver Quantitative charge subscription fees. Capitol Trades provides a web interface but no API. Our datastore makes this data freely available and programmatically accessible — exactly what an AI agent needs.

4. **It transforms portfolio management from passive to informed.** Instead of just tracking positions, a Ghostfolio user with AgentForge can now ask: "Show me congressional trading activity on my top 5 holdings this quarter" and get an instant answer with buy/sell sentiment, member names, and amount ranges.

### Practical Impact

- **For retail investors**: Know when elected officials are trading your stocks before the 45-day disclosure window closes. Spot unusual activity patterns.
- **For journalists/researchers**: Query the full disclosure corpus programmatically instead of reading PDFs one at a time. Cross-reference trading activity with committee assignments and legislative votes.
- **For the AI agent**: Congressional trading data becomes a first-class tool the agent can reason about — combining it with portfolio holdings, market data, and news to generate actionable analysis.
- **For the ecosystem**: Runs at $5/month on Railway with SQLite. No expensive financial data subscriptions required. The entire pipeline is open source and self-hostable.

## Technical Architecture

```
disclosures-clerk.house.gov          Yahoo Finance
   (annual ZIP → XML index)           (stock prices)
           │                                │
           ▼                                ▼
   ┌──────────────┐                ┌──────────────┐
   │   Scraper     │                │ Price Service │
   │ (daily cron)  │                │  (on-demand)  │
   └──────┬───────┘                └──────┬───────┘
          │ download PDFs                  │ fetch + cache
          ▼                                ▼
   ┌──────────────┐          ┌─────────────────────┐
   │    Parser     │          │    SQLite Database   │
   │ (pdftotext +  │────────▶│                     │
   │  regex)       │          │  filings (2K rows)  │
   └──────────────┘          │  trades (24K rows)  │
                              │  price_cache        │
                              │  scraper_runs       │
                              └─────────┬───────────┘
                                        │
                                        ▼
                              ┌─────────────────────┐
                              │   FastAPI REST API   │
                              │    /api/v1/*         │
                              │  (rate-limited,      │
                              │   paginated,         │
                              │   Swagger docs)      │
                              └─────────┬───────────┘
                                        │
                            ┌───────────┼───────────┐
                            ▼           ▼           ▼
                      AgentForge    Dashboard    Direct
                      (AI agent    (Plotly.js)   API
                       tool calls)              consumers
```

## How This Meets the Bounty Requirements

| Requirement | How It's Met |
|---|---|
| **New data source relevant to the problem space** | U.S. House financial disclosures — directly relevant to Ghostfolio's portfolio tracking domain. Answers "are congress members trading my stocks?" |
| **Agent accesses data through the open source project's API** | AgentForge calls the FastAPI REST API at `/api/v1/*` with structured query parameters and receives JSON responses |
| **Stateful data tied to the data source with CRUD operations** | SQLite database with 4 tables. Create (insert filings/trades), Read (8 API endpoints), Update (filing status tracking), Delete (maintenance). Agent uses Read operations via API. |
| **Repeatable setup** | Dockerized with `python:3.12-slim` + `poppler-utils`. Single `docker build && docker run`. Documented in README. |
| **Handles missing/invalid data** | Exponential backoff, circuit breaker, per-filing error isolation, retry tracking, PDF size/timeout limits, date validation, amount bracket validation |
