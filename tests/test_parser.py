"""Tests for the PTR PDF parser using real fixture text files."""

from pathlib import Path

from congressional_trading.parser.ptr_parser import parse_ptr_text

FIXTURES = Path(__file__).parent / "fixtures"


def _read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


class TestParserAllen20024277:
    """Test parsing of Richard Allen's PTR filing (4 trades)."""

    def setup_method(self):
        self.trades = parse_ptr_text(_read_fixture("20024277.txt"))

    def test_trade_count(self):
        assert len(self.trades) == 4

    def test_first_trade_ticker(self):
        assert self.trades[0]["ticker"] == "ALB"

    def test_first_trade_type(self):
        assert self.trades[0]["transaction_type"] == "sale"

    def test_first_trade_owner(self):
        assert self.trades[0]["owner"] == "spouse"

    def test_first_trade_date(self):
        assert self.trades[0]["transaction_date"] == "2023-12-21"

    def test_first_trade_notification_date(self):
        assert self.trades[0]["notification_date"] == "2024-01-08"

    def test_first_trade_amount(self):
        assert self.trades[0]["amount_range_low"] == 1001
        assert self.trades[0]["amount_range_high"] == 15000

    def test_schwab_purchase(self):
        schwab = [t for t in self.trades if t["ticker"] == "SCHW"]
        assert len(schwab) == 1
        assert schwab[0]["transaction_type"] == "purchase"
        assert schwab[0]["amount_range_low"] == 50001
        assert schwab[0]["amount_range_high"] == 100000

    def test_nee_sale(self):
        nee = [t for t in self.trades if t["ticker"] == "NEE"]
        assert len(nee) == 1
        assert nee[0]["transaction_type"] == "sale"
        assert nee[0]["amount_range_low"] == 15001

    def test_asset_description(self):
        assert "Albemarle" in self.trades[0]["asset_description"]


class TestParserGreen20024800:
    """Test parsing of Mark Green's PTR filing (1 trade)."""

    def setup_method(self):
        self.trades = parse_ptr_text(_read_fixture("20024800.txt"))

    def test_trade_count(self):
        assert len(self.trades) == 1

    def test_ticker(self):
        assert self.trades[0]["ticker"] == "NGL"

    def test_transaction_type(self):
        assert self.trades[0]["transaction_type"] == "sale"

    def test_amount(self):
        assert self.trades[0]["amount_range_low"] == 100001
        assert self.trades[0]["amount_range_high"] == 250000

    def test_date(self):
        assert self.trades[0]["transaction_date"] == "2024-04-01"

    def test_notification_date(self):
        assert self.trades[0]["notification_date"] == "2024-04-04"

    def test_asset_description(self):
        desc = self.trades[0]["asset_description"]
        assert "NGL" in desc or "ENERGY" in desc.upper()


class TestParserLatta20024901:
    """Test parsing of Robert Latta's PTR filing (1 trade with description)."""

    def setup_method(self):
        self.trades = parse_ptr_text(_read_fixture("20024901.txt"))

    def test_trade_count(self):
        assert len(self.trades) == 1

    def test_ticker(self):
        assert self.trades[0]["ticker"] == "FMAO"

    def test_transaction_type(self):
        assert self.trades[0]["transaction_type"] == "purchase"

    def test_owner(self):
        assert self.trades[0]["owner"] == "spouse"

    def test_description(self):
        assert self.trades[0]["description"] is not None
        assert "dividend" in self.trades[0]["description"].lower()

    def test_amount(self):
        assert self.trades[0]["amount_range_low"] == 1001
        assert self.trades[0]["amount_range_high"] == 15000


class TestParserJackson20025000:
    """Test parsing of Jonathan Jackson's PTR filing (4 trades, joint owner)."""

    def setup_method(self):
        self.trades = parse_ptr_text(_read_fixture("20025000.txt"))

    def test_trade_count(self):
        assert len(self.trades) == 4

    def test_all_joint_owner(self):
        for t in self.trades:
            assert t["owner"] == "joint"

    def test_cop_purchase(self):
        cop = [t for t in self.trades if t["ticker"] == "COP"]
        assert len(cop) == 1
        assert cop[0]["transaction_type"] == "purchase"
        assert cop[0]["transaction_date"] == "2024-04-02"

    def test_hxl_sale(self):
        hxl = [t for t in self.trades if t["ticker"] == "HXL"]
        assert len(hxl) == 1
        assert hxl[0]["transaction_type"] == "sale"

    def test_jpm_purchase(self):
        jpm = [t for t in self.trades if t["ticker"] == "JPM"]
        assert len(jpm) == 1
        assert jpm[0]["transaction_type"] == "purchase"

    def test_lulu_sale(self):
        lulu = [t for t in self.trades if t["ticker"] == "LULU"]
        assert len(lulu) == 1
        assert lulu[0]["transaction_type"] == "sale"

    def test_amounts(self):
        for t in self.trades:
            assert t["amount_range_low"] == 15001
            assert t["amount_range_high"] == 50000


class TestParserEdgeCases:
    """Test edge cases in parsing."""

    def test_empty_text(self):
        assert parse_ptr_text("") == []

    def test_no_transactions_section(self):
        assert parse_ptr_text("Some random text\nwithout transactions") == []

    def test_iso_date_format(self):
        """Verify dates are converted to ISO format."""
        trades = parse_ptr_text(_read_fixture("20024277.txt"))
        for t in trades:
            if t["transaction_date"]:
                assert len(t["transaction_date"]) == 10
                assert t["transaction_date"][4] == "-"
                assert t["transaction_date"][7] == "-"
