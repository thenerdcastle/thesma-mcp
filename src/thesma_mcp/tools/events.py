"""Corporate events (8-K) — MCP tool."""

from __future__ import annotations

import re
from typing import Any

from mcp.server.fastmcp import Context

from thesma_mcp.formatters import format_table
from thesma_mcp.server import AppContext, mcp

VALID_CATEGORIES = frozenset(
    {
        "earnings",
        "ma",
        "leadership",
        "agreements",
        "governance",
        "accounting",
        "distress",
        "regulatory",
        "other",
    }
)

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_date(value: str) -> str | None:
    """Return an error message if the date is not YYYY-MM-DD, else None."""
    if not DATE_PATTERN.match(value):
        return f"Invalid date format '{value}'. Expected YYYY-MM-DD."
    return None


def _event_description(event: dict[str, Any]) -> str:
    """Extract a display description from an event."""
    items = event.get("items", [])
    if items:
        return str(items[0].get("description", ""))
    return str(event.get("description", ""))


@mcp.tool(
    description=(
        "Get 8-K corporate events (earnings, M&A, leadership changes, material agreements). "
        "Use ticker to scope to one company, or omit to search across all companies. "
        "Filter by category and date range."
    )
)
async def get_events(
    ctx: Context[Any, Any],
    ticker: str | None = None,
    category: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 20,
) -> str:
    """Get 8-K corporate events."""
    app: AppContext = ctx.request_context.lifespan_context

    # Treat empty/whitespace ticker as None
    if ticker is not None and not ticker.strip():
        ticker = None

    # Validate category
    if category and category not in VALID_CATEGORIES:
        valid = ", ".join(sorted(VALID_CATEGORIES))
        return f"Invalid category '{category}'. Valid categories: {valid}."

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
    if category:
        params["category"] = category
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    # Determine endpoint
    company_name: str | None = None
    company_ticker: str | None = None
    if ticker:
        cik = await app.resolver.resolve(ticker)
        path = f"/v1/us/sec/companies/{cik}/events"
        # Get company info for header
        company_resp = await app.client.get(f"/v1/us/sec/companies/{cik}")
        company_data = company_resp.get("data", {})
        company_name = company_data.get("name", ticker)
        company_ticker = company_data.get("ticker", ticker.upper())
    else:
        path = "/v1/us/sec/events"

    response = await app.client.get(path, params=params)
    data = response.get("data", [])
    pagination = response.get("pagination", {})
    total = pagination.get("total", len(data))

    if not data:
        scope = f"for {company_name}" if company_name else ""
        cat_filter = f" in category '{category}'" if category else ""
        return f"No events found{' ' + scope if scope else ''}{cat_filter}. Try adjusting your filters."

    count_shown = len(data)
    cat_label = category.title() if category else "Corporate Events"

    # Build header
    if company_name:
        header = f"{company_name} ({company_ticker}) — {cat_label} ({count_shown} of {total:,})"
    else:
        header = f"Recent {cat_label} ({count_shown} of {total:,})"

    # Build table
    if company_name:
        headers = ["Date", "Category", "Description"]
        alignments = ["l", "l", "l"]
        rows = [
            [event.get("filed_at", event.get("date", ""))[:10], event.get("category", ""), _event_description(event)]
            for event in data
        ]
    else:
        headers = ["Date", "Ticker", "Company", "Description"]
        alignments = ["l", "l", "l", "l"]
        rows = [
            [
                event.get("filed_at", event.get("date", ""))[:10],
                event.get("ticker", ""),
                event.get("company_name", ""),
                _event_description(event),
            ]
            for event in data
        ]

    table = format_table(headers, rows, alignments)

    # Footer
    cat_suffix = f" {category}" if category else ""
    footer = f"Showing {count_shown} of {total:,}{cat_suffix} events.\nSource: SEC EDGAR, 8-K filings."

    return f"{header}\n\n{table}\n\n{footer}"
