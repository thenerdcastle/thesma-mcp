"""Insider trading (Form 4) — MCP tool."""

from __future__ import annotations

import re
from typing import Any

from mcp.server.fastmcp import Context

from thesma_mcp.formatters import format_currency, format_table
from thesma_mcp.server import AppContext, mcp

VALID_TYPES = frozenset({"purchase", "sale", "grant", "exercise"})

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

MAX_TITLE_LEN = 15


def _validate_date(value: str) -> str | None:
    """Return an error message if the date is not YYYY-MM-DD, else None."""
    if not DATE_PATTERN.match(value):
        return f"Invalid date format '{value}'. Expected YYYY-MM-DD."
    return None


def _truncate_title(title: str | None) -> str:
    """Truncate a title to MAX_TITLE_LEN characters."""
    if not title:
        return ""
    if len(title) <= MAX_TITLE_LEN:
        return title
    return title[: MAX_TITLE_LEN - 1] + "…"


def _format_shares_compact(value: float | int | None) -> str:
    """Format shares as a compact comma-separated number."""
    if value is None:
        return "N/A"
    return f"{int(value):,}"


def _format_price(value: float | None) -> str:
    """Format a per-share price."""
    if value is None:
        return "N/A"
    return f"${value:,.2f}"


@mcp.tool(
    description=(
        "Get insider trading transactions (Form 4) — purchases, sales, grants, and option exercises. "
        "Use ticker to scope to one company, or omit to search across all companies. "
        "Filter by transaction type, minimum value, and date range."
    )
)
async def get_insider_trades(
    ctx: Context[Any, Any],
    ticker: str | None = None,
    type: str | None = None,
    min_value: float | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 20,
) -> str:
    """Get insider trading transactions from Form 4."""
    app: AppContext = ctx.request_context.lifespan_context

    # Treat empty/whitespace ticker as None
    if ticker is not None and not ticker.strip():
        ticker = None

    # Validate type
    if type and type not in VALID_TYPES:
        valid = ", ".join(sorted(VALID_TYPES))
        return f"Invalid type '{type}'. Valid types: {valid}."

    # Validate dates
    for date_val, label in [(from_date, "from_date"), (to_date, "to_date")]:
        if date_val:
            err = _validate_date(date_val)
            if err:
                return err

    # Cap limit
    limit = min(limit, 50)

    # Build params
    params: dict[str, Any] = {"per_page": limit}
    if type:
        params["type"] = type
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    # Determine endpoint
    company_name: str | None = None
    company_ticker: str | None = None
    if ticker:
        cik = await app.resolver.resolve(ticker)
        path = f"/v1/us/sec/companies/{cik}/insider-trades"
        # Get company info for header
        company_resp = await app.client.get(f"/v1/us/sec/companies/{cik}")
        company_data = company_resp.get("data", {})
        company_name = company_data.get("name", ticker)
        company_ticker = company_data.get("ticker", ticker.upper())
    else:
        path = "/v1/us/sec/insider-trades"
        if min_value is not None:
            params["min_value"] = min_value

    response = await app.client.get(path, params=params)
    data = response.get("data", [])
    pagination = response.get("pagination", {})
    total = pagination.get("total", len(data))

    if not data:
        scope = f"for {company_name}" if company_name else ""
        type_filter = f" of type '{type}'" if type else ""
        return f"No insider trades found{' ' + scope if scope else ''}{type_filter}. Try adjusting your filters."

    count_shown = len(data)
    type_label = f"Insider {type.title()}s" if type else "Insider Trades"

    # Build header
    min_val_label = f" over {format_currency(min_value)}" if min_value else ""
    if company_name:
        header = f"{company_name} ({company_ticker}) — Recent {type_label} ({count_shown} of {total:,})"
    else:
        header = f"Recent {type_label}{min_val_label} ({count_shown} of {total:,})"

    # Build table — different columns for company-scoped vs all-companies
    if company_name:
        headers = ["Date", "Person", "Title", "Shares", "Price", "Value"]
        alignments = ["l", "l", "l", "r", "r", "r"]
        rows = [
            [
                trade.get("transaction_date", trade.get("date", ""))[:10],
                trade.get("owner_name", ""),
                _truncate_title(trade.get("title", "")),
                _format_shares_compact(trade.get("shares")),
                _format_price(trade.get("price_per_share")),
                format_currency(trade.get("total_value")),
            ]
            for trade in data
        ]
    else:
        headers = ["Date", "Ticker", "Person", "Title", "Value", "Planned?"]
        alignments = ["l", "l", "l", "l", "r", "l"]
        rows = [
            [
                trade.get("transaction_date", trade.get("date", ""))[:10],
                trade.get("ticker", ""),
                trade.get("owner_name", ""),
                _truncate_title(trade.get("title", "")),
                format_currency(trade.get("total_value")),
                "Yes" if trade.get("is_10b5_1") else "No",
            ]
            for trade in data
        ]

    table = format_table(headers, rows, alignments)

    # Footer
    footer = (
        f"{total:,} total {type_label.lower()} found. Showing most recent {count_shown}.\n"
        "Source: SEC EDGAR, Form 4 filings."
    )

    return f"{header}\n\n{table}\n\n{footer}"
