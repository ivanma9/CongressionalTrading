"""FastAPI application entry point with scheduler setup."""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from congressional_trading import config
from congressional_trading.api.chart_routes import chart_router
from congressional_trading.api.routes import router
from congressional_trading.db.database import close_connection, get_connection
from congressional_trading.scraper.scheduler import start_scheduler, stop_scheduler

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"


def _setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format='{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_logging()
    get_connection()
    scheduler = start_scheduler()
    yield
    stop_scheduler()
    close_connection()


limiter = Limiter(key_func=get_remote_address, default_limits=["10/second"])

app = FastAPI(
    title="Congressional Trading API",
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(chart_router)
app.include_router(router)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    html_path = STATIC_DIR / "dashboard.html"
    return HTMLResponse(content=html_path.read_text())


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
