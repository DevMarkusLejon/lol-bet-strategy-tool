from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import Match

LEAGUEPEDIA_API_URL = "https://lol.fandom.com/api.php"


@dataclass(frozen=True)
class LeaguepediaQuery:
    start_date: str | None = None
    end_date: str | None = None
    league: str | None = None
    limit: int = 500


def fetch_scoreboard_games(query: LeaguepediaQuery) -> list[Match]:
    """Fetch completed game results from Leaguepedia's Cargo ScoreboardGames table."""
    params = {
        "action": "cargoquery",
        "format": "json",
        "tables": "ScoreboardGames",
        "fields": ",".join(
            [
                "GameId",
                "OverviewPage",
                "Team1",
                "Team2",
                "WinTeam",
                "DateTime_UTC",
                "N_GameInMatch",
            ]
        ),
        "where": _build_where(query),
        "order_by": "DateTime_UTC ASC",
        "limit": str(query.limit),
    }
    request = Request(
        f"{LEAGUEPEDIA_API_URL}?{urlencode(params)}",
        headers={"User-Agent": "lol-bet-strategy-tool/0.1"},
    )

    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if "error" in payload:
        message = payload["error"].get("info", "Leaguepedia API request failed")
        raise RuntimeError(message)

    return [_leaguepedia_row_to_match(item["title"]) for item in payload.get("cargoquery", [])]


def fetch_match_schedule(query: LeaguepediaQuery) -> list[Match]:
    """Fetch scheduled matches from Leaguepedia's Cargo MatchSchedule table."""
    params = {
        "action": "cargoquery",
        "format": "json",
        "tables": "MatchSchedule",
        "fields": ",".join(
            [
                "MatchId",
                "OverviewPage",
                "Team1",
                "Team2",
                "DateTime_UTC",
                "BestOf",
            ]
        ),
        "where": _build_schedule_where(query),
        "order_by": "DateTime_UTC ASC",
        "limit": str(query.limit),
    }
    request = Request(
        f"{LEAGUEPEDIA_API_URL}?{urlencode(params)}",
        headers={"User-Agent": "lol-bet-strategy-tool/0.1"},
    )

    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if "error" in payload:
        message = payload["error"].get("info", "Leaguepedia API request failed")
        raise RuntimeError(message)

    return [_leaguepedia_schedule_row_to_match(item["title"]) for item in payload.get("cargoquery", [])]


def _build_where(query: LeaguepediaQuery) -> str:
    clauses = ["WinTeam IS NOT NULL", "GameId IS NOT NULL"]
    if query.start_date:
        clauses.append(f'DateTime_UTC >= "{_normalize_cargo_datetime(query.start_date)}"')
    if query.end_date:
        clauses.append(f'DateTime_UTC < "{_normalize_cargo_datetime(query.end_date)}"')
    if query.league:
        clauses.append(f'OverviewPage LIKE "%{_escape_like(query.league)}%"')
    return " AND ".join(clauses)


def _build_schedule_where(query: LeaguepediaQuery) -> str:
    clauses = ["MatchId IS NOT NULL", "DateTime_UTC IS NOT NULL"]
    if query.start_date:
        clauses.append(f'DateTime_UTC >= "{_normalize_cargo_datetime(query.start_date)}"')
    if query.end_date:
        clauses.append(f'DateTime_UTC < "{_normalize_cargo_datetime(query.end_date)}"')
    if query.league:
        clauses.append(f'OverviewPage LIKE "%{_escape_like(query.league)}%"')
    return " AND ".join(clauses)


def _leaguepedia_row_to_match(row: dict[str, str]) -> Match:
    game_id = row.get("GameId") or _fallback_game_id(row)
    return Match(
        match_id=f"leaguepedia:{game_id}",
        league=row.get("OverviewPage", ""),
        start_time=_normalize_leaguepedia_datetime(row.get("DateTime UTC", "")),
        team_a=row.get("Team1", ""),
        team_b=row.get("Team2", ""),
        winner=row.get("WinTeam") or None,
        best_of=1,
    )


def _leaguepedia_schedule_row_to_match(row: dict[str, str]) -> Match:
    match_id = row.get("MatchId") or _fallback_schedule_match_id(row)
    best_of = row.get("BestOf")
    return Match(
        match_id=f"leaguepedia-schedule:{match_id}",
        league=row.get("OverviewPage", ""),
        start_time=_normalize_leaguepedia_datetime(row.get("DateTime UTC", "")),
        team_a=row.get("Team1", ""),
        team_b=row.get("Team2", ""),
        winner=None,
        best_of=int(best_of) if best_of else None,
    )


def _normalize_leaguepedia_datetime(value: str) -> str:
    clean = value.strip()
    if not clean:
        return clean
    if "T" not in clean and " " in clean:
        clean = clean.replace(" ", "T", 1)
    if clean.endswith("Z"):
        return clean
    return f"{clean}Z"


def _normalize_cargo_datetime(value: str) -> str:
    clean = value.strip().replace("T", " ").removesuffix("Z")
    if len(clean) == 10:
        return f"{clean} 00:00:00"
    return clean


def _fallback_game_id(row: dict[str, str]) -> str:
    parts = [
        row.get("OverviewPage", ""),
        row.get("DateTime UTC", ""),
        row.get("Team1", ""),
        row.get("Team2", ""),
        row.get("N GameInMatch", ""),
    ]
    return ":".join(part.replace(" ", "-") for part in parts if part)


def _fallback_schedule_match_id(row: dict[str, str]) -> str:
    parts = [
        row.get("OverviewPage", ""),
        row.get("DateTime UTC", ""),
        row.get("Team1", ""),
        row.get("Team2", ""),
    ]
    return ":".join(part.replace(" ", "-") for part in parts if part)


def _escape_like(value: str) -> str:
    return value.replace('"', '\\"').replace("%", "\\%").replace("_", "\\_")
