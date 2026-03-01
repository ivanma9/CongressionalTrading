"""Parse PTR PDF text (from pdftotext -layout) into structured trade records."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

from .patterns import (
    AMOUNT_OVER_PATTERN,
    AMOUNT_PATTERN,
    AMOUNT_RANGES,
    ASSET_TYPE_PATTERN,
    DATE_PATTERN,
    OWNER_MAP,
    PARTIAL_SALE_PATTERN,
    TICKER_PATTERN,
    TRANSACTION_TYPE_MAP,
)

logger = logging.getLogger(__name__)

# Metadata line prefixes in the PDF: "F S :", "S O :", "D :", "C :"
_META_LINE_RE = re.compile(
    r'^\s*(?:'
    r'F\s+S|'        # Filing Status
    r'S\s+O|'        # Sub-holding Of
    r'D\s+:|'        # Description
    r'C\s+:|'        # Comment
    r'D\w+\s*:|'     # Description (variant)
    r'C\w+\s*:'      # Comment (variant)
    r')'
)


def parse_ptr_text(text: str) -> list[dict]:
    """Parse raw PTR PDF text into a list of trade dicts.

    Args:
        text: Raw text output from `pdftotext -layout` on a PTR PDF.

    Returns:
        List of trade dicts with keys: ticker, asset_description, asset_type,
        transaction_type, owner, transaction_date, notification_date,
        amount_range_low, amount_range_high, description, cap_gains_over_200.
    """
    # Strip form-feed characters from multi-page PDF output
    text = text.replace('\x0c', '')

    blocks = _split_transaction_blocks(text)
    trades = []
    for block in blocks:
        trade = _parse_block(block)
        if trade is not None:
            trades.append(trade)
    return trades


def _split_transaction_blocks(text: str) -> list[str]:
    """Split the transactions section into individual transaction blocks.

    Each block contains the data lines and any following metadata lines
    for a single transaction.
    """
    lines = text.split('\n')

    # Find the start of the transactions table (after the header row)
    start_idx = None
    for i, line in enumerate(lines):
        if re.search(r'ID\s+Owner\s+Asset', line):
            start_idx = i + 1
            break

    if start_idx is None:
        return []

    # Skip sub-header lines (Type, Date, $200?)
    while start_idx < len(lines) and lines[start_idx].strip() and not DATE_PATTERN.search(lines[start_idx]):
        start_idx += 1

    # Find the end of the transactions section
    end_idx = len(lines)
    for i in range(start_idx, len(lines)):
        line = lines[i]
        if '* For the complete list' in line:
            end_idx = i
            break
        if 'I CERTIFY' in line:
            end_idx = i
            break

    transaction_lines = lines[start_idx:end_idx]

    # Split into raw groups separated by blank lines
    raw_groups: list[list[str]] = []
    current: list[str] = []
    for line in transaction_lines:
        if line.strip() == '':
            if current:
                raw_groups.append(current)
                current = []
        else:
            current.append(line)
    if current:
        raw_groups.append(current)

    # Merge data groups with following metadata groups.
    # A group is "metadata" if ALL its lines match metadata prefixes.
    blocks: list[str] = []
    i = 0
    while i < len(raw_groups):
        group = list(raw_groups[i])
        # Check if the NEXT group is metadata — if so, merge it
        while i + 1 < len(raw_groups) and _is_metadata_group(raw_groups[i + 1]):
            i += 1
            group.extend(raw_groups[i])
        blocks.append('\n'.join(group))
        i += 1

    return blocks


def _is_metadata_group(group: list[str]) -> bool:
    """Check if all lines in a group are metadata lines."""
    return all(_META_LINE_RE.match(line) for line in group)


def _parse_block(block: str) -> Optional[dict]:
    """Parse a single transaction block into a trade dict."""
    lines = block.split('\n')

    # Separate data lines from metadata lines
    data_lines: list[str] = []
    meta_lines: list[str] = []
    for line in lines:
        if _META_LINE_RE.match(line):
            meta_lines.append(line.strip())
        else:
            data_lines.append(line)

    if not data_lines:
        return None

    full_data = ' '.join(data_lines)

    # --- Extract fields ---

    # Ticker
    ticker_match = TICKER_PATTERN.search(full_data)
    ticker = ticker_match.group(1) if ticker_match else None

    # Asset type
    asset_type_match = ASSET_TYPE_PATTERN.search(full_data)
    asset_type = asset_type_match.group(1) if asset_type_match else None

    # Asset description
    asset_description = _extract_asset_description(full_data, ticker_match, asset_type_match)

    # Transaction type
    transaction_type = _extract_transaction_type(full_data)

    # Owner
    owner = _extract_owner(data_lines)

    # Dates (convert MM/DD/YYYY -> ISO YYYY-MM-DD)
    dates = DATE_PATTERN.findall(full_data)
    transaction_date = _convert_date(dates[0]) if len(dates) >= 1 else None
    notification_date = _convert_date(dates[1]) if len(dates) >= 2 else None

    # Validate date ordering
    _validate_date_order(transaction_date, notification_date, ticker)

    # Amount
    amount_range_low, amount_range_high = _extract_amount(full_data)

    # Validate amount bracket
    _validate_amount_bracket(amount_range_low, amount_range_high, ticker)

    # Description from metadata lines
    description = _extract_description(meta_lines)

    # Cap gains > $200k
    cap_gains = _extract_cap_gains(block)

    if not asset_description and not ticker:
        return None

    return {
        'ticker': ticker,
        'asset_description': asset_description or '',
        'asset_type': asset_type,
        'transaction_type': transaction_type,
        'owner': owner,
        'transaction_date': transaction_date,
        'notification_date': notification_date,
        'amount_range_low': amount_range_low,
        'amount_range_high': amount_range_high,
        'description': description,
        'cap_gains_over_200': cap_gains,
    }


def _convert_date(date_str: str) -> str | None:
    """Convert MM/DD/YYYY to ISO YYYY-MM-DD."""
    try:
        dt = datetime.strptime(date_str, "%m/%d/%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        logger.warning("Invalid date: %s", date_str)
        return None


def _validate_date_order(
    transaction_date: str | None,
    notification_date: str | None,
    ticker: str | None,
) -> None:
    """Log warning if transaction_date > notification_date."""
    if transaction_date and notification_date and transaction_date > notification_date:
        logger.warning(
            "Transaction date %s is after notification date %s for ticker %s",
            transaction_date,
            notification_date,
            ticker,
        )


def _validate_amount_bracket(
    low: int | None,
    high: int | None,
    ticker: str | None,
) -> None:
    """Log warning if amount range doesn't match a known bracket."""
    if low is None:
        return
    for bracket_low, bracket_high in AMOUNT_RANGES:
        if low == bracket_low and high == bracket_high:
            return
    logger.warning(
        "Unknown amount bracket $%s - $%s for ticker %s",
        f"{low:,}" if low else "?",
        f"{high:,}" if high else "None",
        ticker,
    )


def _extract_asset_description(full_data: str, ticker_match, asset_type_match) -> Optional[str]:
    """Extract the asset description from the data line."""
    text = full_data

    # Remove leading owner token
    text = re.sub(r'^\s*(SP|JT|DC)\s+', '', text)

    if ticker_match:
        # Adjust position for owner removal
        owner_offset = len(full_data) - len(text)
        desc_end = ticker_match.start() - owner_offset
        if desc_end < 0:
            desc_end = 0
        desc = text[:desc_end].strip()
    elif asset_type_match:
        owner_offset = len(full_data) - len(text)
        desc_end = asset_type_match.start() - owner_offset
        if desc_end < 0:
            desc_end = 0
        desc = text[:desc_end].strip()
    else:
        # No ticker or asset type - take text before the first large gap
        parts = re.split(r'\s{3,}', text)
        desc = parts[0].strip() if parts else None
        return desc

    # Clean up whitespace
    desc = re.sub(r'\s+', ' ', desc).strip()
    return desc if desc else None


def _extract_transaction_type(full_data: str) -> Optional[str]:
    """Extract transaction type from the data."""
    # Check for S (partial) first
    if PARTIAL_SALE_PATTERN.search(full_data):
        return 'sale_partial'

    # Strategy: find the P/S/E that appears between the asset info and dates.
    # It's surrounded by whitespace (typically 3+ spaces on each side).
    # Use a pattern that requires surrounding whitespace to avoid matching
    # letters in asset names like "SP" or "Partners".
    date_match = DATE_PATTERN.search(full_data)
    if not date_match:
        return None

    # Look in the region before the first date
    region = full_data[:date_match.start()]

    # The transaction type is a standalone P/S/E surrounded by multiple spaces
    tx_match = re.search(r'\s{2,}(P|S|E)\s{2,}', region)
    if tx_match:
        return TRANSACTION_TYPE_MAP.get(tx_match.group(1))

    # P/S/E after ticker closing paren: "(SCHW) P       12/14/2023"
    tx_match = re.search(r'\)\s+(P|S|E)\s{2,}', region)
    if tx_match:
        return TRANSACTION_TYPE_MAP.get(tx_match.group(1))

    # Transaction type right before the date with trailing whitespace
    tx_match = re.search(r'\s{2,}(P|S|E)\s+$', region)
    if tx_match:
        return TRANSACTION_TYPE_MAP.get(tx_match.group(1))

    return None


def _extract_owner(data_lines: list[str]) -> str:
    """Extract the owner from the data."""
    first_line = data_lines[0] if data_lines else ''
    stripped = first_line.lstrip()
    match = re.match(r'^(SP|JT|DC)\b', stripped)
    if match:
        return OWNER_MAP[match.group(1)]
    return 'self'


def _extract_amount(full_data: str) -> tuple[Optional[int], Optional[int]]:
    """Extract amount range from the data."""
    # Check for "Over $X" pattern first
    over_match = AMOUNT_OVER_PATTERN.search(full_data)
    if over_match:
        amount = int(over_match.group(1).replace(',', ''))
        return (amount + 1, None)

    match = AMOUNT_PATTERN.search(full_data)
    if match:
        low = int(match.group(1).replace(',', ''))
        high = int(match.group(2).replace(',', ''))
        return (low, high)

    # Handle split amounts: "$50,001 -" on one line, "$100,000" on next
    # The full_data has them joined with spaces
    split_match = re.search(r'\$([0-9,]+)\s*-\s+.*?\$([0-9,]+)', full_data)
    if split_match:
        low = int(split_match.group(1).replace(',', ''))
        high = int(split_match.group(2).replace(',', ''))
        return (low, high)

    return (None, None)


def _extract_description(meta_lines: list[str]) -> Optional[str]:
    """Extract description from metadata lines."""
    for line in meta_lines:
        # Match description/comment lines: "D : text" or "C : text"
        match = re.match(r'^[DC]\w*\s*:\s*(.+)', line)
        if match:
            desc = match.group(1).strip()
            if desc.lower() in ('new', ''):
                continue
            return desc
    return None


def _extract_cap_gains(block: str) -> Optional[bool]:
    """Extract capital gains > $200k indicator."""
    for line in block.split('\n'):
        if re.search(r'\bYes\s*$', line.rstrip()):
            return True
        if re.search(r'\bNo\s*$', line.rstrip()):
            return False
    return None
