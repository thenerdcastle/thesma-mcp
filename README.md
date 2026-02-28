# Thesma MCP Server

Give your AI assistant access to SEC EDGAR financial data.

[![PyPI version](https://img.shields.io/pypi/v/thesma-mcp)](https://pypi.org/project/thesma-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/thesma-mcp)](https://pypi.org/project/thesma-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

## What it does

An [MCP](https://modelcontextprotocol.io/) server that wraps the [Thesma API](https://thesma.dev), giving AI assistants (Claude, Cursor, ChatGPT) native access to SEC EDGAR data — financials, ratios, insider trades, institutional holdings, executive compensation, and more.

Ask questions in plain English. Get structured financial data back.

## Quick example

> "What was Apple's revenue last year?"

The AI calls `get_financials` and returns Apple's income statement with formatted line items.

> "Find high-margin S&P 500 companies where insiders are buying"

The AI calls `screen_companies` with margin filters and insider buying signals.

> "Which funds increased their position in NVDA last quarter?"

The AI calls `get_holding_changes` and shows quarter-over-quarter position changes.

## Installation

```bash
pip install thesma-mcp
```

### Claude Desktop

Add to your config file (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "thesma": {
      "command": "uvx",
      "args": ["thesma-mcp"],
      "env": {
        "THESMA_API_KEY": "your-api-key"
      }
    }
  }
}
```

### Cursor

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "thesma": {
      "command": "uvx",
      "args": ["thesma-mcp"],
      "env": {
        "THESMA_API_KEY": "your-api-key"
      }
    }
  }
}
```

> **Using `pip install` instead of `uvx`?** If you've already installed `thesma-mcp` with pip, you can use `"command": "thesma-mcp"` directly (no `args` needed) instead of `uvx`.

Get your API key at [portal.thesma.dev](https://portal.thesma.dev) (free tier: 1,000 requests/day).

## Available tools

### Company Discovery

| Tool | Description |
|------|-------------|
| `search_companies` | Find US public companies by name or ticker symbol |
| `get_company` | Get company details — CIK, SIC code, fiscal year end, index membership |

### Financial Statements

| Tool | Description |
|------|-------------|
| `get_financials` | Get income statement, balance sheet, or cash flow from SEC filings |
| `get_financial_metric` | Get a single financial metric over time for trend analysis |

### Financial Ratios

| Tool | Description |
|------|-------------|
| `get_ratios` | Get computed financial ratios — margins, returns, leverage, growth |
| `get_ratio_history` | Get a single ratio over time for trend analysis |

### Screening

| Tool | Description |
|------|-------------|
| `screen_companies` | Find companies matching financial criteria — profitability, growth, leverage, insider/institutional signals |

### Corporate Events

| Tool | Description |
|------|-------------|
| `get_events` | Get 8-K corporate events — earnings, M&A, leadership changes, material agreements |

### Insider Trading

| Tool | Description |
|------|-------------|
| `get_insider_trades` | Get Form 4 insider transactions — purchases, sales, grants, option exercises |

### Institutional Holdings

| Tool | Description |
|------|-------------|
| `search_funds` | Find institutional investment managers (hedge funds, mutual funds) by name |
| `get_institutional_holders` | Get which funds hold a company's stock with shares and market values |
| `get_fund_holdings` | Get a fund's portfolio — what stocks it owns |
| `get_holding_changes` | Get quarter-over-quarter changes in institutional positions |

### Compensation & Governance

| Tool | Description |
|------|-------------|
| `get_executive_compensation` | Get executive pay — salary, bonus, stock awards, total, CEO pay ratio |
| `get_board_members` | Get board of directors — age, tenure, independence, committee memberships |

### Filings

| Tool | Description |
|------|-------------|
| `search_filings` | Search SEC filings by company, type (10-K, 10-Q, 8-K, etc.), and date range |

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `THESMA_API_KEY` | Yes | API key from [portal.thesma.dev](https://portal.thesma.dev) |
| `THESMA_API_URL` | No | Override API base URL (default: `https://api.thesma.dev`) |

## Data coverage

- ~1,000 US public companies (Russell 1000 + S&P 500)
- Financial statements from 2009-present (iXBRL and companyfacts sources)
- Insider trades, institutional holdings, executive compensation, board data
- Data sourced from SEC EDGAR (public domain)

## Links

- [Thesma API docs](https://docs.thesma.dev)
- [Developer portal](https://portal.thesma.dev)
- [Website](https://thesma.dev)

## License

MIT
