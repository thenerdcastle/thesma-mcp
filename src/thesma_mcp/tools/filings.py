"""MCP tools for SEC filing search."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from thesma_mcp.client import ThesmaAPIError
from thesma_mcp.formatters import format_table
from thesma_mcp.server import AppContext, mcp


def _get_ctx(ctx: Context[Any, AppContext, Any]) -> AppContext:
    return ctx.request_context.lifespan_context


@mcp.tool(
    description=(
        "Search SEC filings by company, type (10-K, 10-Q, 8-K, 4, DEF 14A, 13F-HR), and date range. "
        "Returns filing metadata with accession numbers."
    )
)
async def search_filings(
    ctx: Context[Any, AppContext, Any],
    ticker: str | None = None,
    type: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 20,
) -> str:
    """Search SEC filings by company, type, and date range."""
    app = _get_ctx(ctx)
    limit = min(limit, 50)

    params: dict[str, Any] = {"per_page": limit}
    cik: str | None = None

    if ticker:
        try:
            cik = await app.resolver.resolve(ticker)
        except ThesmaAPIError as e:
            return str(e)
        params["cik"] = cik

    if type:
        params["type"] = type
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    try:
        response = await app.client.get("/v1/us/sec/filings", params=params)
    except ThesmaAPIError as e:
        return str(e)

    filings = response.get("data", [])
    pagination = response.get("pagination", {})
    total = pagination.get("total", len(filings))

    if not filings:
        return "No filings found matching the search criteria."

    # Build title
    if ticker and filings:
        company_name = filings[0].get("company_name", ticker.upper())
        company_ticker = filings[0].get("ticker", ticker.upper())
        title = f"{company_name} ({company_ticker}) — SEC Filings ({len(filings)} of {total:,})"
    else:
        title = f"SEC Filings ({len(filings)} of {total:,})"

    headers = ["Date", "Type", "Period", "Accession Number"]
    rows = []
    for f in filings:
        filed_date = f.get("filed_date", f.get("filing_date", ""))
        filing_type = f.get("filing_type", f.get("type", ""))
        period = f.get("period_of_report", f.get("period", "—")) or "—"
        accession = f.get("accession_number", "")
        rows.append([filed_date, filing_type, period, accession])

    lines = [title, ""]
    lines.append(format_table(headers, rows, alignments=["l", "l", "l", "l"]))
    lines.append("")
    lines.append(f"Showing {len(filings)} of {total:,} filings.")
    lines.append("Source: SEC EDGAR filing index.")
    return "\n".join(lines)
