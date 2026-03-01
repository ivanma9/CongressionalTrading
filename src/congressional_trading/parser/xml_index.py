"""Parse the House Financial Disclosure XML index file."""

from __future__ import annotations

import logging
from datetime import datetime

from lxml import etree

logger = logging.getLogger(__name__)


def parse_xml_index(xml_bytes: bytes) -> list[dict]:
    """Parse the FD XML index and return all filing records.

    Args:
        xml_bytes: Raw bytes of the {YEAR}FD.xml file.

    Returns:
        List of filing dicts with keys: doc_id, prefix, first, last, suffix,
        filing_type, state_district, filing_year, filing_date.
    """
    root = etree.fromstring(xml_bytes)
    filings = []

    for member in root.iter("Member"):
        try:
            filing = _parse_member_element(member)
            if filing:
                filings.append(filing)
        except Exception:
            logger.warning("Failed to parse XML member element", exc_info=True)

    logger.info("Parsed %d filings from XML index", len(filings))
    return filings


def filter_ptrs(filings: list[dict]) -> list[dict]:
    """Filter filings to only PTR (Periodic Transaction Report) types."""
    return [f for f in filings if f["filing_type"] == "P"]


def _parse_member_element(member: etree._Element) -> dict | None:
    """Parse a single <Member> element into a filing dict."""
    doc_id = _text(member, "DocID")
    if not doc_id:
        return None

    filing_date_raw = _text(member, "FilingDate") or ""
    try:
        filing_date = datetime.strptime(filing_date_raw, "%m/%d/%Y").strftime("%Y-%m-%d")
    except ValueError:
        filing_date = filing_date_raw

    year_raw = _text(member, "Year")
    try:
        filing_year = int(year_raw) if year_raw else 0
    except ValueError:
        filing_year = 0

    return {
        "doc_id": doc_id.strip(),
        "prefix": _text(member, "Prefix"),
        "first": _text(member, "First") or "",
        "last": _text(member, "Last") or "",
        "suffix": _text(member, "Suffix"),
        "filing_type": _text(member, "FilingType") or "",
        "state_district": _text(member, "StateDst") or "",
        "filing_year": filing_year,
        "filing_date": filing_date,
    }


def _text(parent: etree._Element, tag: str) -> str | None:
    """Get text content of a child element, or None."""
    el = parent.find(tag)
    if el is not None and el.text:
        return el.text.strip()
    return None
