"""Compiled regex patterns and constants for PTR PDF parsing."""

from __future__ import annotations

import re

# --- Compiled regex patterns ---

TICKER_PATTERN = re.compile(r'\(([A-Z]{1,5})\)')
ASSET_TYPE_PATTERN = re.compile(r'\[(ST|OP|EF|DC|UT|AH|OT)\]')
TRANSACTION_PATTERN = re.compile(r'\b(P|S|E)\b')
PARTIAL_SALE_PATTERN = re.compile(r'S\s*\(partial\)')
OWNER_PATTERN = re.compile(r'\b(SP|JT|DC)\b')
DATE_PATTERN = re.compile(r'(\d{2}/\d{2}/\d{4})')
AMOUNT_PATTERN = re.compile(r'\$([0-9,]+)\s*-?\s*\$([0-9,]+)')
AMOUNT_OVER_PATTERN = re.compile(r'Over\s+\$([0-9,]+)')
DESCRIPTION_PATTERN = re.compile(r'[DC]\w*\s*(?::|;)\s*(.+)', re.IGNORECASE)
CAP_GAINS_PATTERN = re.compile(r'\bcap\w*\s+gains?\b', re.IGNORECASE)
FILING_ID_PATTERN = re.compile(r'Filing\s+ID\s+#(\d+)')

# Header row pattern to find start of transactions table
HEADER_PATTERN = re.compile(r'ID\s+Owner\s+Asset')

# --- Constants ---

AMOUNT_RANGES = [
    (1_001, 15_000),
    (15_001, 50_000),
    (50_001, 100_000),
    (100_001, 250_000),
    (250_001, 500_000),
    (500_001, 1_000_000),
    (1_000_001, 5_000_000),
    (5_000_001, 25_000_000),
    (25_000_001, 50_000_000),
    (50_000_001, None),
]

OWNER_MAP = {
    'SP': 'spouse',
    'JT': 'joint',
    'DC': 'dependent',
}

TRANSACTION_TYPE_MAP = {
    'P': 'purchase',
    'S': 'sale',
    'E': 'exchange',
}
