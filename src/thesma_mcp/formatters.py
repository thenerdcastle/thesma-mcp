"""Number and response formatting utilities for LLM-friendly output."""

from __future__ import annotations


def format_currency(value: float | int | None, decimals: int = 1) -> str:
    """Format a number as currency with unit suffix. Returns 'N/A' for None."""
    if value is None:
        return "N/A"
    return "$" + _format_with_unit(float(value), decimals)


def format_number(value: float | int | None, decimals: int = 1) -> str:
    """Format a number with unit suffix (no dollar sign). Returns 'N/A' for None."""
    if value is None:
        return "N/A"
    return _format_with_unit(float(value), decimals)


def format_percent(value: float | int | None, decimals: int = 1) -> str:
    """Format a number as a percentage. Returns 'N/A' for None."""
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}%"


def format_shares(value: int | float | None) -> str:
    """Format a number as comma-separated shares. Returns 'N/A' for None."""
    if value is None:
        return "N/A"
    return f"{int(value):,} shares"


def _format_with_unit(value: float, decimals: int) -> str:
    """Format a number with T/B/M/K unit suffix."""
    abs_value = abs(value)
    sign = "-" if value < 0 else ""

    if abs_value >= 1_000_000_000_000:
        return f"{sign}{abs_value / 1_000_000_000_000:.{decimals}f}T"
    elif abs_value >= 1_000_000_000:
        return f"{sign}{abs_value / 1_000_000_000:.{decimals}f}B"
    elif abs_value >= 1_000_000:
        return f"{sign}{abs_value / 1_000_000:.{decimals}f}M"
    elif abs_value >= 1_000:
        return f"{sign}{abs_value / 1_000:.{decimals}f}K"
    else:
        if abs_value != int(abs_value) or decimals > 0:
            return f"{sign}{abs_value:.{decimals}f}"
        return f"{sign}{int(abs_value)}"


def format_table(headers: list[str], rows: list[list[str]], alignments: list[str] | None = None) -> str:
    """Format data as an aligned text table.

    Args:
        headers: Column header strings.
        rows: List of rows, each a list of cell strings.
        alignments: Per-column alignment, "l" for left or "r" for right.
                    Defaults to left for all columns.
    """
    if not rows:
        return ""

    if alignments is None:
        alignments = ["l"] * len(headers)

    all_rows = [headers, *rows]
    col_widths = [max(len(str(row[i])) for row in all_rows) for i in range(len(headers))]

    def _format_row(row: list[str]) -> str:
        cells = []
        for i, cell in enumerate(row):
            width = col_widths[i]
            if alignments[i] == "r":
                cells.append(str(cell).rjust(width))
            else:
                cells.append(str(cell).ljust(width))
        return "  ".join(cells)

    lines = [_format_row(headers)]
    lines.append("  ".join("-" * w for w in col_widths))
    for row in rows:
        lines.append(_format_row(row))

    return "\n".join(lines)


def format_source(filing_type: str, accession: str | None = None, data_source: str | None = None) -> str:
    """Produce a source attribution line.

    Args:
        filing_type: E.g., "10-K", "Form 4".
        accession: Optional filing accession number.
        data_source: Optional data source label (e.g., "ixbrl", "companyfacts").
    """
    source_label = {
        "ixbrl": "iXBRL",
        "companyfacts": "CompanyFacts",
    }.get(data_source or "", data_source or "")

    if accession:
        suffix = f" ({source_label})" if source_label else ""
        return f"Source: SEC EDGAR, {filing_type} filing {accession}{suffix}"
    else:
        return f"Source: SEC EDGAR, {filing_type} filings."


def format_pagination(shown: int, total: int, sort_description: str | None = None) -> str:
    """Produce a pagination/count summary line."""
    if shown == total:
        base = f"{total} result{'s' if total != 1 else ''} found."
    elif shown < total:
        base = f"Showing 1-{shown} of {total}."
    else:
        base = f"{shown} results shown."

    if sort_description:
        base = base.rstrip(".") + f" sorted by {sort_description}."

    return base
