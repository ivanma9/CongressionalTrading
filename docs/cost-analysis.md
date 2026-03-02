# Cost Analysis

## Current Infrastructure

| Component | Provider | Spec |
|---|---|---|
| Application | Railway (Hobby plan) | 1 replica, single process |
| Database | SQLite on Railway volume | 150 MB used / 5 GB allocated |
| Stock prices | yfinance | Free API |
| Data source | disclosures-clerk.house.gov | Free public data |
| Source code | GitHub | Free (public repo) |

## Railway Costs

### Plan: Hobby ($5/month)

The $5 subscription includes $5 of usage credit. Pricing based on [Railway docs](https://docs.railway.com/pricing):

| Resource | Rate | Our Usage | Monthly Cost |
|---|---|---|---|
| CPU | $20/vCPU/month | ~0.05 vCPU avg (idle most of day, spikes during scrape) | ~$1.00 |
| Memory | $10/GB/month | ~256 MB constant | ~$2.50 |
| Volume | $0.15/GB/month | 0.15 GB | ~$0.02 |
| Egress | $0.05/GB | ~0.5 GB (API responses + PDF downloads) | ~$0.03 |
| **Total usage** | | | **~$3.55** |
| **Billed** | | | **$5.00** (minimum subscription) |

We're well within the $5 credit — no overage charges.

### What Drives Cost

1. **Memory** (~70% of usage) — Python + FastAPI + APScheduler baseline. Unavoidable.
2. **CPU** (~28%) — Mostly idle. Spikes during daily scrape cycle (PDF downloads + parsing) and yfinance lookups.
3. **Volume + Egress** (~2%) — Negligible. DB is small, API traffic is low.

## Cost Projections

### Current State (low traffic)
- ~24K trades, ~2K filings
- Handful of API requests/day
- **$5/month**

### Moderate Growth (100 daily users)
- Same data volume (House disclosures grow ~500 filings/year)
- ~10K API requests/day, ~1 GB egress
- Memory stays the same, CPU slightly higher
- **$5/month** (still within credit)

### High Traffic (1K+ daily users)
- Egress increases to ~10 GB/month (+$0.50)
- CPU spikes from concurrent requests (~0.1 vCPU avg)
- **$5–7/month** on Hobby, or **$20/month** on Pro for better limits

### If We Add Features
| Feature | Cost Impact |
|---|---|
| More years of data (pre-2020) | +50 MB volume, negligible |
| Real-time price updates (polling yfinance hourly) | +$0.50 CPU |
| Multiple workers (for concurrency) | Need Redis for rate limiting — add Railway Redis ($5–10/month) |
| Senate disclosures | +~2x data volume, +~2x scrape CPU, still under $5 |
| Upgrade to Pro plan | $20/month, higher resource limits, team features |

## External API Costs

| API | Cost | Limit |
|---|---|---|
| yfinance | Free | Unofficial, no SLA. Rate-limited by Yahoo. We cache aggressively. |
| House disclosures | Free | Public data. We rate-limit to 1 req/s to avoid blocks. |

### yfinance Risk

yfinance is an unofficial Yahoo Finance wrapper. If it breaks:
- **Fallback**: Switch to Alpha Vantage (free tier: 25 req/day) or Polygon.io ($30/month)
- **Impact**: Only affects performance/ticker activity charts. Core trade data is unaffected.

## Cost Comparison

| Approach | Monthly Cost | Notes |
|---|---|---|
| **Current (Railway Hobby + SQLite)** | **$5** | Simplest, sufficient for current scale |
| Railway Pro + SQLite | $20 | Team features, higher limits |
| Railway + Postgres (Railway add-on) | $10–25 | Overkill for our read pattern |
| AWS (EC2 t3.micro + EBS) | $10–15 | More ops burden, similar performance |
| Fly.io (single machine) | $5–7 | Comparable to Railway |
| Render (free tier) | $0 | Spins down on inactivity, cold starts |
| Vercel + Turso (serverless) | $0–5 | Would need to rewrite data layer |

## Summary

**Total monthly cost: $5/month.** This covers everything — hosting, compute, storage, and database. No external paid APIs. The architecture is cost-efficient because:

1. SQLite eliminates a separate database service
2. Single process keeps memory low
3. In-memory rate limiting avoids Redis
4. Aggressive caching minimizes external API calls
5. Data volume is inherently small (~500 new filings/year)

The $5/month floor is the Railway Hobby subscription minimum. Our actual resource usage is ~$3.55, so we have headroom before any overage.
