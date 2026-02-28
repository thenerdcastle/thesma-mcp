"""Tests for institutional holdings tools."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from thesma_mcp.tools.holdings import (
    get_fund_holdings,
    get_holding_changes,
    get_institutional_holders,
    search_funds,
)


def _make_ctx(
    resolve_cik: str = "0000320193",
    single_response: dict[str, Any] | None = None,
    multi_responses: list[dict[str, Any]] | None = None,
) -> MagicMock:
    ctx = MagicMock()
    app = MagicMock()
    app.resolver = AsyncMock()
    app.resolver.resolve = AsyncMock(return_value=resolve_cik)
    if multi_responses:
        app.client.get = AsyncMock(side_effect=multi_responses)
    elif single_response:
        app.client.get = AsyncMock(return_value=single_response)
    else:
        app.client.get = AsyncMock(return_value={"data": []})
    ctx.request_context.lifespan_context = app
    return ctx


class TestSearchFunds:
    async def test_returns_fund_list(self) -> None:
        """search_funds returns formatted fund list."""
        ctx = _make_ctx(
            single_response={
                "data": [
                    {"cik": "0001067983", "name": "BERKSHIRE HATHAWAY INC"},
                    {"cik": "0001234567", "name": "BERKSHIRE CAPITAL HOLDINGS LLC"},
                ],
                "pagination": {"page": 1, "per_page": 25, "total": 2},
            }
        )
        result = await search_funds("berkshire", ctx)
        assert "BERKSHIRE HATHAWAY" in result
        assert "0001067983" in result
        assert "Found 2 funds" in result

    async def test_no_results(self) -> None:
        """search_funds with no results returns helpful message."""
        ctx = _make_ctx(single_response={"data": [], "pagination": {"page": 1, "per_page": 25, "total": 0}})
        result = await search_funds("xyznonexistent", ctx)
        assert "No funds found" in result


class TestGetInstitutionalHolders:
    async def test_returns_formatted_table(self) -> None:
        """get_institutional_holders resolves ticker and returns formatted table."""
        ctx = _make_ctx(
            single_response={
                "data": [
                    {
                        "company_name": "Apple Inc.",
                        "company_ticker": "AAPL",
                        "fund_name": "VANGUARD GROUP INC",
                        "shares": 1_250_300_000,
                        "market_value": 286_300_000_000,
                        "discretion": "shared",
                        "quarter": "2024-Q3",
                    },
                ],
                "pagination": {"page": 1, "per_page": 25, "total": 4521},
            }
        )
        result = await get_institutional_holders("AAPL", ctx)
        assert "Apple Inc. (AAPL)" in result
        assert "VANGUARD GROUP" in result
        assert "Shared" in result
        assert "4,521" in result

    async def test_formats_large_share_counts(self) -> None:
        """get_institutional_holders formats large share counts with M/K units."""
        ctx = _make_ctx(
            single_response={
                "data": [
                    {
                        "company_name": "Apple Inc.",
                        "company_ticker": "AAPL",
                        "fund_name": "VANGUARD GROUP INC",
                        "shares": 1_250_300_000,
                        "market_value": 286_300_000_000,
                        "quarter": "2024-Q3",
                    },
                ],
                "pagination": {"page": 1, "per_page": 25, "total": 1},
            }
        )
        result = await get_institutional_holders("AAPL", ctx)
        assert "1.3B" in result or "1250.3M" in result  # formatted with units

    async def test_no_holders(self) -> None:
        """get_institutional_holders with no holders returns helpful message."""
        ctx = _make_ctx(single_response={"data": [], "pagination": {"page": 1, "per_page": 25, "total": 0}})
        result = await get_institutional_holders("AAPL", ctx)
        assert "No institutional holders" in result


class TestGetFundHoldings:
    async def test_resolves_fund_name(self) -> None:
        """get_fund_holdings resolves fund name to CIK via search."""
        ctx = _make_ctx(
            multi_responses=[
                {"data": [{"cik": "0001067983", "name": "BERKSHIRE HATHAWAY INC"}]},  # fund search
                {  # holdings
                    "data": [
                        {
                            "fund_name": "BERKSHIRE HATHAWAY INC",
                            "ticker": "AAPL",
                            "company_name": "Apple Inc.",
                            "shares": 400_000_000,
                            "market_value": 91_600_000_000,
                            "quarter": "2024-Q3",
                        },
                    ],
                    "pagination": {"page": 1, "per_page": 25, "total": 42},
                },
            ]
        )
        result = await get_fund_holdings("Berkshire Hathaway", ctx)
        assert "BERKSHIRE HATHAWAY" in result
        assert "AAPL" in result
        assert "Apple Inc." in result

    async def test_fund_name_not_found(self) -> None:
        """get_fund_holdings with fund name returning no search results returns error."""
        ctx = _make_ctx(single_response={"data": []})
        result = await get_fund_holdings("NonexistentFund", ctx)
        assert "No fund found" in result

    async def test_cik_skips_search(self) -> None:
        """get_fund_holdings with CIK skips search."""
        ctx = _make_ctx(
            single_response={
                "data": [
                    {
                        "fund_name": "BERKSHIRE HATHAWAY INC",
                        "ticker": "AAPL",
                        "company_name": "Apple Inc.",
                        "shares": 400_000_000,
                        "market_value": 91_600_000_000,
                        "quarter": "2024-Q3",
                    },
                ],
                "pagination": {"page": 1, "per_page": 25, "total": 1},
            }
        )
        result = await get_fund_holdings("0001067983", ctx)
        assert "Apple Inc." in result
        # Should only call once (no search needed)
        ctx.request_context.lifespan_context.client.get.assert_called_once()

    async def test_position_type_filter(self) -> None:
        """get_fund_holdings with position_type filter passes to API."""
        ctx = _make_ctx(
            multi_responses=[
                {"data": [{"cik": "0001067983", "name": "BERKSHIRE HATHAWAY INC"}]},
                {"data": [], "pagination": {"page": 1, "per_page": 25, "total": 0}},
            ]
        )
        await get_fund_holdings("Berkshire", ctx, position_type="debt")
        calls = ctx.request_context.lifespan_context.client.get.call_args_list
        holdings_call = calls[1]
        assert holdings_call[1]["params"]["position_type"] == "debt"

    async def test_empty_portfolio(self) -> None:
        """get_fund_holdings with empty portfolio returns helpful message."""
        ctx = _make_ctx(
            multi_responses=[
                {"data": [{"cik": "0001067983", "name": "BERKSHIRE HATHAWAY INC"}]},
                {"data": [], "pagination": {"page": 1, "per_page": 25, "total": 0}},
            ]
        )
        result = await get_fund_holdings("Berkshire", ctx)
        assert "No holdings found" in result


class TestGetHoldingChanges:
    async def test_by_ticker(self) -> None:
        """get_holding_changes with ticker uses company institutional-changes endpoint."""
        ctx = _make_ctx(
            single_response={
                "data": [
                    {
                        "company_name": "Apple Inc.",
                        "company_ticker": "AAPL",
                        "fund_name": "BRIDGEWATER ASSOCIATES",
                        "change_type": "new",
                        "shares_delta": 2_500_000,
                        "current_value": 572_500_000,
                        "quarter": "2024-Q3",
                    },
                ],
                "pagination": {"page": 1, "per_page": 25, "total": 312},
            }
        )
        result = await get_holding_changes(ctx, ticker="AAPL")
        assert "Apple Inc. (AAPL)" in result
        assert "BRIDGEWATER" in result
        assert "New" in result
        assert "institutional-changes" in str(ctx.request_context.lifespan_context.client.get.call_args)

    async def test_by_fund_name(self) -> None:
        """get_holding_changes with fund_name uses fund holding-changes endpoint."""
        ctx = _make_ctx(
            multi_responses=[
                {"data": [{"cik": "0001067983", "name": "BERKSHIRE HATHAWAY INC"}]},
                {
                    "data": [
                        {
                            "fund_name": "BERKSHIRE HATHAWAY INC",
                            "ticker": "SIRI",
                            "company_name": "Sirius XM Holdings",
                            "change_type": "new",
                            "shares_delta": 105_200_000,
                            "current_value": 310_300_000,
                            "quarter": "2024-Q3",
                        },
                    ],
                    "pagination": {"page": 1, "per_page": 25, "total": 10},
                },
            ]
        )
        result = await get_holding_changes(ctx, fund_name="Berkshire Hathaway")
        assert "BERKSHIRE HATHAWAY" in result
        assert "SIRI" in result
        assert "New" in result

    async def test_fund_name_not_found(self) -> None:
        """get_holding_changes with fund_name returning no search results returns error."""
        ctx = _make_ctx(single_response={"data": []})
        result = await get_holding_changes(ctx, fund_name="NonexistentFund")
        assert "No fund found" in result

    async def test_neither_provided(self) -> None:
        """get_holding_changes with neither ticker nor fund_name returns error."""
        ctx = _make_ctx()
        result = await get_holding_changes(ctx)
        assert "Provide exactly one" in result

    async def test_both_provided(self) -> None:
        """get_holding_changes with both ticker and fund_name returns error."""
        ctx = _make_ctx()
        result = await get_holding_changes(ctx, ticker="AAPL", fund_name="Berkshire")
        assert "Provide exactly one" in result

    async def test_no_changes(self) -> None:
        """get_holding_changes with no changes returns helpful message."""
        ctx = _make_ctx(single_response={"data": [], "pagination": {"page": 1, "per_page": 25, "total": 0}})
        result = await get_holding_changes(ctx, ticker="AAPL")
        assert "No position changes" in result

    async def test_formats_deltas(self) -> None:
        """get_holding_changes formats deltas with +/- prefix."""
        ctx = _make_ctx(
            single_response={
                "data": [
                    {
                        "company_name": "Apple Inc.",
                        "company_ticker": "AAPL",
                        "fund_name": "CITADEL",
                        "change_type": "increased",
                        "shares_delta": 1_800_000,
                        "percent_change": 45.0,
                        "current_value": 1_200_000_000,
                        "quarter": "2024-Q3",
                    },
                ],
                "pagination": {"page": 1, "per_page": 25, "total": 1},
            }
        )
        result = await get_holding_changes(ctx, ticker="AAPL")
        assert "+1.8M" in result
        assert "+45.0%" in result
        assert "Increased" in result

    async def test_new_and_exited(self) -> None:
        """get_holding_changes shows 'New'/'Exited' correctly."""
        ctx = _make_ctx(
            single_response={
                "data": [
                    {
                        "company_name": "Apple Inc.",
                        "company_ticker": "AAPL",
                        "fund_name": "FUND A",
                        "change_type": "new",
                        "shares_delta": 2_500_000,
                        "current_value": 500_000_000,
                        "quarter": "2024-Q3",
                    },
                    {
                        "company_name": "Apple Inc.",
                        "company_ticker": "AAPL",
                        "fund_name": "FUND B",
                        "change_type": "exited",
                        "shares_delta": -3_200_000,
                        "percent_change": -100.0,
                        "current_value": None,
                        "quarter": "2024-Q3",
                    },
                ],
                "pagination": {"page": 1, "per_page": 25, "total": 2},
            }
        )
        result = await get_holding_changes(ctx, ticker="AAPL")
        assert "New" in result
        assert "Exited" in result
        # New positions show — for % change
        lines = result.split("\n")
        # Find the line with "New" and check for —
        new_line = next(line for line in lines if "FUND A" in line)
        assert "—" in new_line  # no % change for new
