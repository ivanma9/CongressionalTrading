"""Golden validation tests — compare parser output against hand-verified expected data.

Each fixture file is parsed and the output is compared field-by-field against
known-correct data, providing a regression test suite for the PTR parser.
"""

from pathlib import Path

import pytest

from congressional_trading.parser.ptr_parser import parse_ptr_text

FIXTURES = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


# ---------------------------------------------------------------------------
# Golden expected data
# ---------------------------------------------------------------------------

EXPECTED_20024277 = [
    {
        "ticker": "ALB",
        "asset_description": "Albemarle Corporation",
        "asset_type": "ST",
        "transaction_type": "sale",
        "owner": "spouse",
        "transaction_date": "2023-12-21",
        "notification_date": "2024-01-08",
        "amount_range_low": 1001,
        "amount_range_high": 15000,
        "description": None,
        "cap_gains_over_200": None,
    },
    {
        "ticker": "ALB",
        "asset_description": "Albemarle Corporation",
        "asset_type": "ST",
        "transaction_type": "sale",
        "owner": "spouse",
        "transaction_date": "2023-12-21",
        "notification_date": "2024-01-08",
        "amount_range_low": 1001,
        "amount_range_high": 15000,
        "description": None,
        "cap_gains_over_200": None,
    },
    {
        "ticker": "SCHW",
        "asset_description": "Charles Schwab Corporation",
        "asset_type": "ST",
        "transaction_type": "purchase",
        "owner": "spouse",
        "transaction_date": "2023-12-14",
        "notification_date": "2024-01-08",
        "amount_range_low": 50001,
        "amount_range_high": 100000,
        "description": None,
        "cap_gains_over_200": None,
    },
    {
        "ticker": "NEE",
        "asset_description": "NextEra Energy, Inc.",
        "asset_type": "ST",
        "transaction_type": "sale",
        "owner": "spouse",
        "transaction_date": "2023-12-21",
        "notification_date": "2024-01-08",
        "amount_range_low": 15001,
        "amount_range_high": 50000,
        "description": None,
        "cap_gains_over_200": None,
    },
]

EXPECTED_20024800 = [
    {
        "ticker": "NGL",
        "asset_description": "NGL ENERGY PARTNERS LP",
        "asset_type": "ST",
        "transaction_type": "sale",
        "owner": "self",
        "transaction_date": "2024-04-01",
        "notification_date": "2024-04-04",
        "amount_range_low": 100001,
        "amount_range_high": 250000,
        "description": None,
        "cap_gains_over_200": None,
    },
]

EXPECTED_20024901 = [
    {
        "ticker": "FMAO",
        "asset_description": "Farmers & Merchants Bancorp, Inc.",
        "asset_type": "ST",
        "transaction_type": "purchase",
        "owner": "spouse",
        "transaction_date": "2024-04-20",
        "notification_date": "2024-04-20",
        "amount_range_low": 1001,
        "amount_range_high": 15000,
        "description": "dividend reinvestment",
        "cap_gains_over_200": None,
    },
]

EXPECTED_20025000 = [
    {
        "ticker": "COP",
        "asset_description": "ConocoPhillips Common Stock",
        "asset_type": "ST",
        "transaction_type": "purchase",
        "owner": "joint",
        "transaction_date": "2024-04-02",
        "notification_date": "2024-05-06",
        "amount_range_low": 15001,
        "amount_range_high": 50000,
        "description": None,
        "cap_gains_over_200": None,
    },
    {
        "ticker": "HXL",
        "asset_description": "Hexcel Corporation Common Stock",
        "asset_type": "ST",
        "transaction_type": "sale",
        "owner": "joint",
        "transaction_date": "2024-04-24",
        "notification_date": "2024-05-06",
        "amount_range_low": 15001,
        "amount_range_high": 50000,
        "description": None,
        "cap_gains_over_200": None,
    },
    {
        "ticker": "JPM",
        "asset_description": "JP Morgan Chase & Co. Common",
        "asset_type": "ST",
        "transaction_type": "purchase",
        "owner": "joint",
        "transaction_date": "2024-04-24",
        "notification_date": "2024-05-06",
        "amount_range_low": 15001,
        "amount_range_high": 50000,
        "description": None,
        "cap_gains_over_200": None,
    },
    {
        "ticker": "LULU",
        "asset_description": "lululemon athletica inc. - Common",
        "asset_type": "ST",
        "transaction_type": "sale",
        "owner": "joint",
        "transaction_date": "2024-04-02",
        "notification_date": "2024-05-06",
        "amount_range_low": 15001,
        "amount_range_high": 50000,
        "description": None,
        "cap_gains_over_200": None,
    },
]

EXPECTED_20033928 = [
    {
        "ticker": None,
        "asset_description": "Aalo Atomics",
        "asset_type": "OI",
        "transaction_type": "purchase",
        "owner": "self",
        "transaction_date": "2026-01-29",
        "notification_date": "2026-01-29",
        "amount_range_low": 15001,
        "amount_range_high": 50000,
        "description": "Nuclear Power, Austin, TX",
        "cap_gains_over_200": None,
    },
    {
        "ticker": None,
        "asset_description": "CogniChip, Inc.",
        "asset_type": "OI",
        "transaction_type": "purchase",
        "owner": "self",
        "transaction_date": "2026-01-20",
        "notification_date": "2026-01-27",
        "amount_range_low": 15001,
        "amount_range_high": 50000,
        "description": "AI Chip Design, Redwood City, CA",
        "cap_gains_over_200": None,
    },
    {
        "ticker": None,
        "asset_description": "Modak Communities Inc.",
        "asset_type": "OI",
        "transaction_type": "purchase",
        "owner": "self",
        "transaction_date": "2026-01-20",
        "notification_date": "2026-01-27",
        "amount_range_low": 15001,
        "amount_range_high": 50000,
        "description": "Financial Technology, Menlo Park, CA",
        "cap_gains_over_200": None,
    },
    {
        "ticker": None,
        "asset_description": "Sygaldry Technologies, Inc.",
        "asset_type": "OI",
        "transaction_type": "purchase",
        "owner": "self",
        "transaction_date": "2026-01-29",
        "notification_date": "2026-01-29",
        "amount_range_low": 15001,
        "amount_range_high": 50000,
        "description": "Computer Servers, Santa Monica, CA",
        "cap_gains_over_200": None,
    },
    {
        "ticker": None,
        "asset_description": "Varda Space Industries, Inc.",
        "asset_type": "OI",
        "transaction_type": "purchase",
        "owner": "self",
        "transaction_date": "2026-01-20",
        "notification_date": "2026-01-27",
        "amount_range_low": 15001,
        "amount_range_high": 50000,
        "description": "Microgravity Manufacturing, El Segundo, CA",
        "cap_gains_over_200": None,
    },
]


# ---------------------------------------------------------------------------
# Parametrized golden tests
# ---------------------------------------------------------------------------

GOLDEN_CASES = [
    ("20024277.txt", 2024, EXPECTED_20024277),
    ("20024800.txt", 2024, EXPECTED_20024800),
    ("20024901.txt", 2024, EXPECTED_20024901),
    ("20025000.txt", 2024, EXPECTED_20025000),
    ("20033928.txt", 2026, EXPECTED_20033928),
]


@pytest.mark.parametrize("fixture,year,expected", GOLDEN_CASES, ids=[c[0] for c in GOLDEN_CASES])
class TestGoldenValidation:
    """Compare parser output against hand-verified expected data."""

    def test_trade_count(self, fixture, year, expected):
        trades = parse_ptr_text(_read_fixture(fixture), filing_year=year)
        assert len(trades) == len(expected), (
            f"Expected {len(expected)} trades, got {len(trades)}"
        )

    def test_all_fields_match(self, fixture, year, expected):
        trades = parse_ptr_text(_read_fixture(fixture), filing_year=year)
        for i, (actual, exp) in enumerate(zip(trades, expected)):
            for key in exp:
                assert actual[key] == exp[key], (
                    f"Trade {i} field '{key}': expected {exp[key]!r}, got {actual[key]!r}"
                )

    def test_no_extra_fields(self, fixture, year, expected):
        """Ensure parser doesn't introduce unexpected fields."""
        trades = parse_ptr_text(_read_fixture(fixture), filing_year=year)
        expected_keys = set(expected[0].keys()) if expected else set()
        for i, trade in enumerate(trades):
            assert set(trade.keys()) == expected_keys, (
                f"Trade {i} has unexpected keys: {set(trade.keys()) - expected_keys}"
            )
