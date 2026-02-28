"""Tests for the get_events MCP tool."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from thesma_mcp.tools.events import get_events


def _make_ctx(
    client_responses: list[dict[str, Any]] | None = None,
    single_response: dict[str, Any] | None = None,
) -> MagicMock:
    """Create a mock MCP context.

    If single_response is given, all client.get calls return it.
    If client_responses is given, calls return them in sequence.
    """
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


def _events_response(
    events: list[dict[str, Any]] | None = None,
    total: int | None = None,
) -> dict[str, Any]:
    """Build a sample events API response."""
    if events is None:
        events = [
            {
                "filed_at": "2024-10-31",
                "category": "earnings",
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "items": [{"item_code": "2.02", "description": "Results of Operations (Item 2.02)"}],
            },
            {
                "filed_at": "2024-07-31",
                "category": "governance",
                "ticker": "MSFT",
                "company_name": "Microsoft Corporation",
                "items": [{"item_code": "5.07", "description": "Submission of Matters (Item 5.07)"}],
            },
        ]
    if total is None:
        total = len(events)
    return {
        "data": events,
        "pagination": {"page": 1, "per_page": 20, "total": total},
    }


def _company_response(cik: str = "0000320193", ticker: str = "AAPL", name: str = "Apple Inc.") -> dict[str, Any]:
    return {"data": {"cik": cik, "ticker": ticker, "name": name}}


@pytest.mark.asyncio
async def test_events_with_ticker() -> None:
    """get_events with ticker scopes to company endpoint."""
    ctx = _make_ctx(
        client_responses=[
            _company_response(),  # company lookup
            _events_response(),  # events
        ]
    )
    result = await get_events(ctx, ticker="AAPL")

    assert "Apple Inc. (AAPL)" in result
    # Verify resolver was called
    ctx.request_context.lifespan_context.resolver.resolve.assert_called_once_with("AAPL")
    # Verify company-scoped endpoint was used
    calls = ctx.request_context.lifespan_context.client.get.call_args_list
    assert any("/v1/us/sec/companies/0000320193/events" in str(c) for c in calls)


@pytest.mark.asyncio
async def test_events_without_ticker() -> None:
    """get_events without ticker uses all-events endpoint."""
    ctx = _make_ctx(single_response=_events_response())
    result = await get_events(ctx)

    assert "Recent" in result
    calls = ctx.request_context.lifespan_context.client.get.call_args_list
    assert calls[0][0][0] == "/v1/us/sec/events"


@pytest.mark.asyncio
async def test_events_empty_ticker() -> None:
    """get_events with empty string ticker uses all-events endpoint."""
    ctx = _make_ctx(single_response=_events_response())
    await get_events(ctx, ticker="  ")

    calls = ctx.request_context.lifespan_context.client.get.call_args_list
    assert calls[0][0][0] == "/v1/us/sec/events"


@pytest.mark.asyncio
async def test_events_category_filter() -> None:
    """get_events with category filter passes it to API."""
    ctx = _make_ctx(single_response=_events_response())
    await get_events(ctx, category="earnings")

    call_args = ctx.request_context.lifespan_context.client.get.call_args
    params = call_args.kwargs.get("params", {})
    assert params.get("category") == "earnings"


@pytest.mark.asyncio
async def test_events_invalid_category() -> None:
    """get_events with invalid category returns error listing valid categories."""
    ctx = _make_ctx(single_response=_events_response())
    result = await get_events(ctx, category="invalid_cat")

    assert "Invalid category 'invalid_cat'" in result
    assert "Valid categories:" in result
    assert "earnings" in result
    # Should not have made API call
    ctx.request_context.lifespan_context.client.get.assert_not_called()


@pytest.mark.asyncio
async def test_events_date_range() -> None:
    """get_events with date range passes from/to params."""
    ctx = _make_ctx(single_response=_events_response())
    await get_events(ctx, from_date="2024-01-01", to_date="2024-12-31")

    call_args = ctx.request_context.lifespan_context.client.get.call_args
    params = call_args.kwargs.get("params", {})
    assert params.get("from") == "2024-01-01"
    assert params.get("to") == "2024-12-31"


@pytest.mark.asyncio
async def test_events_invalid_date() -> None:
    """get_events with invalid date format returns helpful error."""
    ctx = _make_ctx(single_response=_events_response())
    result = await get_events(ctx, from_date="last week")

    assert "Invalid date format 'last week'" in result
    assert "YYYY-MM-DD" in result
    ctx.request_context.lifespan_context.client.get.assert_not_called()


@pytest.mark.asyncio
async def test_events_company_format_omits_ticker() -> None:
    """get_events company-scoped format omits ticker column."""
    ctx = _make_ctx(
        client_responses=[
            _company_response(),
            _events_response(),
        ]
    )
    result = await get_events(ctx, ticker="AAPL")

    # Company-scoped table has Date, Category, Description columns
    assert "Category" in result
    assert "Description" in result
    # Header shows company name
    assert "Apple Inc. (AAPL)" in result


@pytest.mark.asyncio
async def test_events_all_companies_includes_ticker() -> None:
    """get_events all-companies format includes ticker column."""
    ctx = _make_ctx(single_response=_events_response())
    result = await get_events(ctx)

    # All-companies table has Ticker and Company columns
    assert "Ticker" in result
    assert "Company" in result


@pytest.mark.asyncio
async def test_events_no_results() -> None:
    """get_events with no results returns helpful message."""
    ctx = _make_ctx(single_response=_events_response(events=[], total=0))
    result = await get_events(ctx, category="distress")

    assert "No events found" in result
