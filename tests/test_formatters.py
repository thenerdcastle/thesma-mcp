"""Tests for number and response formatting utilities."""

from __future__ import annotations

from thesma_mcp.formatters import (
    format_currency,
    format_number,
    format_pagination,
    format_percent,
    format_shares,
    format_source,
    format_table,
)


class TestFormatCurrency:
    def test_trillions(self) -> None:
        assert format_currency(1_500_000_000_000) == "$1.5T"

    def test_billions(self) -> None:
        assert format_currency(391_035_000_000) == "$391.0B"

    def test_millions(self) -> None:
        assert format_currency(17_148_000) == "$17.1M"

    def test_thousands(self) -> None:
        assert format_currency(5_500) == "$5.5K"

    def test_plain(self) -> None:
        assert format_currency(6.08) == "$6.1"

    def test_plain_exact(self) -> None:
        assert format_currency(6.08, decimals=2) == "$6.08"

    def test_none(self) -> None:
        assert format_currency(None) == "N/A"

    def test_negative(self) -> None:
        assert format_currency(-500_000_000) == "$-500.0M"


class TestFormatNumber:
    def test_large(self) -> None:
        assert format_number(100_000) == "100.0K"

    def test_billions(self) -> None:
        assert format_number(2_500_000_000) == "2.5B"

    def test_none(self) -> None:
        assert format_number(None) == "N/A"


class TestFormatPercent:
    def test_basic(self) -> None:
        assert format_percent(46.2) == "46.2%"

    def test_none(self) -> None:
        assert format_percent(None) == "N/A"

    def test_decimals(self) -> None:
        assert format_percent(46.25, decimals=2) == "46.25%"


class TestFormatShares:
    def test_basic(self) -> None:
        assert format_shares(100_000) == "100,000 shares"

    def test_none(self) -> None:
        assert format_shares(None) == "N/A"

    def test_large(self) -> None:
        assert format_shares(1_500_000) == "1,500,000 shares"


class TestFormatTable:
    def test_basic_table(self) -> None:
        result = format_table(
            headers=["Name", "Revenue", "Growth"],
            rows=[
                ["Apple", "$391.0B", "8.1%"],
                ["Microsoft", "$211.9B", "12.3%"],
            ],
            alignments=["l", "r", "r"],
        )
        lines = result.split("\n")
        assert len(lines) == 4  # header + separator + 2 data rows
        assert "Apple" in lines[2]
        assert "Microsoft" in lines[3]

    def test_empty_rows(self) -> None:
        assert format_table(["A", "B"], []) == ""

    def test_default_alignment(self) -> None:
        result = format_table(["Col1", "Col2"], [["a", "b"]])
        assert "Col1" in result


class TestFormatSource:
    def test_with_accession(self) -> None:
        result = format_source("10-K", accession="0000320193-24-000123", data_source="ixbrl")
        assert result == "Source: SEC EDGAR, 10-K filing 0000320193-24-000123 (iXBRL)"

    def test_without_accession(self) -> None:
        result = format_source("Form 4")
        assert result == "Source: SEC EDGAR, Form 4 filings."

    def test_with_accession_no_source(self) -> None:
        result = format_source("10-K", accession="0000320193-24-000123")
        assert result == "Source: SEC EDGAR, 10-K filing 0000320193-24-000123"


class TestFormatPagination:
    def test_all_shown(self) -> None:
        result = format_pagination(5, 5)
        assert result == "5 results found."

    def test_partial(self) -> None:
        result = format_pagination(25, 127)
        assert result == "Showing 1-25 of 127."

    def test_with_sort(self) -> None:
        result = format_pagination(5, 47, sort_description="revenue growth (descending)")
        assert "Showing 1-5 of 47" in result
        assert "sorted by revenue growth (descending)" in result

    def test_single_result(self) -> None:
        result = format_pagination(1, 1)
        assert result == "1 result found."
