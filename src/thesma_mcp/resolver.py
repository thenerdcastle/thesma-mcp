"""Ticker-to-CIK resolution with in-memory cache."""

from __future__ import annotations

import re

from thesma_mcp.client import ThesmaAPIError, ThesmaClient

CIK_PATTERN = re.compile(r"^0\d{9}$")


class TickerResolver:
    """Resolves stock tickers to SEC CIKs, caching results in memory."""

    def __init__(self, client: ThesmaClient) -> None:
        self._client = client
        self._cache: dict[str, str] = {}

    async def resolve(self, ticker_or_cik: str) -> str:
        """Resolve a ticker or CIK to a 10-digit zero-padded CIK string.

        If the input is already a CIK (10-digit zero-padded starting with "0"),
        return it as-is. Otherwise, look up the ticker via the Thesma API.
        """
        if CIK_PATTERN.match(ticker_or_cik):
            return ticker_or_cik

        cache_key = ticker_or_cik.upper()
        if cache_key in self._cache:
            return self._cache[cache_key]

        response = await self._client.get("/v1/us/sec/companies", params={"ticker": cache_key})
        data = response.get("data", [])
        if not data:
            msg = f"No company found for ticker '{ticker_or_cik}'. Try searching with search_companies."
            raise ThesmaAPIError(msg)

        cik: str = data[0]["cik"]
        self._cache[cache_key] = cik
        return cik
