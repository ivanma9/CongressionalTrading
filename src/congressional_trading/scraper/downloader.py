"""ZIP + PDF download logic with rate limiting, retries, and circuit breaker."""

from __future__ import annotations

import io
import logging
import random
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import httpx

from congressional_trading import config
from congressional_trading.db import queries
from congressional_trading.parser.ptr_parser import parse_ptr_text
from congressional_trading.parser.xml_index import filter_ptrs, parse_xml_index

logger = logging.getLogger(__name__)

BACKUP_DIR = Path("/data/backups")
MAX_BACKUPS = 7

DOC_ID_PATTERN = re.compile(r"^[0-9]+$")


def _backup_database(db_path: Path) -> None:
    """Copy the DB file to /data/backups/, keeping only the last 7 backups."""
    try:
        if not db_path.exists():
            logger.debug("No database file at %s to back up", db_path)
            return

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{db_path.stem}_{timestamp}{db_path.suffix}"
        backup_path = BACKUP_DIR / backup_name

        shutil.copy2(db_path, backup_path)
        logger.info("Database backed up to %s", backup_path)

        # Prune old backups — keep only the most recent MAX_BACKUPS
        backups = sorted(BACKUP_DIR.glob(f"{db_path.stem}_*{db_path.suffix}"))
        if len(backups) > MAX_BACKUPS:
            for old in backups[: len(backups) - MAX_BACKUPS]:
                old.unlink()
                logger.info("Removed old backup %s", old.name)
    except Exception:
        logger.error("Database backup failed", exc_info=True)


def _download_with_backoff(url: str, max_retries: int = 3) -> bytes:
    """Download a PDF with exponential backoff and jitter.

    Retry delays: 1s, 2s, 4s (±0.5s jitter). Only retries on 5xx and
    network errors. Raises on 4xx, validation errors, or exhausted retries.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return _download_pdf(url)
        except httpx.HTTPStatusError as e:
            if e.response.status_code < 500:
                raise  # Don't retry client errors (4xx)
            last_exc = e
        except httpx.TransportError as e:
            last_exc = e
        except ValueError:
            raise  # Don't retry validation errors (bad magic bytes, too large)

        if attempt < max_retries:
            delay = (2**attempt) + random.uniform(-0.5, 0.5)
            logger.warning(
                "Retry %d/%d for %s after %.1fs (error: %s)",
                attempt + 1, max_retries, url, delay, last_exc,
            )
            time.sleep(delay)

    raise last_exc  # type: ignore[misc]


def run_scrape_cycle(conn) -> dict:
    """Execute a full scrape cycle.

    Returns dict with keys: new_filings, new_trades, retried_filings, errors.
    """
    _backup_database(config.DATABASE_PATH)

    run_id = queries.insert_scraper_run(conn)
    stats = {"new_filings": 0, "new_trades": 0, "retried_filings": 0, "errors": 0}
    consecutive_failures = 0

    try:
        # Determine which years to scrape
        now = datetime.now(timezone.utc)
        start_year = int(config.SCRAPE_START_YEAR)
        years = list(range(start_year, now.year + 1))

        # Download and parse XML indices
        existing_ids = queries.get_existing_doc_ids(conn)
        new_filings: list[dict] = []

        for year in years:
            try:
                xml_bytes = _download_xml_index(year)
                if xml_bytes is None:
                    continue
                all_filings = parse_xml_index(xml_bytes)
                ptrs = filter_ptrs(all_filings)
                for f in ptrs:
                    if f["doc_id"] not in existing_ids:
                        queries.insert_filing(conn, f)
                        new_filings.append(f)
                        stats["new_filings"] += 1
                conn.commit()
            except Exception:
                logger.error("Failed to process year %d", year, exc_info=True)

        # Process new + retryable filings
        pending = queries.get_pending_filings(conn)
        stats["retried_filings"] = len(pending) - len(new_filings)
        if stats["retried_filings"] < 0:
            stats["retried_filings"] = 0

        for filing in pending:
            if consecutive_failures >= config.CIRCUIT_BREAKER_THRESHOLD:
                logger.warning(
                    "Circuit breaker tripped after %d failures, pausing",
                    consecutive_failures,
                )
                time.sleep(config.CIRCUIT_BREAKER_PAUSE)
                consecutive_failures = 0

            doc_id = filing["doc_id"]
            year = filing["filing_year"]

            try:
                trades = _process_filing(doc_id, year)
                if trades:
                    # Validate notification_date <= filing_date
                    filing_date = filing.get("filing_date")
                    if filing_date:
                        for trade in trades:
                            nd = trade.get("notification_date")
                            if nd and nd > filing_date:
                                logger.warning(
                                    "Notification date %s is after filing date %s "
                                    "for ticker %s in filing %s",
                                    nd, filing_date,
                                    trade.get("ticker"), doc_id,
                                )
                    inserted = queries.insert_trades(conn, doc_id, trades)
                    stats["new_trades"] += inserted
                    queries.update_filing_status(conn, doc_id, "parsed")
                else:
                    queries.update_filing_status(
                        conn, doc_id, "parse_error",
                        error_message="No transactions extracted",
                    )
                conn.commit()
                consecutive_failures = 0
            except Exception as e:
                logger.error("Failed to process filing %s: %s", doc_id, e)
                queries.update_filing_status(conn, doc_id, "error", error_message=str(e))
                conn.commit()
                stats["errors"] += 1
                consecutive_failures += 1

            time.sleep(config.RATE_LIMIT_DELAY)

        queries.update_scraper_run(
            conn, run_id,
            status="success",
            new_filings=stats["new_filings"],
            new_trades=stats["new_trades"],
            retried_filings=stats["retried_filings"],
        )
        logger.info("Scrape cycle complete: %s", stats)

    except Exception as e:
        logger.error("Scrape cycle failed: %s", e, exc_info=True)
        queries.update_scraper_run(
            conn, run_id,
            status="error",
            error_message=str(e),
            new_filings=stats["new_filings"],
            new_trades=stats["new_trades"],
        )

    return stats


def _download_xml_index(year: int) -> bytes | None:
    """Download the annual ZIP and extract the XML index."""
    url = config.ZIP_URL_TEMPLATE.format(year=year)
    logger.info("Downloading ZIP index for %d from %s", year, url)

    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": config.USER_AGENT})
            resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.error("Failed to download ZIP for %d: %s", year, e)
        return None

    try:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            xml_name = f"{year}FD.xml"
            if xml_name in zf.namelist():
                return zf.read(xml_name)
            # Try case-insensitive match
            for name in zf.namelist():
                if name.upper() == xml_name.upper():
                    return zf.read(name)
            logger.error("XML file %s not found in ZIP", xml_name)
            return None
    except zipfile.BadZipFile:
        logger.error("Corrupted ZIP file for year %d", year)
        return None


def _process_filing(doc_id: str, year: int) -> list[dict]:
    """Download and parse a single PTR PDF."""
    if not DOC_ID_PATTERN.match(doc_id):
        raise ValueError(f"Invalid DocID format: {doc_id}")

    url = config.PTR_PDF_URL_TEMPLATE.format(year=year, doc_id=doc_id)
    logger.debug("Downloading PDF %s", url)

    pdf_bytes = _download_with_backoff(url)
    text = _extract_text(pdf_bytes)
    return parse_ptr_text(text, filing_year=year)


def _download_pdf(url: str) -> bytes:
    """Download a PDF with size/timeout limits and magic byte validation."""
    with httpx.Client(
        timeout=config.PDF_DOWNLOAD_TIMEOUT,
        follow_redirects=True,
    ) as client:
        resp = client.get(url, headers={"User-Agent": config.USER_AGENT})
        resp.raise_for_status()

    content = resp.content

    if len(content) > config.PDF_MAX_SIZE:
        raise ValueError(f"PDF exceeds {config.PDF_MAX_SIZE} byte limit: {len(content)} bytes")

    if not content[:5] == b"%PDF-":
        raise ValueError("Downloaded file is not a valid PDF (bad magic bytes)")

    return content


def _extract_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF using pdftotext -layout."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
        tmp.write(pdf_bytes)
        tmp.flush()

        result = subprocess.run(
            ["pdftotext", "-layout", tmp.name, "-"],
            capture_output=True,
            text=True,
            timeout=config.PDF_PARSE_TIMEOUT,
        )

    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {result.stderr}")

    return result.stdout
