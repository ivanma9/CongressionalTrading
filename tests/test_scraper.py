"""Tests for the scraper components."""

from congressional_trading.parser.xml_index import filter_ptrs, parse_xml_index


SAMPLE_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<FinancialDisclosure>
  <Member>
    <Prefix>Hon.</Prefix>
    <Last>Pelosi</Last>
    <First>Nancy</First>
    <Suffix/>
    <FilingType>P</FilingType>
    <StateDst>CA11</StateDst>
    <Year>2025</Year>
    <FilingDate>01/17/2025</FilingDate>
    <DocID>20026590</DocID>
  </Member>
  <Member>
    <Prefix>Hon.</Prefix>
    <Last>Smith</Last>
    <First>John</First>
    <Suffix/>
    <FilingType>O</FilingType>
    <StateDst>TX05</StateDst>
    <Year>2025</Year>
    <FilingDate>02/01/2025</FilingDate>
    <DocID>20026600</DocID>
  </Member>
  <Member>
    <Prefix>Hon.</Prefix>
    <Last>Crenshaw</Last>
    <First>Dan</First>
    <Suffix/>
    <FilingType>P</FilingType>
    <StateDst>TX02</StateDst>
    <Year>2025</Year>
    <FilingDate>01/18/2025</FilingDate>
    <DocID>20026591</DocID>
  </Member>
</FinancialDisclosure>
"""


class TestXmlParsing:
    def test_parse_all_filings(self):
        filings = parse_xml_index(SAMPLE_XML)
        assert len(filings) == 3

    def test_filing_fields(self):
        filings = parse_xml_index(SAMPLE_XML)
        pelosi = [f for f in filings if f["last"] == "Pelosi"][0]
        assert pelosi["doc_id"] == "20026590"
        assert pelosi["first"] == "Nancy"
        assert pelosi["prefix"] == "Hon."
        assert pelosi["state_district"] == "CA11"
        assert pelosi["filing_year"] == 2025
        assert pelosi["filing_date"] == "2025-01-17"
        assert pelosi["filing_type"] == "P"

    def test_filter_ptrs(self):
        filings = parse_xml_index(SAMPLE_XML)
        ptrs = filter_ptrs(filings)
        assert len(ptrs) == 2
        assert all(f["filing_type"] == "P" for f in ptrs)
        names = {f["last"] for f in ptrs}
        assert names == {"Pelosi", "Crenshaw"}


class TestDocIdValidation:
    def test_valid_doc_id(self):
        import re
        pattern = re.compile(r"^[0-9]+$")
        assert pattern.match("20026590")
        assert not pattern.match("../../etc/passwd")
        assert not pattern.match("abc123")
