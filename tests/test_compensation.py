"""Tests for executive compensation and board governance tools."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from thesma_mcp.client import ThesmaAPIError
from thesma_mcp.tools.compensation import get_board_members, get_executive_compensation


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
        app.client.get = AsyncMock(return_value={"data": {}})
    ctx.request_context.lifespan_context = app
    return ctx


SAMPLE_EXEC_COMP = {
    "data": {
        "company_name": "Apple Inc.",
        "ticker": "AAPL",
        "fiscal_year": 2024,
        "accession_number": "0000320193-24-000456",
        "ceo_pay_ratio": 287,
        "ceo_total_compensation": 74_600_000,
        "median_employee_compensation": 260_000,
        "executives": [
            {
                "name": "Timothy D. Cook",
                "title": "CEO",
                "salary": 3_000_000,
                "stock_awards": 58_000_000,
                "total_compensation": 74_600_000,
                "bonus": None,
                "option_awards": None,
            },
            {
                "name": "Luca Maestri",
                "title": "SVP, CFO",
                "salary": 1_000_000,
                "stock_awards": 21_000_000,
                "total_compensation": 27_200_000,
                "bonus": None,
                "option_awards": None,
            },
        ],
    }
}

SAMPLE_BOARD = {
    "data": {
        "company_name": "Apple Inc.",
        "ticker": "AAPL",
        "fiscal_year": 2024,
        "accession_number": "0000320193-24-000456",
        "members": [
            {
                "name": "Timothy D. Cook",
                "age": 63,
                "tenure_years": 13,
                "is_independent": False,
                "committees": [],
            },
            {
                "name": "James Bell",
                "age": 75,
                "tenure_years": 8,
                "is_independent": True,
                "committees": [{"name": "Audit", "is_chair": True}],
            },
            {
                "name": "Andrea Jung",
                "age": 65,
                "tenure_years": 16,
                "is_independent": True,
                "committees": [
                    {"name": "Compensation", "is_chair": True},
                    {"name": "Nominating", "is_chair": False},
                ],
            },
        ],
    }
}


class TestGetExecutiveCompensation:
    async def test_returns_formatted_table(self) -> None:
        """get_executive_compensation returns formatted table."""
        ctx = _make_ctx(single_response=SAMPLE_EXEC_COMP)
        result = await get_executive_compensation("AAPL", ctx)
        assert "Apple Inc. (AAPL)" in result
        assert "Timothy D. Cook" in result
        assert "CEO" in result
        assert "$3.0M" in result  # salary
        assert "$74.6M" in result  # total

    async def test_skips_null_columns(self) -> None:
        """get_executive_compensation skips all-null columns."""
        ctx = _make_ctx(single_response=SAMPLE_EXEC_COMP)
        result = await get_executive_compensation("AAPL", ctx)
        # bonus and option_awards are null for all execs — should not appear
        assert "Bonus" not in result
        assert "Option Awards" not in result
        # But salary and stock awards should appear
        assert "Salary" in result
        assert "Stock Awards" in result

    async def test_includes_pay_ratio(self) -> None:
        """get_executive_compensation includes pay ratio when available."""
        ctx = _make_ctx(single_response=SAMPLE_EXEC_COMP)
        result = await get_executive_compensation("AAPL", ctx)
        assert "287:1" in result
        assert "$74.6M" in result
        assert "$260.0K" in result

    async def test_omits_pay_ratio_when_null(self) -> None:
        """get_executive_compensation omits pay ratio section when null."""
        data = {
            "data": {
                **SAMPLE_EXEC_COMP["data"],
                "ceo_pay_ratio": None,
                "ceo_total_compensation": None,
                "median_employee_compensation": None,
            }
        }
        ctx = _make_ctx(single_response=data)
        result = await get_executive_compensation("AAPL", ctx)
        assert "Pay Ratio" not in result

    async def test_no_data(self) -> None:
        """get_executive_compensation with no data returns helpful message."""
        ctx = _make_ctx(single_response={"data": {}})
        result = await get_executive_compensation("AAPL", ctx)
        assert "No executive compensation data" in result

    async def test_api_error(self) -> None:
        """get_executive_compensation passes through API error."""
        ctx = _make_ctx()
        ctx.request_context.lifespan_context.resolver.resolve = AsyncMock(
            side_effect=ThesmaAPIError("Company not found")
        )
        result = await get_executive_compensation("ZZZZ", ctx)
        assert "Company not found" in result


class TestGetBoardMembers:
    async def test_returns_formatted_table(self) -> None:
        """get_board_members returns formatted table with committees."""
        ctx = _make_ctx(single_response=SAMPLE_BOARD)
        result = await get_board_members("AAPL", ctx)
        assert "Apple Inc. (AAPL)" in result
        assert "Board of Directors" in result
        assert "Timothy D. Cook" in result
        assert "James Bell" in result

    async def test_shows_chair_designation(self) -> None:
        """get_board_members shows chair designation."""
        ctx = _make_ctx(single_response=SAMPLE_BOARD)
        result = await get_board_members("AAPL", ctx)
        assert "Audit (Chair)" in result
        assert "Compensation (Chair)" in result

    async def test_counts_independent_directors(self) -> None:
        """get_board_members counts independent directors."""
        ctx = _make_ctx(single_response=SAMPLE_BOARD)
        result = await get_board_members("AAPL", ctx)
        assert "2 of 3 directors are independent" in result

    async def test_null_independence(self) -> None:
        """get_board_members shows 'N/A' for null independence."""
        data = {
            "data": {
                **SAMPLE_BOARD["data"],
                "members": [
                    {
                        "name": "Unknown Director",
                        "age": 50,
                        "tenure_years": 5,
                        "is_independent": None,
                        "committees": [],
                    },
                ],
            }
        }
        ctx = _make_ctx(single_response=data)
        result = await get_board_members("AAPL", ctx)
        assert "N/A" in result

    async def test_no_data(self) -> None:
        """get_board_members with no data returns helpful message."""
        ctx = _make_ctx(single_response={"data": {}})
        result = await get_board_members("AAPL", ctx)
        assert "No board data" in result
