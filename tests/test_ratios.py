"""Tests for financial ratio tools."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from thesma_mcp.tools.ratios import get_ratio_history, get_ratios


@pytest.fixture()
def mock_ctx() -> MagicMock:
    """Create a mock Context with AppContext."""
    ctx = MagicMock()
    app = MagicMock()
    app.client = AsyncMock()
    app.resolver = AsyncMock()
    app.resolver.resolve = AsyncMock(return_value="0000320193")
    ctx.request_context.lifespan_context = app
    return ctx


def _app(ctx: MagicMock) -> Any:
    return ctx.request_context.lifespan_context


SAMPLE_RATIOS = {
    "data": {
        "company_name": "Apple Inc.",
        "ticker": "AAPL",
        "fiscal_year": 2024,
        "gross_margin": 46.2,
        "operating_margin": 31.5,
        "net_margin": 24.0,
        "return_on_equity": 157.4,
        "return_on_assets": 30.3,
        "debt_to_equity": 4.56,
        "current_ratio": 0.99,
        "interest_coverage": 35.2,
        "revenue_growth_yoy": 2.0,
        "net_income_growth_yoy": -3.4,
        "eps_growth_yoy": -2.1,
    }
}


class TestGetRatios:
    async def test_grouped_by_category(self, mock_ctx: MagicMock) -> None:
        """get_ratios returns ratios grouped by category."""
        _app(mock_ctx).client.get = AsyncMock(return_value=SAMPLE_RATIOS)
        result = await get_ratios("AAPL", mock_ctx)
        assert "Profitability" in result
        assert "Returns" in result
        assert "Leverage" in result
        assert "Growth (YoY)" in result

    async def test_skips_null_ratios(self, mock_ctx: MagicMock) -> None:
        """get_ratios skips null ratios."""
        data = {
            "data": {
                "company_name": "Test Corp",
                "ticker": "TEST",
                "fiscal_year": 2024,
                "gross_margin": 40.0,
                "operating_margin": None,
                "net_margin": None,
                "return_on_equity": None,
                "return_on_assets": None,
                "debt_to_equity": None,
                "current_ratio": None,
                "interest_coverage": None,
                "revenue_growth_yoy": None,
                "net_income_growth_yoy": None,
                "eps_growth_yoy": None,
            }
        }
        _app(mock_ctx).client.get = AsyncMock(return_value=data)
        result = await get_ratios("TEST", mock_ctx)
        assert "Gross Margin" in result
        assert "Operating Margin" not in result
        # Categories with all nulls should not appear
        assert "Returns" not in result
        assert "Leverage" not in result

    async def test_percentage_and_multiplier_formatting(self, mock_ctx: MagicMock) -> None:
        """get_ratios formats percentages and leverage multipliers correctly."""
        _app(mock_ctx).client.get = AsyncMock(return_value=SAMPLE_RATIOS)
        result = await get_ratios("AAPL", mock_ctx)
        assert "46.2%" in result  # percentage
        assert "4.56x" in result  # multiplier
        assert "-3.4%" in result  # negative percentage

    async def test_quarterly_no_quarter_error(self, mock_ctx: MagicMock) -> None:
        """get_ratios with quarterly period but no quarter returns helpful error."""
        result = await get_ratios("AAPL", mock_ctx, period="quarterly")
        assert "Quarter (1-4) is required" in result

    async def test_annual_with_quarter_error(self, mock_ctx: MagicMock) -> None:
        """get_ratios rejects quarter when period is annual."""
        result = await get_ratios("AAPL", mock_ctx, period="annual", quarter=2)
        assert "Quarter should not be specified" in result

    async def test_no_data(self, mock_ctx: MagicMock) -> None:
        """get_ratios for company with no ratio data returns helpful message."""
        _app(mock_ctx).client.get = AsyncMock(return_value={"data": {}})
        result = await get_ratios("AAPL", mock_ctx)
        assert "No ratio data" in result


class TestGetRatioHistory:
    async def test_returns_time_series(self, mock_ctx: MagicMock) -> None:
        """get_ratio_history returns formatted time series."""
        _app(mock_ctx).client.get = AsyncMock(
            return_value={
                "data": [
                    {"company_name": "Apple Inc.", "ticker": "AAPL", "fiscal_year": 2024, "value": 46.2},
                    {"company_name": "Apple Inc.", "ticker": "AAPL", "fiscal_year": 2023, "value": 44.1},
                    {"company_name": "Apple Inc.", "ticker": "AAPL", "fiscal_year": 2022, "value": 43.3},
                ]
            }
        )
        result = await get_ratio_history("AAPL", "gross_margin", mock_ctx)
        assert "Gross Margin" in result
        assert "46.2%" in result
        assert "3 data points" in result

    async def test_date_range_params(self, mock_ctx: MagicMock) -> None:
        """get_ratio_history with date range passes from/to params."""
        app = _app(mock_ctx)
        app.client.get = AsyncMock(return_value={"data": [{"fiscal_year": 2023, "value": 40.0}]})
        await get_ratio_history("AAPL", "gross_margin", mock_ctx, from_year=2020, to_year=2023)
        call_params = app.client.get.call_args[1]["params"]
        assert call_params["from"] == 2020
        assert call_params["to"] == 2023

    async def test_invalid_ratio(self, mock_ctx: MagicMock) -> None:
        """get_ratio_history with invalid ratio name returns helpful error."""
        result = await get_ratio_history("AAPL", "invalid_ratio", mock_ctx)
        assert "Invalid ratio" in result
        assert "gross_margin" in result  # should list valid ratios
