# Demo Script (~2 minutes)

## Setup Before Recording

- Open browser to the prod dashboard: `https://congressional-trading-datastore-production-9fd6.up.railway.app/dashboard`
- Have a second tab ready for the API docs: `.../docs`
- Optional: terminal open for a quick curl command

---

## Part 1: The Problem (20 seconds)

**Talking points:**

> Members of Congress are required to disclose their stock trades, but the data is buried in PDFs on a government website. It's hard to search, hard to analyze, and there's no easy way to see what they're buying or whether they're beating the market.
>
> This service scrapes those filings automatically, parses the PDFs into structured data, and serves it through an API and interactive dashboard.

**On screen:** Briefly show the House disclosure website or a raw PDF to contrast with what we built. Then switch to the dashboard.

---

## Part 2: Dashboard Walkthrough (60 seconds)

### Tab 1 — Recent Activity (~15s)

- Show the recent trades table
- Point out: member names, tickers, buy/sell, amount ranges
- Change the time window (30 → 365 days) to show the range of data
- Filter by a specific ticker (e.g., NVDA) or member name

### Tab 2 — Trending Tickers (~15s)

- Show the stacked bar chart of most-traded tickers
- Point out green (buys) vs red (sells) — "You can see at a glance what Congress is buying vs selling"
- Hover over a bar to show member breakdown

### Tab 3 — Member Performance (~15s)

- Select a well-known member (e.g., Pelosi)
- Show the scatter plot of trade returns vs S&P 500 benchmark
- Point out win rate and average return stats
- Toggle the return window (30d → 90d)

### Tab 4 — Ticker Deep Dive (~15s)

- Search for a popular ticker (e.g., AAPL or MSFT)
- Show the price chart with congressional trade markers (green/red arrows)
- Point out the SPY overlay — "You can see when Congress bought relative to the stock's performance"

---

## Part 3: Under the Hood (30 seconds)

**Talking points (pick 2-3):**

> - Scrapes daily from disclosures-clerk.house.gov — currently tracking ~24,000 trades across 2,000 filings going back to 2020
> - Parses column-aligned PDFs with pdftotext, with validation guardrails that reject impossible dates from misaligned columns
> - REST API with FastAPI — rate limited, documented at /docs
> - Stock price data from Yahoo Finance, cached locally so repeat lookups are instant
> - Runs on Railway for $5/month — single container, SQLite database, no external services needed

**On screen:** Briefly flash the Swagger docs page (`/docs`) to show the API endpoints. Optionally run a quick curl:

```bash
curl -s "https://congressional-trading-datastore-production-9fd6.up.railway.app/api/v1/trades?ticker=NVDA&days=365" | python3 -m json.tool | head -30
```

---

## Part 4: Wrap Up (10 seconds)

> Open source on GitHub. The API is live and free to use. Link in the description.

**On screen:** Show the GitHub repo page briefly.

---

## Key Stats to Mention

| Stat | Value |
|---|---|
| Total trades tracked | ~24,000 |
| Filings parsed | ~2,000 |
| Data range | 2020–present |
| Update frequency | Daily (automated) |
| Hosting cost | $5/month |
| External paid APIs | None |

## Tips

- Keep mouse movements deliberate — don't wander around the UI
- Let charts load before narrating them
- The member performance tab may take 2-3 seconds on first load (yfinance fetch) — fill that time with narration
- If something loads slowly, say "prices are fetched and cached on first lookup" — turns a wait into a feature explanation
