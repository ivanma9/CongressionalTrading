"""Tests for the PTR PDF text parser using real PDF text fixtures."""

import logging
from pathlib import Path

from congressional_trading.parser import parse_ptr_text

FIXTURES = Path(__file__).parent.parent / 'fixtures'

# Helper to build synthetic PTR text for edge case tests
_HEADER = (
    'ID         Owner Asset                                            '
    'Transaction Date                 Notification Amount\n'
    '                                                                  '
    'Type                             Date\n'
    '                                                                  '
    '\n'
)


def _make_ptr(body: str) -> str:
    """Wrap transaction body lines in a valid PTR text structure."""
    return _HEADER + body + '\n\n* For the complete list\n'


def _load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


# ---------------------------------------------------------------------------
# 20024277 — Richard Allen, GA12 — 4 transactions, all SP-owned
# ---------------------------------------------------------------------------

class TestAllenFiling:
    """Richard Allen filing with 4 spouse-owned trades."""

    def setup_method(self):
        self.trades = parse_ptr_text(_load_fixture('20024277.txt'), filing_year=2024)

    def test_trade_count(self):
        assert len(self.trades) == 4

    def test_first_alb_sale(self):
        t = self.trades[0]
        assert t['ticker'] == 'ALB'
        assert t['asset_type'] == 'ST'
        assert t['transaction_type'] == 'sale'
        assert t['owner'] == 'spouse'
        assert t['transaction_date'] == '2023-12-21'
        assert t['notification_date'] == '2024-01-08'
        assert t['amount_range_low'] == 1_001
        assert t['amount_range_high'] == 15_000

    def test_second_alb_sale(self):
        t = self.trades[1]
        assert t['ticker'] == 'ALB'
        assert t['transaction_type'] == 'sale'
        assert t['owner'] == 'spouse'

    def test_schwab_purchase(self):
        t = self.trades[2]
        assert t['ticker'] == 'SCHW'
        assert t['asset_type'] == 'ST'
        assert t['transaction_type'] == 'purchase'
        assert t['owner'] == 'spouse'
        assert t['transaction_date'] == '2023-12-14'
        assert t['notification_date'] == '2024-01-08'
        assert t['amount_range_low'] == 50_001
        assert t['amount_range_high'] == 100_000

    def test_nee_sale(self):
        t = self.trades[3]
        assert t['ticker'] == 'NEE'
        assert t['asset_type'] == 'ST'
        assert t['transaction_type'] == 'sale'
        assert t['owner'] == 'spouse'
        assert t['amount_range_low'] == 15_001
        assert t['amount_range_high'] == 50_000

    def test_asset_description_present(self):
        assert 'Albemarle' in (self.trades[0]['asset_description'] or '')
        assert 'Schwab' in (self.trades[2]['asset_description'] or '')
        assert 'NextEra' in (self.trades[3]['asset_description'] or '')


# ---------------------------------------------------------------------------
# 20024901 — Robert Latta, OH05 — 1 transaction, SP-owned, with description
# ---------------------------------------------------------------------------

class TestLattaFiling:
    """Robert Latta filing with 1 spouse-owned trade and description."""

    def setup_method(self):
        self.trades = parse_ptr_text(_load_fixture('20024901.txt'), filing_year=2024)

    def test_trade_count(self):
        assert len(self.trades) == 1

    def test_fmao_purchase(self):
        t = self.trades[0]
        assert t['ticker'] == 'FMAO'
        assert t['asset_type'] == 'ST'
        assert t['transaction_type'] == 'purchase'
        assert t['owner'] == 'spouse'
        assert t['transaction_date'] == '2024-04-20'
        assert t['notification_date'] == '2024-04-20'
        assert t['amount_range_low'] == 1_001
        assert t['amount_range_high'] == 15_000

    def test_description(self):
        t = self.trades[0]
        assert t['description'] is not None
        assert 'dividend reinvestment' in t['description'].lower()


# ---------------------------------------------------------------------------
# 20024800 — Mark Green, TN07 — 1 transaction, self-owned, multi-line asset
# ---------------------------------------------------------------------------

class TestGreenFiling:
    """Mark Green filing with 1 self-owned trade, multi-line asset name."""

    def setup_method(self):
        self.trades = parse_ptr_text(_load_fixture('20024800.txt'), filing_year=2024)

    def test_trade_count(self):
        assert len(self.trades) == 1

    def test_ngl_sale(self):
        t = self.trades[0]
        assert t['ticker'] == 'NGL'
        assert t['asset_type'] == 'ST'
        assert t['transaction_type'] == 'sale'
        assert t['owner'] == 'self'
        assert t['transaction_date'] == '2024-04-01'
        assert t['notification_date'] == '2024-04-04'
        assert t['amount_range_low'] == 100_001
        assert t['amount_range_high'] == 250_000

    def test_asset_description(self):
        t = self.trades[0]
        desc = t['asset_description']
        assert desc is not None
        assert 'NGL' in desc or 'ENERGY' in desc.upper()


# ---------------------------------------------------------------------------
# 20025000 — Jonathan Jackson, IL01 — 4 transactions, all JT-owned
# ---------------------------------------------------------------------------

class TestJacksonFiling:
    """Jonathan Jackson filing with 4 joint-owned trades."""

    def setup_method(self):
        self.trades = parse_ptr_text(_load_fixture('20025000.txt'), filing_year=2024)

    def test_trade_count(self):
        assert len(self.trades) == 4

    def test_cop_purchase(self):
        t = self.trades[0]
        assert t['ticker'] == 'COP'
        assert t['asset_type'] == 'ST'
        assert t['transaction_type'] == 'purchase'
        assert t['owner'] == 'joint'
        assert t['transaction_date'] == '2024-04-02'
        assert t['notification_date'] == '2024-05-06'
        assert t['amount_range_low'] == 15_001
        assert t['amount_range_high'] == 50_000

    def test_hxl_sale(self):
        t = self.trades[1]
        assert t['ticker'] == 'HXL'
        assert t['transaction_type'] == 'sale'
        assert t['owner'] == 'joint'

    def test_jpm_purchase(self):
        t = self.trades[2]
        assert t['ticker'] == 'JPM'
        assert t['transaction_type'] == 'purchase'
        assert t['owner'] == 'joint'

    def test_lulu_sale(self):
        t = self.trades[3]
        assert t['ticker'] == 'LULU'
        assert t['transaction_type'] == 'sale'
        assert t['owner'] == 'joint'
        assert t['transaction_date'] == '2024-04-02'


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases: empty text, no transactions, malformed data."""

    def test_empty_text(self):
        assert parse_ptr_text('') == []

    def test_no_transaction_section(self):
        text = 'Some random text\nwithout any transaction table'
        assert parse_ptr_text(text) == []

    def test_header_only(self):
        assert parse_ptr_text(_HEADER + '* For the complete list\n') == []

    def test_missing_ticker(self):
        """Transaction with no ticker should still parse with ticker=None."""
        text = _make_ptr(
            '                       Some Municipal Bond [OT]                   '
            'P                 01/15/2024 02/01/2024             $1,001 - $15,000'
        )
        trades = parse_ptr_text(text)
        assert len(trades) == 1
        assert trades[0]['ticker'] is None
        assert trades[0]['asset_type'] == 'OT'
        assert trades[0]['transaction_type'] == 'purchase'

    def test_amount_range_parsing(self):
        text = _make_ptr(
            '                       Test Corp (TST) [ST]                       '
            'P                 01/15/2024 02/01/2024             $1,001 - $15,000'
        )
        trades = parse_ptr_text(text)
        assert len(trades) == 1
        assert trades[0]['amount_range_low'] == 1_001
        assert trades[0]['amount_range_high'] == 15_000


# ---------------------------------------------------------------------------
# "Over $X" amount pattern
# ---------------------------------------------------------------------------

class TestOverAmount:
    """Over $50,000,000 → (50_000_001, None)."""

    def test_over_50m(self):
        text = _make_ptr(
            '                       Big Corp (BIG) [ST]                        '
            'P                 01/15/2024 02/01/2024         Over $50,000,000'
        )
        trades = parse_ptr_text(text)
        assert len(trades) == 1
        assert trades[0]['amount_range_low'] == 50_000_001
        assert trades[0]['amount_range_high'] is None

    def test_over_1m(self):
        text = _make_ptr(
            '                       Mid Corp (MID) [ST]                        '
            'S                 03/10/2024 04/01/2024         Over $1,000,000'
        )
        trades = parse_ptr_text(text)
        assert len(trades) == 1
        assert trades[0]['amount_range_low'] == 1_000_001
        assert trades[0]['amount_range_high'] is None


# ---------------------------------------------------------------------------
# Cap gains > $200k
# ---------------------------------------------------------------------------

class TestCapGains:
    """Capital gains > $200k field extraction."""

    def test_cap_gains_yes(self):
        text = _make_ptr(
            '                       Gain Corp (GAIN) [ST]                      '
            'S                 01/15/2024 02/01/2024             $1,001 - $15,000        Yes'
        )
        trades = parse_ptr_text(text)
        assert len(trades) == 1
        assert trades[0]['cap_gains_over_200'] is True

    def test_cap_gains_no(self):
        text = _make_ptr(
            '                       Loss Corp (LOSS) [ST]                      '
            'S                 01/15/2024 02/01/2024             $1,001 - $15,000         No'
        )
        trades = parse_ptr_text(text)
        assert len(trades) == 1
        assert trades[0]['cap_gains_over_200'] is False

    def test_cap_gains_absent(self):
        text = _make_ptr(
            '                       None Corp (NONE) [ST]                      '
            'P                 01/15/2024 02/01/2024             $1,001 - $15,000'
        )
        trades = parse_ptr_text(text)
        assert len(trades) == 1
        assert trades[0]['cap_gains_over_200'] is None


# ---------------------------------------------------------------------------
# Date validation
# ---------------------------------------------------------------------------

class TestDateValidation:
    """Date ordering warnings and invalid dates."""

    def test_date_order_warning(self, caplog):
        """transaction_date > notification_date logs a warning."""
        text = _make_ptr(
            '                       Late Corp (LATE) [ST]                      '
            'P                 06/15/2024 01/01/2024             $1,001 - $15,000'
        )
        with caplog.at_level(logging.WARNING, logger='congressional_trading.parser.ptr_parser'):
            trades = parse_ptr_text(text)
        assert len(trades) == 1
        assert trades[0]['transaction_date'] == '2024-06-15'
        assert trades[0]['notification_date'] == '2024-01-01'
        assert any('after notification date' in r.message for r in caplog.records)

    def test_valid_date_order_no_warning(self, caplog):
        """Normal date ordering produces no warning."""
        text = _make_ptr(
            '                       Good Corp (GOOD) [ST]                      '
            'P                 01/15/2024 02/01/2024             $1,001 - $15,000'
        )
        with caplog.at_level(logging.WARNING, logger='congressional_trading.parser.ptr_parser'):
            trades = parse_ptr_text(text)
        assert len(trades) == 1
        date_warnings = [r for r in caplog.records if 'after notification date' in r.message]
        assert len(date_warnings) == 0

    def test_invalid_date_returns_none(self, caplog):
        """Malformed date string returns None and logs warning."""
        text = _make_ptr(
            '                       Bad Corp (BAD) [ST]                        '
            'P                 13/45/2024 02/01/2024             $1,001 - $15,000'
        )
        with caplog.at_level(logging.WARNING, logger='congressional_trading.parser.ptr_parser'):
            trades = parse_ptr_text(text)
        assert len(trades) == 1
        assert trades[0]['transaction_date'] is None
        assert any('Invalid date' in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Amount bracket validation
# ---------------------------------------------------------------------------

class TestAmountBracketValidation:
    """Unknown amount brackets log a warning."""

    def test_unknown_bracket_warning(self, caplog):
        """Non-standard amount range logs a warning."""
        text = _make_ptr(
            '                       Weird Corp (WRD) [ST]                      '
            'P                 01/15/2024 02/01/2024             $5,000 - $10,000'
        )
        with caplog.at_level(logging.WARNING, logger='congressional_trading.parser.ptr_parser'):
            trades = parse_ptr_text(text)
        assert len(trades) == 1
        assert trades[0]['amount_range_low'] == 5_000
        assert trades[0]['amount_range_high'] == 10_000
        assert any('Unknown amount bracket' in r.message for r in caplog.records)

    def test_known_bracket_no_warning(self, caplog):
        """Standard amount range produces no warning."""
        text = _make_ptr(
            '                       Normal Corp (NRM) [ST]                     '
            'P                 01/15/2024 02/01/2024             $1,001 - $15,000'
        )
        with caplog.at_level(logging.WARNING, logger='congressional_trading.parser.ptr_parser'):
            trades = parse_ptr_text(text)
        assert len(trades) == 1
        bracket_warnings = [r for r in caplog.records if 'Unknown amount bracket' in r.message]
        assert len(bracket_warnings) == 0


# ---------------------------------------------------------------------------
# Form-feed / multi-page handling
# ---------------------------------------------------------------------------

class TestMultiPage:
    """Multi-page PDFs with form-feed characters."""

    def test_form_feed_stripped(self):
        """Form-feed characters don't break parsing."""
        fixture = _load_fixture('20024277.txt')
        # Inject a form-feed in the middle of the transactions section
        lines = fixture.split('\n')
        mid = len(lines) // 2
        lines.insert(mid, '\x0c')
        text_with_ff = '\n'.join(lines)
        trades = parse_ptr_text(text_with_ff, filing_year=2024)
        # Should still parse the same number of trades
        assert len(trades) == 4

    def test_form_feed_between_transactions(self):
        """Form-feed between transactions is stripped and both parse."""
        text = _make_ptr(
            '                       Page One Corp (PGON) [ST]                  '
            'P                 01/15/2024 02/01/2024             $1,001 - $15,000\n'
            '\n\x0c\n'
            '                       Page Two Corp (PGTW) [ST]                  '
            'S                 03/10/2024 04/01/2024             $15,001 - $50,000'
        )
        trades = parse_ptr_text(text)
        assert len(trades) == 2
        assert trades[0]['ticker'] == 'PGON'
        assert trades[1]['ticker'] == 'PGTW'


# ---------------------------------------------------------------------------
# S (partial) transaction type
# ---------------------------------------------------------------------------

class TestPartialSale:
    """S (partial) transaction type."""

    def test_sale_partial(self):
        text = _make_ptr(
            '                       Partial Corp (PRT) [ST]                    '
            'S (partial)       01/15/2024 02/01/2024             $1,001 - $15,000'
        )
        trades = parse_ptr_text(text)
        assert len(trades) == 1
        assert trades[0]['transaction_type'] == 'sale_partial'


# ---------------------------------------------------------------------------
# Date range validation
# ---------------------------------------------------------------------------

class TestDateRangeValidation:
    """Date range guardrails reject impossible dates."""

    def test_future_date_rejected(self, caplog):
        """Year 3031 with filing_year=2020 → date becomes None."""
        text = _make_ptr(
            '                       Future Corp (FUT) [ST]                     '
            'P                 01/15/3031 02/01/3031             $1,001 - $15,000'
        )
        with caplog.at_level(logging.WARNING, logger='congressional_trading.parser.ptr_parser'):
            trades = parse_ptr_text(text, filing_year=2020)
        assert len(trades) == 1
        assert trades[0]['transaction_date'] is None
        assert trades[0]['notification_date'] is None
        assert any('in the future' in r.message for r in caplog.records)

    def test_valid_date_passes(self):
        """Normal 2020 date with filing_year=2020 passes through."""
        text = _make_ptr(
            '                       Valid Corp (VLD) [ST]                      '
            'P                 06/15/2020 07/01/2020             $1,001 - $15,000'
        )
        trades = parse_ptr_text(text, filing_year=2020)
        assert len(trades) == 1
        assert trades[0]['transaction_date'] == '2020-06-15'
        assert trades[0]['notification_date'] == '2020-07-01'

    def test_one_year_before_filing_passes(self):
        """Date 1 year before filing year is valid (late filing)."""
        text = _make_ptr(
            '                       Late Corp (LTE) [ST]                       '
            'P                 11/15/2019 12/01/2019             $1,001 - $15,000'
        )
        trades = parse_ptr_text(text, filing_year=2020)
        assert len(trades) == 1
        assert trades[0]['transaction_date'] == '2019-11-15'

    def test_five_years_before_filing_rejected(self, caplog):
        """Date 5 years before filing year → rejected."""
        text = _make_ptr(
            '                       Old Corp (OLD) [ST]                        '
            'P                 01/15/2015 02/01/2015             $1,001 - $15,000'
        )
        with caplog.at_level(logging.WARNING, logger='congressional_trading.parser.ptr_parser'):
            trades = parse_ptr_text(text, filing_year=2020)
        assert len(trades) == 1
        assert trades[0]['transaction_date'] is None
        assert any('>2 years before filing year' in r.message for r in caplog.records)

    def test_pre_stock_act_rejected(self, caplog):
        """Year before 2008 → rejected."""
        text = _make_ptr(
            '                       Ancient Corp (ANC) [ST]                    '
            'P                 01/15/2005 02/01/2005             $1,001 - $15,000'
        )
        with caplog.at_level(logging.WARNING, logger='congressional_trading.parser.ptr_parser'):
            trades = parse_ptr_text(text, filing_year=2005)
        assert len(trades) == 1
        assert trades[0]['transaction_date'] is None
        assert any('before STOCK Act' in r.message for r in caplog.records)
