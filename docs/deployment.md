# Production Deployment (Railway)

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

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_PATH` | `/data/congressional_trades.db` | SQLite DB path. Set to `data/congressional_trades.db` for local dev. |
| `LOG_LEVEL` | `INFO` | Logging level |
| `SCRAPE_HOUR_UTC` | `6` | Hour (UTC) for the daily scrape cron job |
| `SCRAPE_START_YEAR` | `2020` | Earliest year to scrape filings from |
