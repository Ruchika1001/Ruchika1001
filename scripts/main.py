"""Entry point: fetch GitHub stats and render README.md."""
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from . import github_graphql as gql
from . import github_rest as rest
from .config import USERNAME
from .markdown_renderer import render
from .stats_aggregator import aggregate


async def run() -> None:
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        # Kick off independent API calls in parallel
        year_data_task = asyncio.create_task(gql.fetch_all_years(client))
        search_task = asyncio.create_task(gql.fetch_search_counts(client))
        repos_task = asyncio.create_task(rest.fetch_user_repos(client))
        user_info_task = asyncio.create_task(gql.fetch_user_info(client))

        year_data = await year_data_task
        search_counts = await search_task
        repos = await repos_task
        user_info = await user_info_task

        # Second wave: depends on repos list
        languages = await rest.fetch_all_languages(client, repos)

    stats = aggregate(year_data, search_counts, languages, repos, user_info, USERNAME)
    readme_content = render(stats)

    output_path = Path(__file__).resolve().parent.parent / "README.md"
    output_path.write_text(readme_content, encoding="utf-8")
    print(f"README.md written ({len(readme_content)} bytes)")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
