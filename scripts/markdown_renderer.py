from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader

from .config import END_YEAR, START_YEAR
from .stats_aggregator import ProfileStats, WEEKDAY_NAMES


# ── Jinja2 filters ──────────────────────────────────────────────────

def _fmt_number(value: int | float) -> str:
    if isinstance(value, float):
        return f"{value:,.1f}"
    return f"{value:,}"


def _fmt_compact(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def _shields_badge(label: str, value: str, color: str, logo: str = "") -> str:
    label_enc = quote(label.replace("-", "--").replace("_", "__"), safe="")
    value_enc = quote(str(value).replace("-", "--").replace("_", "__"), safe="")
    url = f"https://img.shields.io/badge/{label_enc}-{value_enc}-{color}?style=for-the-badge"
    if logo:
        url += f"&logo={quote(logo)}&logoColor=white"
    return url


# ── Chart builders ───────────────────────────────────────────────────

def _build_language_table(languages: dict[str, int], top_n: int = 8) -> str:
    if not languages:
        return "_No language data available._"

    sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)[:top_n]
    total = sum(v for _, v in sorted_langs)
    max_bytes = sorted_langs[0][1]

    lines = []
    for name, count in sorted_langs:
        pct = count / total * 100
        filled = round(count / max_bytes * 25)
        bar = "█" * filled + "░" * (25 - filled)
        lines.append(f"| `{name}` | `{bar}` | **{pct:.1f}%** |")

    header = "| Language | Distribution | % |"
    sep = "|----------|-------------|--:|"
    return "\n".join([header, sep] + lines)


def _build_year_table(yearly: list) -> str:
    if not yearly:
        return ""

    max_total = max(y.total for y in yearly) if yearly else 1

    lines = []
    lines.append("| Year | Commits | PRs | Issues | Reviews | Total | Activity |")
    lines.append("|:----:|--------:|----:|-------:|--------:|------:|----------|")

    for ys in yearly:
        bar_len = round(ys.total / max_total * 15) if max_total > 0 else 0
        bar = "▓" * bar_len + "░" * (15 - bar_len)
        lines.append(
            f"| **{ys.year}** | {ys.commits:,} | {ys.prs:,} | {ys.issues:,} "
            f"| {ys.reviews:,} | **{ys.total:,}** | `{bar}` |"
        )

    tc = sum(y.commits for y in yearly)
    tp = sum(y.prs for y in yearly)
    ti = sum(y.issues for y in yearly)
    tr = sum(y.reviews for y in yearly)
    tt = sum(y.total for y in yearly)
    lines.append(f"| **Total** | **{tc:,}** | **{tp:,}** | **{ti:,}** | **{tr:,}** | **{tt:,}** | |")

    return "\n".join(lines)


def _build_weekday_chart(weekday_dist: dict[str, int]) -> str:
    if not weekday_dist:
        return ""

    max_val = max(weekday_dist.values()) if weekday_dist else 1
    short_names = {"Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed",
                   "Thursday": "Thu", "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun"}

    lines = []
    for day_name in WEEKDAY_NAMES:
        count = weekday_dist.get(day_name, 0)
        bar_len = round(count / max_val * 20) if max_val > 0 else 0
        bar = "█" * bar_len + "░" * (20 - bar_len)
        short = short_names[day_name]
        lines.append(f"{short}  {bar}  {count:,}")
    return "\n".join(lines)


# ── Render ───────────────────────────────────────────────────────────

def render(stats: ProfileStats) -> str:
    templates_dir = Path(__file__).resolve().parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)), keep_trailing_newline=True)
    env.filters["fmt_number"] = _fmt_number
    env.filters["fmt_compact"] = _fmt_compact
    env.filters["shields_badge"] = _shields_badge

    template = env.get_template("README.template.md")

    return template.render(
        stats=stats,
        start_year=START_YEAR,
        end_year=END_YEAR,
        language_table=_build_language_table(stats.languages),
        year_table=_build_year_table(stats.yearly),
        weekday_chart=_build_weekday_chart(stats.weekday_distribution),
        shields_badge=_shields_badge,
        updated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )
