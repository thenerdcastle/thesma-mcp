"""Thesma API client — async httpx wrapper with auth, error handling, and timeout."""

from __future__ import annotations

import os
from typing import Any

import httpx

from thesma_mcp import __version__

DEFAULT_BASE_URL = "https://api.thesma.dev"
DEFAULT_TIMEOUT = 30.0


class ThesmaAPIError(Exception):
    """Raised when the Thesma API returns an error response."""


class ThesmaClient:
    """Async HTTP client for the Thesma REST API."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        resolved_key = api_key or os.environ.get("THESMA_API_KEY", "")
        if not resolved_key or not resolved_key.strip():
            msg = "THESMA_API_KEY not set. Get an API key at https://portal.thesma.dev"
            raise ThesmaAPIError(msg)

        self._base_url = (base_url or os.environ.get("THESMA_API_URL", "")).rstrip("/") or DEFAULT_BASE_URL
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {resolved_key}",
                "User-Agent": f"Thesma-MCP/{__version__}",
            },
            timeout=DEFAULT_TIMEOUT,
        )

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make an authenticated GET request and return parsed JSON."""
        try:
            response = await self._client.get(path, params=params)
        except httpx.TimeoutException:
            msg = f"Cannot reach Thesma API at {self._base_url}. Check your network connection."
            raise ThesmaAPIError(msg) from None
        except httpx.ConnectError:
            msg = f"Cannot reach Thesma API at {self._base_url}. Check your network connection."
            raise ThesmaAPIError(msg) from None

        if response.status_code >= 400:
            self._handle_error(response)

        result: dict[str, Any] = response.json()
        return result

    def _handle_error(self, response: httpx.Response) -> None:
        """Translate HTTP error responses into descriptive exceptions."""
        try:
            body = response.json()
            api_message = body.get("error", {}).get("message", "Unknown error")
        except Exception:
            api_message = "Unknown error"

        status = response.status_code

        if status == 401:
            msg = f"{api_message}. Get a new key at https://portal.thesma.dev"
            raise ThesmaAPIError(msg)
        elif status == 404:
            raise ThesmaAPIError(api_message)
        elif status == 429:
            retry_after = response.headers.get("Retry-After", "60")
            msg = (
                f"Rate limit exceeded. Try again in {retry_after} seconds. Upgrade at https://portal.thesma.dev/billing"
            )
            raise ThesmaAPIError(msg)
        elif status >= 500:
            msg = "Thesma API is temporarily unavailable. Try again in a moment."
            raise ThesmaAPIError(msg)
        else:
            raise ThesmaAPIError(api_message)

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()
