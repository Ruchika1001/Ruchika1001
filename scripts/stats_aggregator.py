from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta


WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


@dataclass
class YearStats:
    year: int
    commits: int = 0
    prs: int = 0
    issues: int = 0
    reviews: int = 0
    private: int = 0
    total: int = 0


@dataclass
class RepoInfo:
    name: str
    stars: int = 0
    commits: int = 0
    language: str = ""


@dataclass
class StreakInfo:
    longest_days: int = 0
    longest_start: str = ""
    longest_end: str = ""
    current_days: int = 0
    current_start: str = ""


@dataclass
class MonthActivity:
    month: str = ""  # "YYYY-MM"
    label: str = ""  # "Mar 2024"
    count: int = 0


@dataclass
class ProfileStats:
    # Overview
    total_contributions: int = 0
    total_commits: int = 0
    prs_opened: int = 0
    prs_merged: int = 0
    merge_rate: float = 0.0
    total_reviews: int = 0
    issues_opened: int = 0
    issues_closed: int = 0
    issue_close_rate: float = 0.0
    lines_added: int = 0
    lines_deleted: int = 0
    net_lines: int = 0
    repos_contributed_to: int = 0
    total_repos_owned: int = 0

    # Activity insights
    active_days: int = 0
    total_days_tracked: int = 0
    consistency_pct: float = 0.0  # active_days / total_days * 100
    avg_contributions_per_active_day: float = 0.0
    avg_prs_per_month: float = 0.0
    reviews_per_pr: float = 0.0
    most_productive_weekday: str = ""
    weekday_distribution: dict[str, int] = field(default_factory=dict)
    weekend_pct: float = 0.0
    best_year: int = 0
    best_year_count: int = 0
    busiest_month: MonthActivity = field(default_factory=MonthActivity)

    # Organizations
    orgs_contributed_to: list[str] = field(default_factory=list)

    # Streaks
    streak: StreakInfo = field(default_factory=StreakInfo)

    # Languages: {name: bytes}
    languages: dict[str, int] = field(default_factory=dict)
    total_languages: int = 0

    # Year-over-year
    yearly: list[YearStats] = field(default_factory=list)

    # Top repos
    top_repos: list[RepoInfo] = field(default_factory=list)

    # Profile
    account_created: str = ""
    account_age_years: int = 0
    followers: int = 0
    following: int = 0


def _compute_streaks(year_data: list[tuple[int, dict]]) -> StreakInfo:
    all_days: list[tuple[date, int]] = []
    for _year, collection in year_data:
        calendar = collection.get("contributionCalendar", {})
        for week in calendar.get("weeks", []):
            for day in week.get("contributionDays", []):
                d = date.fromisoformat(day["date"])
                all_days.append((d, day["contributionCount"]))

    all_days.sort(key=lambda x: x[0])

    if not all_days:
        return StreakInfo()

    longest_days = 0
    longest_start = all_days[0][0]
    longest_end = all_days[0][0]

    streak_start = all_days[0][0]
    streak_len = 0

    for i, (d, count) in enumerate(all_days):
        if count > 0:
            if streak_len == 0:
                streak_start = d
            streak_len += 1
        else:
            if streak_len > longest_days:
                longest_days = streak_len
                longest_start = streak_start
                longest_end = all_days[i - 1][0] if i > 0 else streak_start
            streak_len = 0

    if streak_len > longest_days:
        longest_days = streak_len
        longest_start = streak_start
        longest_end = all_days[-1][0]

    today = date.today()
    day_map = {d: c for d, c in all_days}
    current_days = 0
    current_start_date = today
    check = today
    while day_map.get(check, 0) > 0:
        current_days += 1
        current_start_date = check
        check -= timedelta(days=1)
    if current_days == 0:
        check = today - timedelta(days=1)
        while day_map.get(check, 0) > 0:
            current_days += 1
            current_start_date = check
            check -= timedelta(days=1)

    return StreakInfo(
        longest_days=longest_days,
        longest_start=longest_start.isoformat(),
        longest_end=longest_end.isoformat(),
        current_days=current_days,
        current_start=current_start_date.isoformat(),
    )


def _compute_activity_insights(
    year_data: list[tuple[int, dict]],
) -> tuple[int, int, float, str, dict[str, int], float, MonthActivity]:
    """Return (active_days, total_days, avg_per_active_day, best_weekday, weekday_dist, weekend_pct, busiest_month)."""
    weekday_totals = {name: 0 for name in WEEKDAY_NAMES}
    monthly_totals: dict[str, int] = {}
    active_days = 0
    total_days = 0
    total_contribs = 0

    for _year, collection in year_data:
        calendar = collection.get("contributionCalendar", {})
        for week in calendar.get("weeks", []):
            for day in week.get("contributionDays", []):
                d = date.fromisoformat(day["date"])
                count = day["contributionCount"]
                total_days += 1
                total_contribs += count
                weekday_name = WEEKDAY_NAMES[d.weekday()]
                weekday_totals[weekday_name] += count
                if count > 0:
                    active_days += 1
                month_key = d.strftime("%Y-%m")
                monthly_totals[month_key] = monthly_totals.get(month_key, 0) + count

    avg = round(total_contribs / active_days, 1) if active_days > 0 else 0.0
    best_weekday = max(weekday_totals, key=weekday_totals.get) if weekday_totals else ""

    weekend = weekday_totals.get("Saturday", 0) + weekday_totals.get("Sunday", 0)
    weekend_pct = round(weekend / total_contribs * 100, 1) if total_contribs > 0 else 0.0

    busiest_month = MonthActivity()
    if monthly_totals:
        best_key = max(monthly_totals, key=monthly_totals.get)
        best_date = date.fromisoformat(best_key + "-01")
        busiest_month = MonthActivity(
            month=best_key,
            label=best_date.strftime("%b %Y"),
            count=monthly_totals[best_key],
        )

    return active_days, total_days, avg, best_weekday, weekday_totals, weekend_pct, busiest_month


def _aggregate_yearly(year_data: list[tuple[int, dict]]) -> list[YearStats]:
    yearly = []
    for year, collection in year_data:
        commits = collection.get("totalCommitContributions", 0)
        prs = collection.get("totalPullRequestContributions", 0)
        issues = collection.get("totalIssueContributions", 0)
        reviews = collection.get("totalPullRequestReviewContributions", 0)
        total = collection.get("contributionCalendar", {}).get("totalContributions", 0)
        calendar_total = collection.get("contributionCalendar", {}).get("totalContributions", 0)
        public_total = commits + prs + issues + reviews
        private = max(calendar_total - public_total, 0)
        yearly.append(YearStats(
            year=year, commits=commits, prs=prs,
            issues=issues, reviews=reviews,
            private=private, total=calendar_total,
        ))
    return yearly


def _aggregate_top_repos(year_data: list[tuple[int, dict]], limit: int = 5) -> list[RepoInfo]:
    repo_map: dict[str, RepoInfo] = {}
    for _year, collection in year_data:
        for entry in collection.get("commitContributionsByRepository", []):
            repo = entry["repository"]
            name = repo["nameWithOwner"]
            commits = entry["contributions"]["totalCount"]
            if name not in repo_map:
                repo_map[name] = RepoInfo(
                    name=name,
                    stars=repo.get("stargazerCount", 0),
                    commits=0,
                    language=(repo.get("primaryLanguage") or {}).get("name", ""),
                )
            repo_map[name].commits += commits
    ranked = sorted(repo_map.values(), key=lambda r: r.commits, reverse=True)
    return ranked[:limit]


def _extract_orgs(year_data: list[tuple[int, dict]], username: str) -> list[str]:
    """Extract unique organization names from contributed repos."""
    orgs = set()
    for _year, collection in year_data:
        for entry in collection.get("commitContributionsByRepository", []):
            owner = entry["repository"]["nameWithOwner"].split("/")[0]
            if owner.lower() != username.lower():
                orgs.add(owner)
    return sorted(orgs)


def aggregate(
    year_data: list[tuple[int, dict]],
    search_counts: dict,
    languages: dict[str, int],
    lines_added: int,
    lines_deleted: int,
    repos: list[dict],
    user_info: dict,
    username: str,
) -> ProfileStats:
    total_contributions = 0
    total_commits = 0
    total_reviews = 0
    repos_contributed = set()

    for _year, collection in year_data:
        total_contributions += collection.get("contributionCalendar", {}).get("totalContributions", 0)
        total_commits += collection.get("totalCommitContributions", 0)
        total_reviews += collection.get("totalPullRequestReviewContributions", 0)
        repos_contributed.add(collection.get("totalRepositoriesWithContributedCommits", 0))
        for entry in collection.get("commitContributionsByRepository", []):
            repos_contributed.add(entry["repository"]["nameWithOwner"])

    prs_opened = search_counts.get("prs_opened", 0)
    prs_merged = search_counts.get("prs_merged", 0)
    merge_rate = (prs_merged / prs_opened * 100) if prs_opened > 0 else 0.0

    issues_opened = search_counts.get("issues_opened", 0)
    issues_closed = search_counts.get("issues_closed", 0)
    issue_close_rate = (issues_closed / issues_opened * 100) if issues_opened > 0 else 0.0

    repo_count = sum(1 for r in repos_contributed if isinstance(r, str))

    non_fork_repos = [r for r in repos if not r.get("fork")]

    # Activity insights
    active_days, total_days, avg_per_day, best_weekday, weekday_dist, weekend_pct, busiest_month = (
        _compute_activity_insights(year_data)
    )

    # Best year
    yearly = _aggregate_yearly(year_data)
    best_year_stats = max(yearly, key=lambda y: y.total) if yearly else None

    # Account age
    created_at = user_info.get("createdAt", "")
    account_age = 0
    if created_at:
        created_date = date.fromisoformat(created_at[:10])
        account_age = (date.today() - created_date).days // 365

    # Months active (for avg PRs per month)
    months_active = account_age * 12 if account_age > 0 else 1
    avg_prs_per_month = round(prs_opened / months_active, 1)

    reviews_per_pr = round(total_reviews / prs_opened, 1) if prs_opened > 0 else 0.0
    consistency = round(active_days / total_days * 100, 1) if total_days > 0 else 0.0

    orgs = _extract_orgs(year_data, username)

    return ProfileStats(
        total_contributions=total_contributions,
        total_commits=total_commits,
        prs_opened=prs_opened,
        prs_merged=prs_merged,
        merge_rate=round(merge_rate, 1),
        total_reviews=total_reviews,
        issues_opened=issues_opened,
        issues_closed=issues_closed,
        issue_close_rate=round(issue_close_rate, 1),
        lines_added=lines_added,
        lines_deleted=lines_deleted,
        net_lines=lines_added - lines_deleted,
        repos_contributed_to=repo_count,
        total_repos_owned=len(non_fork_repos),
        active_days=active_days,
        total_days_tracked=total_days,
        consistency_pct=consistency,
        avg_contributions_per_active_day=avg_per_day,
        avg_prs_per_month=avg_prs_per_month,
        reviews_per_pr=reviews_per_pr,
        most_productive_weekday=best_weekday,
        weekday_distribution=weekday_dist,
        weekend_pct=weekend_pct,
        best_year=best_year_stats.year if best_year_stats else 0,
        best_year_count=best_year_stats.total if best_year_stats else 0,
        busiest_month=busiest_month,
        orgs_contributed_to=orgs,
        streak=_compute_streaks(year_data),
        languages=languages,
        total_languages=len(languages),
        yearly=yearly,
        top_repos=_aggregate_top_repos(year_data),
        account_created=created_at[:10] if created_at else "",
        account_age_years=account_age,
        followers=user_info.get("followers", {}).get("totalCount", 0),
        following=user_info.get("following", {}).get("totalCount", 0),
    )
