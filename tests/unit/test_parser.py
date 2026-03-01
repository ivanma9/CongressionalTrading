"""Tests for the PTR PDF text parser using real PDF text fixtures."""

from pathlib import Path

from congressional_trading.parser import parse_ptr_text

FIXTURES = Path(__file__).parent.parent / 'fixtures'


def _load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


# ---------------------------------------------------------------------------
# 20024277 — Richard Allen, GA12 — 4 transactions, all SP-owned
# ---------------------------------------------------------------------------

class TestAllenFiling:
    """Richard Allen filing with 4 spouse-owned trades."""

    def setup_method(self):
        self.trades = parse_ptr_text(_load_fixture('20024277.txt'))

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
        self.trades = parse_ptr_text(_load_fixture('20024901.txt'))

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
        self.trades = parse_ptr_text(_load_fixture('20024800.txt'))

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
        self.trades = parse_ptr_text(_load_fixture('20025000.txt'))

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
        text = (
            'ID         Owner Asset                                            '
            'Transaction Date                 Notification Amount\n'
            '                                                                  '
            'Type                             Date\n'
            '                                                                  '
            '\n'
            '* For the complete list\n'
        )
        assert parse_ptr_text(text) == []

    def test_missing_ticker(self):
        """Transaction with no ticker should still parse with ticker=None."""
        text = (
            'ID         Owner Asset                                            '
            'Transaction Date                 Notification Amount\n'
            '                                                                  '
            'Type                             Date\n'
            '                                                                  '
            '\n'
            '                       Some Municipal Bond [OT]                   '
            'P                 01/15/2024 02/01/2024             $1,001 - $15,000\n'
            '\n'
            '* For the complete list\n'
        )
        trades = parse_ptr_text(text)
        assert len(trades) == 1
        assert trades[0]['ticker'] is None
        assert trades[0]['asset_type'] == 'OT'
        assert trades[0]['transaction_type'] == 'purchase'

    def test_amount_range_parsing(self):
        """Various amount range formats."""
        text = (
            'ID         Owner Asset                                            '
            'Transaction Date                 Notification Amount\n'
            '                                                                  '
            'Type                             Date\n'
            '                                                                  '
            '\n'
            '                       Test Corp (TST) [ST]                       '
            'P                 01/15/2024 02/01/2024             $1,001 - $15,000\n'
            '\n'
            '* For the complete list\n'
        )
        trades = parse_ptr_text(text)
        assert len(trades) == 1
        assert trades[0]['amount_range_low'] == 1_001
        assert trades[0]['amount_range_high'] == 15_000
