"""Tests for SEC filing search tool."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from thesma_mcp.tools.filings import search_filings


def _make_ctx(
    resolve_cik: str = "0000320193",
    single_response: dict[str, Any] | None = None,
) -> MagicMock:
    ctx = MagicMock()
    app = MagicMock()
    app.resolver = AsyncMock()
    app.resolver.resolve = AsyncMock(return_value=resolve_cik)
    if single_response:
        app.client.get = AsyncMock(return_value=single_response)
    else:
        app.client.get = AsyncMock(return_value={"data": []})
    ctx.request_context.lifespan_context = app
    return ctx


SAMPLE_FILINGS = {
    "data": [
        {
            "company_name": "Apple Inc.",
            "ticker": "AAPL",
            "filed_date": "2024-11-01",
            "filing_type": "10-K",
            "period_of_report": "2024-09-28",
            "accession_number": "0000320193-24-000123",
        },
        {
            "company_name": "Apple Inc.",
            "ticker": "AAPL",
            "filed_date": "2024-08-02",
            "filing_type": "10-Q",
            "period_of_report": "2024-06-29",
            "accession_number": "0000320193-24-000089",
        },
    ],
    "pagination": {"page": 1, "per_page": 25, "total": 234},
}


class TestSearchFilings:
    async def test_with_ticker(self) -> None:
        """search_filings with ticker resolves and passes CIK."""
        ctx = _make_ctx(single_response=SAMPLE_FILINGS)
        result = await search_filings(ctx, ticker="AAPL")
        assert "Apple Inc. (AAPL)" in result
        assert "10-K" in result
        assert "0000320193-24-000123" in result
        # Verify CIK was passed
        call_params = ctx.request_context.lifespan_context.client.get.call_args[1]["params"]
        assert call_params["cik"] == "0000320193"

    async def test_without_ticker(self) -> None:
        """search_filings without ticker searches all filings."""
        ctx = _make_ctx(single_response=SAMPLE_FILINGS)
        result = await search_filings(ctx)
        assert "SEC Filings" in result
        # Should not have CIK in params
        call_params = ctx.request_context.lifespan_context.client.get.call_args[1]["params"]
        assert "cik" not in call_params

    async def test_type_filter(self) -> None:
        """search_filings with type filter passes to API."""
        ctx = _make_ctx(single_response=SAMPLE_FILINGS)
        await search_filings(ctx, type="10-K")
        call_params = ctx.request_context.lifespan_context.client.get.call_args[1]["params"]
        assert call_params["type"] == "10-K"

    async def test_date_range(self) -> None:
        """search_filings with date range passes from/to."""
        ctx = _make_ctx(single_response=SAMPLE_FILINGS)
        await search_filings(ctx, from_date="2024-01-01", to_date="2024-12-31")
        call_params = ctx.request_context.lifespan_context.client.get.call_args[1]["params"]
        assert call_params["from"] == "2024-01-01"
        assert call_params["to"] == "2024-12-31"

    async def test_formats_correctly(self) -> None:
        """search_filings formats dates and accession numbers correctly."""
        ctx = _make_ctx(single_response=SAMPLE_FILINGS)
        result = await search_filings(ctx, ticker="AAPL")
        assert "2024-11-01" in result
        assert "2024-09-28" in result
        assert "0000320193-24-000123" in result
        assert "Showing 2 of 234 filings" in result
        assert "Source: SEC EDGAR filing index." in result

    async def test_no_results(self) -> None:
        """search_filings with no results returns helpful message."""
        ctx = _make_ctx(single_response={"data": [], "pagination": {"page": 1, "per_page": 25, "total": 0}})
        result = await search_filings(ctx, ticker="AAPL")
        assert "No filings found" in result
