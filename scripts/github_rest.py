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


# ── per-user lines added / deleted via contributor stats ──────────────

async def fetch_contributor_lines(
    client: httpx.AsyncClient, owner: str, repo: str, username: str,
) -> tuple[int, int]:
    """Return (lines_added, lines_deleted) for a specific user in a repo."""
    url = f"{REST_BASE}/repos/{owner}/{repo}/stats/contributors"
    for attempt in range(6):
        resp = await _get(client, url)
        if resp.status_code == 202:
            await asyncio.sleep(3)
            continue
        if resp.status_code in (204, 404, 403):
            print(f"  [{owner}/{repo}] status={resp.status_code}, skipping")
            return (0, 0)
        if resp.status_code >= 400:
            print(f"  [{owner}/{repo}] status={resp.status_code}, skipping")
            return (0, 0)
        data = resp.json()
        if not isinstance(data, list):
            print(f"  [{owner}/{repo}] unexpected response type: {type(data)}")
            return (0, 0)
        for contributor in data:
            author = contributor.get("author") or {}
            if author.get("login", "").lower() == username.lower():
                weeks = contributor.get("weeks") or []
                added = sum(w.get("a", 0) for w in weeks)
                deleted = sum(w.get("d", 0) for w in weeks)
                print(f"  [{owner}/{repo}] +{added:,} -{deleted:,}")
                return (added, deleted)
        # User not in contributors list
        logins = [((c.get("author") or {}).get("login", "?")) for c in data[:5]]
        print(f"  [{owner}/{repo}] user not found in {len(data)} contributors (first: {logins})")
        return (0, 0)
    print(f"  [{owner}/{repo}] still 202 after retries")
    return (0, 0)


async def fetch_all_contributor_lines(
    client: httpx.AsyncClient, repo_names: list[str], username: str,
) -> tuple[int, int]:
    """Fetch per-user lines across contributed repos (top 20 by commits)."""
    tasks = [
        fetch_contributor_lines(client, name.split("/")[0], name.split("/")[1], username)
        for name in repo_names[:20]
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total_added = 0
    total_deleted = 0
    for result in results:
        if isinstance(result, Exception):
            continue
        total_added += result[0]
        total_deleted += result[1]
    return total_added, total_deleted


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
