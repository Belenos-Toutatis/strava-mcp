"""Strava REST client — async httpx wrapper with rate-limit awareness."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any

import httpx

from .auth import TokenManager

API_BASE = "https://www.strava.com/api/v3"

# Strava default limits: 100 / 15min, 1000 / day per app.
SHORT_WINDOW_SECONDS = 15 * 60
SHORT_LIMIT = 100
DAILY_LIMIT = 1000


class StravaError(RuntimeError):
    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"Strava API {status}: {body}")
        self.status = status
        self.body = body


class StravaClient:
    def __init__(self, token_manager: TokenManager | None = None) -> None:
        self._tokens = token_manager or TokenManager()
        self._client = httpx.AsyncClient(timeout=60)
        self._short_calls: deque[float] = deque()
        self._daily_calls: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _wait_for_slot(self) -> None:
        async with self._lock:
            now = time.time()
            while self._short_calls and now - self._short_calls[0] > SHORT_WINDOW_SECONDS:
                self._short_calls.popleft()
            while self._daily_calls and now - self._daily_calls[0] > 86400:
                self._daily_calls.popleft()
            if len(self._short_calls) >= SHORT_LIMIT:
                sleep_for = SHORT_WINDOW_SECONDS - (now - self._short_calls[0]) + 0.5
                await asyncio.sleep(max(0.0, sleep_for))
            if len(self._daily_calls) >= DAILY_LIMIT:
                raise StravaError(429, "Daily Strava API limit reached (local guard).")
            now = time.time()
            self._short_calls.append(now)
            self._daily_calls.append(now)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._tokens.access_token()}"}

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        data: dict | None = None,
        json_body: dict | None = None,
        files: dict | None = None,
    ) -> Any:
        await self._wait_for_slot()
        url = f"{API_BASE}{path}" if path.startswith("/") else path
        for attempt in range(3):
            resp = await self._client.request(
                method,
                url,
                params=params,
                data=data,
                json=json_body,
                files=files,
                headers=self._headers(),
            )
            if resp.status_code == 429:
                # Honour Retry-After if present, else backoff.
                retry_after = float(resp.headers.get("Retry-After", "30"))
                await asyncio.sleep(retry_after)
                continue
            if resp.status_code >= 400:
                raise StravaError(resp.status_code, resp.text[:800])
            if resp.status_code == 204 or not resp.content:
                return None
            ctype = resp.headers.get("content-type", "")
            if "application/json" in ctype:
                return resp.json()
            return resp.content
        raise StravaError(429, "Rate-limited after retries.")

    # Convenience wrappers
    async def get(self, path: str, **params) -> Any:
        return await self.request("GET", path, params={k: v for k, v in params.items() if v is not None})

    async def put(self, path: str, **fields) -> Any:
        return await self.request("PUT", path, json_body={k: v for k, v in fields.items() if v is not None})

    async def post_form(self, path: str, *, data: dict | None = None, files: dict | None = None) -> Any:
        return await self.request("POST", path, data=data, files=files)
