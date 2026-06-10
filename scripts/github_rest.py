from __future__ import annotations

import asyncio

import httpx

from .config import (
    BACKOFF_BASE,
    MAX_RETRIES,
    REST_BASE,
    USERNAME,
)

# Limit concurrent requests to avoid GitHub rejecting bursts
_semaphore = asyncio.Semaphore(3)


def _headers() -> dict:
    from .config import GH_TOKEN
    return {
        "Authorization": f"token {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


async def _get(client: httpx.AsyncClient, url: str, params: dict | None = None) -> httpx.Response:
    hdrs = _headers()
    async with _semaphore:
        for attempt in range(MAX_RETRIES):
            resp = await client.get(url, headers=hdrs, params=params)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", BACKOFF_BASE ** (attempt + 1)))
                await asyncio.sleep(retry_after)
                continue

            if resp.status_code in (401, 403) and attempt < MAX_RETRIES - 1:
                await asyncio.sleep(BACKOFF_BASE ** (attempt + 1))
                continue

            if resp.status_code >= 500:
                await asyncio.sleep(BACKOFF_BASE ** (attempt + 1))
                continue

            return resp

    raise RuntimeError(f"Max retries exceeded for {url}")


# ── repos ────────────────────────────────────────────────────────────

async def fetch_user_repos(client: httpx.AsyncClient) -> list[dict]:
    """Fetch all repos owned by the user (paginated)."""
    repos: list[dict] = []
    page = 1
    while True:
        resp = await _get(
            client,
            f"{REST_BASE}/users/{USERNAME}/repos",
            params={"per_page": 100, "page": page, "type": "owner"},
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos


# ── languages ────────────────────────────────────────────────────────

async def fetch_repo_languages(client: httpx.AsyncClient, owner: str, repo: str) -> dict[str, int]:
    resp = await _get(client, f"{REST_BASE}/repos/{owner}/{repo}/languages")
    if resp.status_code == 404:
        return {}
    resp.raise_for_status()
    return resp.json()


async def fetch_all_languages(client: httpx.AsyncClient, repos: list[dict]) -> dict[str, int]:
    """Aggregate language byte counts across all repos."""
    tasks = [
        fetch_repo_languages(client, r["owner"]["login"], r["name"])
        for r in repos
        if not r.get("fork")
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    totals: dict[str, int] = {}
    for result in results:
        if isinstance(result, Exception):
            continue
        for lang, count in result.items():
            totals[lang] = totals.get(lang, 0) + count
    return totals
