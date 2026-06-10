from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx

from .config import (
    BACKOFF_BASE,
    END_YEAR,
    GRAPHQL_URL,
    MAX_RETRIES,
    START_YEAR,
    USERNAME,
)

# Limit concurrent requests to avoid GitHub rejecting bursts
_semaphore = asyncio.Semaphore(3)


def _headers() -> dict:
    from .config import GH_TOKEN
    return {
        "Authorization": f"bearer {GH_TOKEN}",
        "Content-Type": "application/json",
    }

# ── helpers ──────────────────────────────────────────────────────────

async def _post(client: httpx.AsyncClient, payload: dict) -> dict:
    """POST to GraphQL endpoint with exponential backoff and rate-limit handling."""
    hdrs = _headers()
    async with _semaphore:
        for attempt in range(MAX_RETRIES):
            resp = await client.post(GRAPHQL_URL, json=payload, headers=hdrs)

            if resp.status_code in (401, 403) and attempt < MAX_RETRIES - 1:
                await asyncio.sleep(BACKOFF_BASE ** (attempt + 1))
                continue

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", BACKOFF_BASE ** (attempt + 1)))
                await asyncio.sleep(retry_after)
                continue

            if resp.status_code == 502:
                await asyncio.sleep(BACKOFF_BASE ** (attempt + 1))
                continue

            resp.raise_for_status()
            body = resp.json()

            if "errors" in body:
                raise RuntimeError(f"GraphQL errors: {body['errors']}")

            return body["data"]

    raise RuntimeError("Max retries exceeded for GraphQL request")


# ── user profile info ────────────────────────────────────────────────

USER_INFO_QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    following { totalCount }
  }
}
"""


async def fetch_user_info(client: httpx.AsyncClient) -> dict:
    data = await _post(client, {
        "query": USER_INFO_QUERY,
        "variables": {"login": USERNAME},
    })
    return data["user"]


# ── contributions per year ───────────────────────────────────────────

CONTRIBUTIONS_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
      totalRepositoriesWithContributedCommits
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
      commitContributionsByRepository(maxRepositories: 100) {
        repository {
          nameWithOwner
          stargazerCount
          primaryLanguage { name }
        }
        contributions { totalCount }
      }
    }
  }
}
"""


async def fetch_contributions_for_year(
    client: httpx.AsyncClient, year: int
) -> dict:
    from_dt = f"{year}-01-01T00:00:00Z"
    to_dt = f"{year}-12-31T23:59:59Z"
    if year == datetime.now(timezone.utc).year:
        to_dt = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    variables = {"login": USERNAME, "from": from_dt, "to": to_dt}
    data = await _post(client, {"query": CONTRIBUTIONS_QUERY, "variables": variables})
    return data["user"]["contributionsCollection"]


async def fetch_all_years(client: httpx.AsyncClient) -> list[dict]:
    tasks = [
        fetch_contributions_for_year(client, y) for y in range(START_YEAR, END_YEAR + 1)
    ]
    return list(zip(range(START_YEAR, END_YEAR + 1), await asyncio.gather(*tasks)))


# ── lifetime PR / issue counts via search ────────────────────────────

async def fetch_search_counts(client: httpx.AsyncClient) -> dict:
    query = f"""
    {{
      prsOpened: search(query: "author:{USERNAME} type:pr", type: ISSUE, first: 0) {{ issueCount }}
      prsMerged: search(query: "author:{USERNAME} type:pr is:merged", type: ISSUE, first: 0) {{ issueCount }}
      issuesOpened: search(query: "author:{USERNAME} type:issue", type: ISSUE, first: 0) {{ issueCount }}
      issuesClosed: search(query: "author:{USERNAME} type:issue is:closed", type: ISSUE, first: 0) {{ issueCount }}
    }}
    """
    data = await _post(client, {"query": query})
    return {
        "prs_opened": data["prsOpened"]["issueCount"],
        "prs_merged": data["prsMerged"]["issueCount"],
        "issues_opened": data["issuesOpened"]["issueCount"],
        "issues_closed": data["issuesClosed"]["issueCount"],
    }
