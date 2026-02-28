"""Tests for the get_insider_trades MCP tool."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from thesma_mcp.tools.insider_trades import get_insider_trades


def _make_ctx(
    client_responses: list[dict[str, Any]] | None = None,
    single_response: dict[str, Any] | None = None,
) -> MagicMock:
    """Create a mock MCP context."""
    mock_client = AsyncMock()
    if client_responses:
        mock_client.get = AsyncMock(side_effect=client_responses)
    else:
        mock_client.get = AsyncMock(return_value=single_response or {})

    mock_resolver = AsyncMock()
    mock_resolver.resolve = AsyncMock(return_value="0000320193")

    app = MagicMock()
    app.client = mock_client
    app.resolver = mock_resolver

    ctx = MagicMock()
    ctx.request_context.lifespan_context = app
    return ctx


def _trades_response(
    trades: list[dict[str, Any]] | None = None,
    total: int | None = None,
) -> dict[str, Any]:
    """Build a sample insider trades API response."""
    if trades is None:
        trades = [
            {
                "transaction_date": "2024-04-01",
                "owner_name": "Jeffrey E. Williams",
                "title": "COO",
                "shares": 100000,
                "price_per_share": 171.48,
                "total_value": 17148000,
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "is_10b5_1": False,
            },
            {
                "transaction_date": "2024-03-15",
                "owner_name": "Luca Maestri",
                "title": "SVP, CFO",
                "shares": 50000,
                "price_per_share": 173.22,
                "total_value": 8661000,
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "is_10b5_1": True,
            },
        ]
    if total is None:
        total = len(trades)
    return {
        "data": trades,
        "pagination": {"page": 1, "per_page": 20, "total": total},
    }


def _company_response(cik: str = "0000320193", ticker: str = "AAPL", name: str = "Apple Inc.") -> dict[str, Any]:
    return {"data": {"cik": cik, "ticker": ticker, "name": name}}


@pytest.mark.asyncio
async def test_trades_with_ticker() -> None:
    """get_insider_trades with ticker scopes to company endpoint."""
    ctx = _make_ctx(
        client_responses=[
            _company_response(),
            _trades_response(),
        ]
    )
    result = await get_insider_trades(ctx, ticker="AAPL")

    assert "Apple Inc. (AAPL)" in result
    ctx.request_context.lifespan_context.resolver.resolve.assert_called_once_with("AAPL")
    calls = ctx.request_context.lifespan_context.client.get.call_args_list
    assert any("/v1/us/sec/companies/0000320193/insider-trades" in str(c) for c in calls)


@pytest.mark.asyncio
async def test_trades_without_ticker() -> None:
    """get_insider_trades without ticker uses all-trades endpoint."""
    ctx = _make_ctx(single_response=_trades_response())
    await get_insider_trades(ctx)

    calls = ctx.request_context.lifespan_context.client.get.call_args_list
    assert calls[0][0][0] == "/v1/us/sec/insider-trades"


@pytest.mark.asyncio
async def test_trades_empty_ticker() -> None:
    """get_insider_trades with empty string ticker uses all-trades endpoint."""
    ctx = _make_ctx(single_response=_trades_response())
    await get_insider_trades(ctx, ticker="")

    calls = ctx.request_context.lifespan_context.client.get.call_args_list
    assert calls[0][0][0] == "/v1/us/sec/insider-trades"


@pytest.mark.asyncio
async def test_trades_type_filter() -> None:
    """get_insider_trades with type filter passes it to API."""
    ctx = _make_ctx(single_response=_trades_response())
    await get_insider_trades(ctx, type="purchase")

    call_args = ctx.request_context.lifespan_context.client.get.call_args
    params = call_args.kwargs.get("params", {})
    assert params.get("type") == "purchase"


@pytest.mark.asyncio
async def test_trades_invalid_type() -> None:
    """get_insider_trades with invalid type returns error listing valid types."""
    ctx = _make_ctx(single_response=_trades_response())
    result = await get_insider_trades(ctx, type="short_sell")

    assert "Invalid type 'short_sell'" in result
    assert "Valid types:" in result
    assert "purchase" in result
    assert "sale" in result
    ctx.request_context.lifespan_context.client.get.assert_not_called()


@pytest.mark.asyncio
async def test_trades_min_value() -> None:
    """get_insider_trades with min_value filter passes it to API."""
    ctx = _make_ctx(single_response=_trades_response())
    await get_insider_trades(ctx, min_value=1000000)

    call_args = ctx.request_context.lifespan_context.client.get.call_args
    params = call_args.kwargs.get("params", {})
    assert params.get("min_value") == 1000000


@pytest.mark.asyncio
async def test_trades_invalid_date() -> None:
    """get_insider_trades with invalid date format returns helpful error."""
    ctx = _make_ctx(single_response=_trades_response())
    result = await get_insider_trades(ctx, from_date="yesterday")

    assert "Invalid date format 'yesterday'" in result
    assert "YYYY-MM-DD" in result
    ctx.request_context.lifespan_context.client.get.assert_not_called()


@pytest.mark.asyncio
async def test_trades_company_scoped_shows_detail() -> None:
    """get_insider_trades company-scoped shows per-share detail."""
    ctx = _make_ctx(
        client_responses=[
            _company_response(),
            _trades_response(),
        ]
    )
    result = await get_insider_trades(ctx, ticker="AAPL")

    # Company-scoped table has Shares, Price, Value columns
    assert "Shares" in result
    assert "Price" in result
    assert "Value" in result
    assert "100,000" in result  # formatted shares
    assert "$171.48" in result  # formatted price


@pytest.mark.asyncio
async def test_trades_all_companies_shows_value_and_planned() -> None:
    """get_insider_trades all-companies shows total value and planned flag."""
    ctx = _make_ctx(single_response=_trades_response())
    result = await get_insider_trades(ctx)

    # All-companies table has Value and Planned? columns
    assert "Planned?" in result
    assert "Yes" in result  # Luca's trade is_10b5_1=True
    assert "No" in result  # Jeff's trade is_10b5_1=False


@pytest.mark.asyncio
async def test_trades_formats_currency() -> None:
    """get_insider_trades formats currency and share counts correctly."""
    ctx = _make_ctx(
        client_responses=[
            _company_response(),
            _trades_response(),
        ]
    )
    result = await get_insider_trades(ctx, ticker="AAPL")

    # $17.1M for 17148000
    assert "$17.1M" in result
    assert "100,000" in result


@pytest.mark.asyncio
async def test_trades_no_results() -> None:
    """get_insider_trades with no results returns helpful message."""
    ctx = _make_ctx(single_response=_trades_response(trades=[], total=0))
    result = await get_insider_trades(ctx, type="grant")

    assert "No insider trades found" in result
