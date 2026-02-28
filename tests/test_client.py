"""Tests for the Thesma API client."""

from __future__ import annotations

import httpx
import pytest
import respx

from thesma_mcp.client import ThesmaAPIError, ThesmaClient

BASE_URL = "https://api.thesma.dev"


async def test_successful_get(client: ThesmaClient, mock_api: respx.MockRouter) -> None:
    """Successful GET returns parsed JSON."""
    mock_api.get("/v1/test").mock(return_value=httpx.Response(200, json={"data": {"result": "ok"}}))
    result = await client.get("/v1/test")
    assert result == {"data": {"result": "ok"}}


async def test_auth_header(client: ThesmaClient, mock_api: respx.MockRouter) -> None:
    """API key is sent in Authorization header."""
    route = mock_api.get("/v1/test").mock(return_value=httpx.Response(200, json={"data": {}}))
    await client.get("/v1/test")

    request = route.calls[0].request
    assert request.headers["Authorization"] == "Bearer test-key-123"


async def test_user_agent_header(client: ThesmaClient, mock_api: respx.MockRouter) -> None:
    """User-Agent header includes Thesma-MCP/ prefix."""
    route = mock_api.get("/v1/test").mock(return_value=httpx.Response(200, json={"data": {}}))
    await client.get("/v1/test")

    request = route.calls[0].request
    assert request.headers["User-Agent"].startswith("Thesma-MCP/")


async def test_401_error(client: ThesmaClient, mock_api: respx.MockRouter) -> None:
    """401 passes through API message with portal link."""
    mock_api.get("/v1/test").mock(
        return_value=httpx.Response(
            401,
            json={"error": {"status": 401, "code": "unauthorized", "message": "Invalid or revoked API key."}},
        )
    )
    with pytest.raises(ThesmaAPIError, match="Invalid or revoked API key."):
        await client.get("/v1/test")

    # Verify portal link is appended
    with pytest.raises(ThesmaAPIError, match="https://portal.thesma.dev"):
        await client.get("/v1/test")


async def test_404_error(client: ThesmaClient, mock_api: respx.MockRouter) -> None:
    """404 passes through API error message."""
    mock_api.get("/v1/test").mock(
        return_value=httpx.Response(
            404,
            json={"error": {"status": 404, "code": "not_found", "message": "Company not found"}},
        )
    )
    with pytest.raises(ThesmaAPIError, match="Company not found"):
        await client.get("/v1/test")


async def test_429_error(client: ThesmaClient, mock_api: respx.MockRouter) -> None:
    """429 produces rate limit message with retry seconds."""
    mock_api.get("/v1/test").mock(
        return_value=httpx.Response(
            429,
            headers={"Retry-After": "30"},
            json={"error": {"status": 429, "code": "rate_limited", "message": "Rate limited"}},
        )
    )
    with pytest.raises(ThesmaAPIError, match="Rate limit exceeded. Try again in 30 seconds"):
        await client.get("/v1/test")

    with pytest.raises(ThesmaAPIError, match="https://portal.thesma.dev/billing"):
        await client.get("/v1/test")


async def test_5xx_error(client: ThesmaClient, mock_api: respx.MockRouter) -> None:
    """5xx produces 'temporarily unavailable' message."""
    mock_api.get("/v1/test").mock(
        return_value=httpx.Response(500, json={"error": {"status": 500, "code": "internal", "message": "Oops"}})
    )
    with pytest.raises(ThesmaAPIError, match="temporarily unavailable"):
        await client.get("/v1/test")


async def test_network_timeout(mock_api: respx.MockRouter) -> None:
    """Network timeout produces 'Cannot reach' message."""
    client = ThesmaClient(api_key="test-key")
    mock_api.get("/v1/test").mock(side_effect=httpx.TimeoutException("timed out"))

    with pytest.raises(ThesmaAPIError, match="Cannot reach Thesma API"):
        await client.get("/v1/test")


async def test_connection_error(mock_api: respx.MockRouter) -> None:
    """Connection error produces 'Cannot reach' message."""
    client = ThesmaClient(api_key="test-key")
    mock_api.get("/v1/test").mock(side_effect=httpx.ConnectError("connection refused"))

    with pytest.raises(ThesmaAPIError, match="Cannot reach Thesma API"):
        await client.get("/v1/test")


def test_missing_api_key() -> None:
    """Missing API key raises on construction."""
    import os

    env_backup = os.environ.pop("THESMA_API_KEY", None)
    try:
        with pytest.raises(ThesmaAPIError, match="THESMA_API_KEY not set"):
            ThesmaClient(api_key=None)
    finally:
        if env_backup is not None:
            os.environ["THESMA_API_KEY"] = env_backup


def test_empty_api_key() -> None:
    """Empty string API key raises on construction."""
    with pytest.raises(ThesmaAPIError, match="THESMA_API_KEY not set"):
        ThesmaClient(api_key="")


def test_whitespace_api_key() -> None:
    """Whitespace-only API key raises on construction."""
    with pytest.raises(ThesmaAPIError, match="THESMA_API_KEY not set"):
        ThesmaClient(api_key="   ")
