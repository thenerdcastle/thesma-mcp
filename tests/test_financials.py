"""Tests for financial statement tools."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from thesma_mcp.tools.financials import get_financial_metric, get_financials


@pytest.fixture()
def mock_ctx() -> MagicMock:
    """Create a mock Context with AppContext."""
    ctx = MagicMock()
    app = MagicMock()
    app.client = AsyncMock()
    app.resolver = AsyncMock(return_value="0000320193")
    app.resolver.resolve = AsyncMock(return_value="0000320193")
    ctx.request_context.lifespan_context = app
    return ctx


def _app(ctx: MagicMock) -> Any:
    return ctx.request_context.lifespan_context


SAMPLE_INCOME = {
    "data": {
        "company_name": "Apple Inc.",
        "ticker": "AAPL",
        "fiscal_year": 2024,
        "filing_type": "10-K",
        "accession_number": "0000320193-24-000123",
        "data_source": "ixbrl",
        "revenue": 391_035_000_000,
        "cost_of_revenue": 210_400_000_000,
        "gross_profit": 180_635_000_000,
        "operating_expenses": 57_500_000_000,
        "research_and_development": 29_900_000_000,
        "selling_general_admin": 27_600_000_000,
        "operating_income": 123_135_000_000,
        "interest_expense": 3_500_000_000,
        "pre_tax_income": 123_500_000_000,
        "income_tax_expense": 29_700_000_000,
        "net_income": 93_736_000_000,
        "eps_diluted": 6.08,
    }
}

SAMPLE_BALANCE_SHEET = {
    "data": {
        "company_name": "Apple Inc.",
        "ticker": "AAPL",
        "fiscal_year": 2024,
        "filing_type": "10-K",
        "accession_number": "0000320193-24-000123",
        "data_source": "ixbrl",
        "total_assets": 352_583_000_000,
        "current_assets": 133_293_000_000,
        "cash_and_equivalents": 29_943_000_000,
        "total_liabilities": 290_437_000_000,
        "total_equity": 62_146_000_000,
        "inventory": None,  # Apple doesn't report this
        "goodwill": None,
    }
}

SAMPLE_CASH_FLOW = {
    "data": {
        "company_name": "Apple Inc.",
        "ticker": "AAPL",
        "fiscal_year": 2024,
        "filing_type": "10-K",
        "accession_number": "0000320193-24-000123",
        "data_source": "ixbrl",
        "operating_cash_flow": 110_543_000_000,
        "investing_cash_flow": -7_077_000_000,
        "financing_cash_flow": -103_466_000_000,
        "capital_expenditures": -10_959_000_000,
        "dividends_paid": -15_025_000_000,
        "share_repurchases": -77_550_000_000,
        "net_change_in_cash": None,
    }
}


class TestGetFinancials:
    async def test_income_statement_with_margins(self, mock_ctx: MagicMock) -> None:
        """get_financials returns formatted income statement with margins."""
        _app(mock_ctx).client.get = AsyncMock(return_value=SAMPLE_INCOME)
        result = await get_financials("AAPL", mock_ctx)
        assert "Income Statement" in result
        assert "FY 2024" in result
        assert "$391.0B" in result  # revenue
        assert "$6.08" in result  # EPS
        assert "(46.2%)" in result  # gross margin shown inline
        assert "Currency: USD" in result

    async def test_balance_sheet_omits_null(self, mock_ctx: MagicMock) -> None:
        """get_financials for balance sheet omits null fields."""
        _app(mock_ctx).client.get = AsyncMock(return_value=SAMPLE_BALANCE_SHEET)
        result = await get_financials("AAPL", mock_ctx, statement="balance-sheet")
        assert "Balance Sheet" in result
        assert "Total Assets" in result
        assert "Inventory" not in result  # null, should be omitted
        assert "Goodwill" not in result  # null, should be omitted

    async def test_cash_flow(self, mock_ctx: MagicMock) -> None:
        """get_financials for cash flow formats correctly."""
        _app(mock_ctx).client.get = AsyncMock(return_value=SAMPLE_CASH_FLOW)
        result = await get_financials("AAPL", mock_ctx, statement="cash-flow")
        assert "Cash Flow" in result
        assert "Operating Cash Flow" in result
        assert "Net Change in Cash" not in result  # null

    async def test_quarterly_passes_quarter(self, mock_ctx: MagicMock) -> None:
        """get_financials with quarterly period passes quarter param."""
        app = _app(mock_ctx)
        app.client.get = AsyncMock(return_value=SAMPLE_INCOME)
        await get_financials("AAPL", mock_ctx, period="quarterly", quarter=2)
        call_params = app.client.get.call_args[1]["params"]
        assert call_params["period"] == "quarterly"
        assert call_params["quarter"] == 2

    async def test_quarterly_no_quarter_error(self, mock_ctx: MagicMock) -> None:
        """get_financials with quarterly period but no quarter returns helpful error."""
        result = await get_financials("AAPL", mock_ctx, period="quarterly")
        assert "Quarter (1-4) is required" in result

    async def test_annual_with_quarter_error(self, mock_ctx: MagicMock) -> None:
        """get_financials rejects quarter when period is annual."""
        result = await get_financials("AAPL", mock_ctx, period="annual", quarter=2)
        assert "Quarter should not be specified" in result

    async def test_no_data(self, mock_ctx: MagicMock) -> None:
        """get_financials for company with no financial data returns helpful message."""
        _app(mock_ctx).client.get = AsyncMock(return_value={"data": {}})
        result = await get_financials("AAPL", mock_ctx)
        assert "No financial data" in result

    async def test_includes_currency(self, mock_ctx: MagicMock) -> None:
        """get_financials includes currency in response."""
        _app(mock_ctx).client.get = AsyncMock(return_value=SAMPLE_INCOME)
        result = await get_financials("AAPL", mock_ctx)
        assert "Currency: USD" in result


class TestGetFinancialMetric:
    async def test_returns_time_series(self, mock_ctx: MagicMock) -> None:
        """get_financial_metric returns formatted time series."""
        _app(mock_ctx).client.get = AsyncMock(
            return_value={
                "data": [
                    {"company_name": "Apple Inc.", "ticker": "AAPL", "fiscal_year": 2024, "value": 391_035_000_000},
                    {"company_name": "Apple Inc.", "ticker": "AAPL", "fiscal_year": 2023, "value": 383_285_000_000},
                    {"company_name": "Apple Inc.", "ticker": "AAPL", "fiscal_year": 2022, "value": 394_328_000_000},
                ]
            }
        )
        result = await get_financial_metric("AAPL", "revenue", mock_ctx)
        assert "Revenue" in result
        assert "Annual" in result
        assert "$391.0B" in result
        assert "3 data points" in result

    async def test_date_range_params(self, mock_ctx: MagicMock) -> None:
        """get_financial_metric with date range passes from/to params."""
        app = _app(mock_ctx)
        app.client.get = AsyncMock(return_value={"data": [{"fiscal_year": 2023, "value": 100}]})
        await get_financial_metric("AAPL", "revenue", mock_ctx, from_year=2020, to_year=2023)
        call_params = app.client.get.call_args[1]["params"]
        assert call_params["from"] == 2020
        assert call_params["to"] == 2023

    async def test_no_data(self, mock_ctx: MagicMock) -> None:
        """get_financial_metric with no data returns helpful message."""
        _app(mock_ctx).client.get = AsyncMock(return_value={"data": []})
        result = await get_financial_metric("AAPL", "revenue", mock_ctx)
        assert "No data found" in result

    async def test_invalid_metric(self, mock_ctx: MagicMock) -> None:
        """get_financial_metric with invalid metric name returns helpful error."""
        result = await get_financial_metric("AAPL", "invalid_metric", mock_ctx)
        assert "Invalid metric" in result
        assert "revenue" in result  # should list valid metrics
