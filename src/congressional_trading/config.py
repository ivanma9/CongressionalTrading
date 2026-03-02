"""Application configuration from environment variables."""

from __future__ import annotations

import os
from pathlib import Path


DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "/data/congressional_trades.db"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
SCRAPE_HOUR_UTC = int(os.getenv("SCRAPE_HOUR_UTC", "6"))
SCRAPE_START_YEAR = os.getenv("SCRAPE_START_YEAR", "2020")

# Scraper constants
HOUSE_BASE_URL = "https://disclosures-clerk.house.gov/public_disc"
ZIP_URL_TEMPLATE = f"{HOUSE_BASE_URL}/financial-pdfs/{{year}}FD.zip"
PTR_PDF_URL_TEMPLATE = f"{HOUSE_BASE_URL}/ptr-pdfs/{{year}}/{{doc_id}}.pdf"

USER_AGENT = "CongressionalTradingBot/1.0 (https://github.com/ivanma/congressional-trading)"
PDF_MAX_SIZE = 10 * 1024 * 1024  # 10 MB
PDF_DOWNLOAD_TIMEOUT = 30  # seconds
PDF_PARSE_TIMEOUT = 10  # seconds
RATE_LIMIT_DELAY = 1.0  # seconds between PDF downloads
MAX_RETRY_COUNT = 3
CIRCUIT_BREAKER_THRESHOLD = 5  # consecutive failures before pausing
CIRCUIT_BREAKER_PAUSE = 3600  # 1 hour in seconds
