"""Shared test fixtures — mock API client, sample responses."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from thesma_mcp.client import ThesmaClient
from thesma_mcp.resolver import TickerResolver

BASE_URL = "https://api.thesma.dev"


@pytest.fixture()
def mock_api() -> respx.MockRouter:
    """Create a respx mock router for the Thesma API."""
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
        yield router


@pytest.fixture()
def client(mock_api: respx.MockRouter) -> ThesmaClient:
    """Create a ThesmaClient with a test API key."""
    return ThesmaClient(api_key="test-key-123")


@pytest.fixture()
def resolver(client: ThesmaClient) -> TickerResolver:
    """Create a TickerResolver backed by the mock client."""
    return TickerResolver(client)


# --- Sample API responses ---


def company_response(cik: str = "0000320193", ticker: str = "AAPL", name: str = "Apple Inc.") -> dict[str, Any]:
    """Sample single company response."""
    return {"data": {"cik": cik, "ticker": ticker, "name": name}}


def company_list_response(
    companies: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Sample company list response."""
    if companies is None:
        companies = [{"cik": "0000320193", "ticker": "AAPL", "name": "Apple Inc."}]
    return {
        "data": companies,
        "pagination": {"page": 1, "per_page": 25, "total": len(companies)},
    }


def error_response(status: int, code: str, message: str) -> dict[str, Any]:
    """Sample error response."""
    return {"error": {"status": status, "code": code, "message": message}}


def mock_error(status: int, code: str, message: str) -> httpx.Response:
    """Create a mock error response."""
    return httpx.Response(
        status_code=status,
        json=error_response(status, code, message),
    )
