"""MCP tools for executive compensation and board governance."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context

from thesma_mcp.client import ThesmaAPIError
from thesma_mcp.formatters import format_currency, format_table
from thesma_mcp.server import AppContext, mcp


def _get_ctx(ctx: Context[Any, AppContext, Any]) -> AppContext:
    return ctx.request_context.lifespan_context


@mcp.tool(
    description=(
        "Get executive compensation (salary, bonus, stock awards, total) from proxy statements. "
        "Includes CEO-to-median pay ratio when available. Accepts ticker or CIK."
    )
)
async def get_executive_compensation(
    ticker: str,
    ctx: Context[Any, AppContext, Any],
    year: int | None = None,
) -> str:
    """Get named executive officer compensation."""
    app = _get_ctx(ctx)

    try:
        cik = await app.resolver.resolve(ticker)
    except ThesmaAPIError as e:
        return str(e)

    params: dict[str, Any] = {}
    if year is not None:
        params["year"] = year

    try:
        response = await app.client.get(f"/v1/us/sec/companies/{cik}/executive-compensation", params=params)
    except ThesmaAPIError as e:
        return str(e)

    data = response.get("data", {})
    if not data:
        return "No executive compensation data found for this company."

    company_name = data.get("company_name", ticker.upper())
    company_ticker = data.get("ticker", ticker.upper())
    fiscal_year = data.get("fiscal_year", year or "")
    executives = data.get("executives", [])
    pay_ratio = data.get("ceo_pay_ratio")
    ceo_total = data.get("ceo_total_compensation")
    median_pay = data.get("median_employee_compensation")
    accession = data.get("accession_number")

    if not executives:
        return "No executive compensation data found for this company."

    title = f"{company_name} ({company_ticker}) — Executive Compensation, FY {fiscal_year}"

    # Determine which columns have data
    comp_fields = [
        ("salary", "Salary"),
        ("bonus", "Bonus"),
        ("stock_awards", "Stock Awards"),
        ("option_awards", "Option Awards"),
        ("non_equity_incentive", "Non-Equity Incentive"),
        ("other_compensation", "Other"),
        ("total_compensation", "Total"),
    ]

    # Only show columns that have at least one non-null value
    active_fields: list[tuple[str, str]] = []
    for key, label in comp_fields:
        if any(e.get(key) is not None for e in executives):
            active_fields.append((key, label))

    headers = ["Name", "Title", *[label for _, label in active_fields]]
    alignments = ["l", "l", *["r" for _ in active_fields]]
    rows = []
    for exec_ in executives:
        row = [
            exec_.get("name", ""),
            exec_.get("title", ""),
        ]
        for key, _ in active_fields:
            row.append(format_currency(exec_.get(key)))
        rows.append(row)

    lines = [title, ""]
    lines.append(format_table(headers, rows, alignments=alignments))

    if pay_ratio is not None:
        lines.append("")
        lines.append(f"CEO-to-Median Pay Ratio: {pay_ratio}:1")
        if ceo_total is not None and median_pay is not None:
            ceo_fmt = format_currency(ceo_total)
            median_fmt = format_currency(median_pay)
            lines.append(f"  CEO compensation: {ceo_fmt} | Median employee: {median_fmt}")

    lines.append("")
    if accession:
        lines.append(f"Source: SEC EDGAR, DEF 14A filing {accession}.")
    else:
        lines.append("Source: SEC EDGAR, DEF 14A filing.")
    return "\n".join(lines)


@mcp.tool(
    description=(
        "Get board of directors (name, age, tenure, independence, committee memberships) "
        "from proxy statements. Accepts ticker or CIK."
    )
)
async def get_board_members(
    ticker: str,
    ctx: Context[Any, AppContext, Any],
    year: int | None = None,
) -> str:
    """Get board of directors from proxy statements."""
    app = _get_ctx(ctx)

    try:
        cik = await app.resolver.resolve(ticker)
    except ThesmaAPIError as e:
        return str(e)

    params: dict[str, Any] = {}
    if year is not None:
        params["year"] = year

    try:
        response = await app.client.get(f"/v1/us/sec/companies/{cik}/board", params=params)
    except ThesmaAPIError as e:
        return str(e)

    data = response.get("data", {})
    if not data:
        return "No board data found for this company."

    company_name = data.get("company_name", ticker.upper())
    company_ticker = data.get("ticker", ticker.upper())
    fiscal_year = data.get("fiscal_year", year or "")
    members = data.get("members", [])
    accession = data.get("accession_number")

    if not members:
        return "No board data found for this company."

    total = len(members)
    suffix = "s" if total != 1 else ""
    title = f"{company_name} ({company_ticker}) — Board of Directors, FY {fiscal_year} ({total} member{suffix})"

    headers = ["Name", "Age", "Tenure", "Independent", "Committees"]
    rows = []
    independent_count = 0
    countable = 0

    for m in members:
        is_independent = m.get("is_independent")
        if is_independent is True:
            ind_label = "Yes"
            independent_count += 1
            countable += 1
        elif is_independent is False:
            ind_label = "No"
            countable += 1
        else:
            ind_label = "N/A"

        tenure_years = m.get("tenure_years")
        tenure_str = f"{tenure_years} yr" if tenure_years is not None else "—"

        age = m.get("age")
        age_str = str(age) if age is not None else "—"

        committees = m.get("committees", [])
        if committees:
            committee_strs = []
            for c in committees:
                name = c if isinstance(c, str) else c.get("name", "")
                is_chair = False if isinstance(c, str) else c.get("is_chair", False)
                committee_strs.append(f"{name} (Chair)" if is_chair else name)
            committee_str = ", ".join(committee_strs)
        else:
            committee_str = "—"

        rows.append([m.get("name", ""), age_str, tenure_str, ind_label, committee_str])

    lines = [title, ""]
    lines.append(format_table(headers, rows, alignments=["l", "r", "r", "l", "l"]))
    lines.append("")
    if countable > 0:
        lines.append(f"{independent_count} of {total} directors are independent.")
    if accession:
        lines.append(f"Source: SEC EDGAR, DEF 14A filing {accession}.")
    else:
        lines.append("Source: SEC EDGAR, DEF 14A filing.")
    return "\n".join(lines)
