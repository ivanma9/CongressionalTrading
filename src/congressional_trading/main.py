"""FastAPI application entry point with scheduler setup."""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from congressional_trading import config
from congressional_trading.api.routes import router
from congressional_trading.db.database import close_connection, get_connection
from congressional_trading.scraper.scheduler import start_scheduler, stop_scheduler


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
app.include_router(router)
