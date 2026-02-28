"""MCP tools for institutional holdings."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from thesma_mcp.client import ThesmaAPIError
from thesma_mcp.formatters import format_currency, format_number, format_table
from thesma_mcp.resolver import CIK_PATTERN
from thesma_mcp.server import AppContext, mcp


def _get_ctx(ctx: Context[Any, AppContext, Any]) -> AppContext:
    return ctx.request_context.lifespan_context


async def _resolve_fund_cik(app: AppContext, fund_name: str) -> str:
    """Resolve a fund name or CIK to a CIK string."""
    if CIK_PATTERN.match(fund_name):
        return fund_name

    response = await app.client.get("/v1/us/sec/funds", params={"search": fund_name})
    data = response.get("data", [])
    if not data:
        msg = f"No fund found matching '{fund_name}'. Try a different name or use the fund's CIK directly."
        raise ThesmaAPIError(msg)

    cik: str = data[0]["cik"]
    return cik


@mcp.tool(
    description=(
        "Find institutional investment managers (hedge funds, mutual funds) by name. "
        "Use this to look up a fund's CIK before querying its holdings."
    )
)
async def search_funds(
    query: str,
    ctx: Context[Any, AppContext, Any],
    limit: int = 20,
) -> str:
    """Search for institutional funds by name."""
    app = _get_ctx(ctx)
    limit = min(limit, 50)

    response = await app.client.get("/v1/us/sec/funds", params={"search": query, "per_page": limit})
    funds = response.get("data", [])

    if not funds:
        return f'No funds found matching "{query}". Try a different name.'

    count = len(funds)
    lines = [f'Found {count} fund{"" if count == 1 else "s"} matching "{query}"', ""]

    headers = ["#", "CIK", "Fund Name"]
    rows = [[str(i), f.get("cik", ""), f.get("name", "")] for i, f in enumerate(funds, 1)]

    lines.append(format_table(headers, rows, alignments=["r", "l", "l"]))
    lines.append("")
    lines.append("Source: SEC EDGAR, 13F filings.")
    return "\n".join(lines)


@mcp.tool(
    description=(
        "Get which institutional funds hold a company's stock. "
        "Shows shares held, market value, and discretion type. Accepts ticker or CIK."
    )
)
async def get_institutional_holders(
    ticker: str,
    ctx: Context[Any, AppContext, Any],
    quarter: str | None = None,
    limit: int = 20,
) -> str:
    """Get institutional holders of a company's stock."""
    app = _get_ctx(ctx)
    limit = min(limit, 50)

    try:
        cik = await app.resolver.resolve(ticker)
    except ThesmaAPIError as e:
        return str(e)

    params: dict[str, Any] = {"per_page": limit}
    if quarter:
        params["quarter"] = quarter

    try:
        response = await app.client.get(f"/v1/us/sec/companies/{cik}/institutional-holders", params=params)
    except ThesmaAPIError as e:
        return str(e)

    holders = response.get("data", [])
    pagination = response.get("pagination", {})
    total = pagination.get("total", len(holders))

    if not holders:
        return "No institutional holders found for this company."

    company_name = holders[0].get("company_name", ticker.upper()) if holders else ticker.upper()
    company_ticker = holders[0].get("company_ticker", ticker.upper()) if holders else ticker.upper()
    q_label = quarter or holders[0].get("quarter", "Latest") if holders else "Latest"

    title = f"{company_name} ({company_ticker}) — Top Institutional Holders, {q_label} ({len(holders)} of {total:,})"

    headers = ["#", "Fund", "Shares", "Market Value", "Discretion"]
    rows = []
    for i, h in enumerate(holders, 1):
        shares = h.get("shares")
        value = h.get("market_value")
        discretion = h.get("discretion", "").title() if h.get("discretion") else ""
        rows.append(
            [
                str(i),
                h.get("fund_name", ""),
                format_number(shares, decimals=1) if shares is not None else "N/A",
                format_currency(value) if value is not None else "N/A",
                discretion,
            ]
        )

    lines = [title, ""]
    lines.append(format_table(headers, rows, alignments=["r", "l", "r", "r", "l"]))
    lines.append("")
    lines.append(f"Showing {len(holders)} of {total:,} institutional holders.")
    lines.append(f"Source: SEC EDGAR, 13F filings ({q_label}).")
    return "\n".join(lines)


@mcp.tool(
    description=(
        "Get a fund's portfolio holdings. Shows what stocks a fund owns, "
        "with share counts and market values. Accepts fund name or CIK."
    )
)
async def get_fund_holdings(
    fund_name: str,
    ctx: Context[Any, AppContext, Any],
    quarter: str | None = None,
    position_type: str = "equity",
    limit: int = 20,
) -> str:
    """Get a fund's portfolio holdings."""
    app = _get_ctx(ctx)
    limit = min(limit, 50)

    try:
        fund_cik = await _resolve_fund_cik(app, fund_name)
    except ThesmaAPIError as e:
        return str(e)

    params: dict[str, Any] = {"per_page": limit}
    if quarter:
        params["quarter"] = quarter
    if position_type != "all":
        params["position_type"] = position_type

    try:
        response = await app.client.get(f"/v1/us/sec/funds/{fund_cik}/holdings", params=params)
    except ThesmaAPIError as e:
        return str(e)

    holdings = response.get("data", [])
    pagination = response.get("pagination", {})
    total = pagination.get("total", len(holdings))

    if not holdings:
        return "No holdings found for this fund."

    fund_display = holdings[0].get("fund_name", fund_name.upper()) if holdings else fund_name.upper()
    q_label = quarter or holdings[0].get("quarter", "Latest") if holdings else "Latest"
    type_label = position_type.title() if position_type != "all" else "All"

    title = f"{fund_display} — Portfolio Holdings, {q_label} ({type_label}, {len(holdings)} of {total:,})"

    headers = ["#", "Ticker", "Company", "Shares", "Market Value"]
    rows = []
    for i, h in enumerate(holdings, 1):
        shares = h.get("shares")
        value = h.get("market_value")
        rows.append(
            [
                str(i),
                h.get("ticker", h.get("company_ticker", "")),
                h.get("company_name", h.get("name", "")),
                format_number(shares, decimals=1) if shares is not None else "N/A",
                format_currency(value) if value is not None else "N/A",
            ]
        )

    lines = [title, ""]
    lines.append(format_table(headers, rows, alignments=["r", "l", "l", "r", "r"]))
    lines.append("")
    lines.append(f"Showing {len(holdings)} of {total:,} {type_label.lower()} positions.")
    lines.append(f"Source: SEC EDGAR, 13F filing ({q_label}).")
    return "\n".join(lines)


@mcp.tool(
    description=(
        "Get quarter-over-quarter changes in institutional holdings. "
        "Use 'ticker' to see which funds are buying/selling a company, "
        "or 'fund_name' to see what a fund is buying/selling. Provide exactly one."
    )
)
async def get_holding_changes(
    ctx: Context[Any, AppContext, Any],
    ticker: str | None = None,
    fund_name: str | None = None,
    quarter: str | None = None,
    change: str | None = None,
    limit: int = 20,
) -> str:
    """Get quarter-over-quarter position changes."""
    if (ticker and fund_name) or (not ticker and not fund_name):
        return (
            "Provide exactly one of 'ticker' or 'fund_name'. "
            "Use ticker to see which funds changed positions, or fund_name to see what positions changed."
        )

    app = _get_ctx(ctx)
    limit = min(limit, 50)

    params: dict[str, Any] = {"per_page": limit}
    if quarter:
        params["quarter"] = quarter
    if change:
        params["change"] = change

    if ticker:
        try:
            cik = await app.resolver.resolve(ticker)
        except ThesmaAPIError as e:
            return str(e)
        try:
            response = await app.client.get(f"/v1/us/sec/companies/{cik}/institutional-changes", params=params)
        except ThesmaAPIError as e:
            return str(e)
        return _format_changes_by_ticker(response, ticker)
    else:
        assert fund_name is not None
        try:
            fund_cik = await _resolve_fund_cik(app, fund_name)
        except ThesmaAPIError as e:
            return str(e)
        try:
            response = await app.client.get(f"/v1/us/sec/funds/{fund_cik}/holding-changes", params=params)
        except ThesmaAPIError as e:
            return str(e)
        return _format_changes_by_fund(response, fund_name)


def _format_changes_by_ticker(response: dict[str, Any], ticker: str) -> str:
    """Format holding changes for a company (who's buying/selling?)."""
    changes = response.get("data", [])
    pagination = response.get("pagination", {})
    total = pagination.get("total", len(changes))

    if not changes:
        return "No position changes found for this company in the selected quarter."

    company_name = changes[0].get("company_name", ticker.upper())
    company_ticker = changes[0].get("company_ticker", ticker.upper())
    q_label = changes[0].get("quarter", "Latest")

    count_shown = len(changes)
    title = (
        f"{company_name} ({company_ticker}) — Institutional Position Changes, {q_label} ({count_shown} of {total:,})"
    )

    headers = ["#", "Fund", "Change", "Shares Delta", "% Change", "Current Value"]
    rows = []
    for i, c in enumerate(changes, 1):
        rows.append(
            [
                str(i),
                c.get("fund_name", ""),
                _change_label(c.get("change_type", "")),
                _format_delta(c.get("shares_delta"), c.get("change_type", "")),
                _format_pct_change(c.get("percent_change"), c.get("change_type", "")),
                _format_current_value(c.get("current_value"), c.get("change_type", "")),
            ]
        )

    lines = [title, ""]
    lines.append(format_table(headers, rows, alignments=["r", "l", "l", "r", "r", "r"]))
    lines.append("")
    lines.append(f"Showing {len(changes)} of {total:,} position changes.")
    lines.append(f"Source: SEC EDGAR, 13F filings ({q_label}).")
    return "\n".join(lines)


def _format_changes_by_fund(response: dict[str, Any], fund_name: str) -> str:
    """Format holding changes for a fund (what's the fund buying/selling?)."""
    changes = response.get("data", [])
    pagination = response.get("pagination", {})
    total = pagination.get("total", len(changes))

    if not changes:
        return "No position changes found for this fund in the selected quarter."

    fund_display = changes[0].get("fund_name", fund_name.upper())
    q_label = changes[0].get("quarter", "Latest")

    title = f"{fund_display} — Position Changes, {q_label} ({len(changes)} of {total:,})"

    headers = ["#", "Ticker", "Company", "Change", "Shares Delta", "% Change", "Current Value"]
    rows = []
    for i, c in enumerate(changes, 1):
        rows.append(
            [
                str(i),
                c.get("ticker", c.get("company_ticker", "")),
                c.get("company_name", ""),
                _change_label(c.get("change_type", "")),
                _format_delta(c.get("shares_delta"), c.get("change_type", "")),
                _format_pct_change(c.get("percent_change"), c.get("change_type", "")),
                _format_current_value(c.get("current_value"), c.get("change_type", "")),
            ]
        )

    lines = [title, ""]
    lines.append(format_table(headers, rows, alignments=["r", "l", "l", "l", "r", "r", "r"]))
    lines.append("")
    lines.append(f"Showing {len(changes)} of {total:,} position changes.")
    lines.append(f"Source: SEC EDGAR, 13F filings ({q_label}).")
    return "\n".join(lines)


def _change_label(change_type: str) -> str:
    """Format change type for display."""
    return {
        "new": "New",
        "exited": "Exited",
        "increased": "Increased",
        "decreased": "Decreased",
        "unchanged": "Unchanged",
    }.get(change_type, change_type.title() if change_type else "")


def _format_delta(shares_delta: float | int | None, change_type: str) -> str:
    """Format shares delta with +/- prefix."""
    if shares_delta is None:
        return "—"
    formatted = format_number(abs(shares_delta), decimals=1)
    if change_type in ("new", "increased"):
        return f"+{formatted}"
    elif change_type in ("exited", "decreased"):
        return f"-{formatted}"
    return formatted


def _format_pct_change(pct: float | None, change_type: str) -> str:
    """Format percentage change, showing — for new positions."""
    if change_type == "new":
        return "—"
    if pct is None:
        return "—"
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.1f}%"


def _format_current_value(value: float | int | None, change_type: str) -> str:
    """Format current value, showing — for exited positions."""
    if change_type == "exited":
        return "—"
    if value is None:
        return "N/A"
    return format_currency(value)
