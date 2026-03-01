"""APScheduler cron job for daily scraping."""

from __future__ import annotations

import fcntl
import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from congressional_trading import config
from congressional_trading.db.database import get_connection
from congressional_trading.scraper.downloader import run_scrape_cycle

logger = logging.getLogger(__name__)

LOCK_PATH = os.path.join(tempfile.gettempdir(), "congressional_scraper.lock")

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler:
    """Start the APScheduler background scheduler."""
    global _scheduler

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _run_with_lock,
        "cron",
        hour=config.SCRAPE_HOUR_UTC,
        minute=0,
        id="daily_scrape",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler

    # Run initial scrape if needed
    if _should_run_initial_scrape():
        logger.info("Running initial scrape on startup")
        scheduler.add_job(_run_with_lock, id="initial_scrape")

    return scheduler


def stop_scheduler() -> None:
    """Stop the scheduler if running."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def _run_with_lock() -> None:
    """Run a scrape cycle with file-based lock to prevent concurrent runs."""
    lock_fd = None
    try:
        lock_fd = open(LOCK_PATH, "w")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        logger.warning("Another scrape cycle is already running, skipping")
        if lock_fd:
            lock_fd.close()
        return

    try:
        conn = get_connection()
        run_scrape_cycle(conn)
    except Exception:
        logger.error("Scrape cycle failed", exc_info=True)
    finally:
        if lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()


def _should_run_initial_scrape() -> bool:
    """Check if we should run a scrape on startup."""
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT completed_at FROM scraper_runs WHERE status = 'success' "
            "ORDER BY completed_at DESC LIMIT 1"
        ).fetchone()

        if row is None:
            return True

        last_scrape = datetime.fromisoformat(row[0])
        if last_scrape.tzinfo is None:
            last_scrape = last_scrape.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - last_scrape > timedelta(hours=24)
    except Exception:
        return True
