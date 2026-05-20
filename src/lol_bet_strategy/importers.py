from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from .models import Match, OddsSnapshot

REQUIRED_HISTORY_COLUMNS = {"match_id", "league", "start_time", "team_a", "team_b", "winner", "best_of"}
ORACLES_ELIXIR_REQUIRED_COLUMNS = {"gameid", "league", "date", "teamname", "result"}


def load_historical_matches(path: Path | str) -> tuple[list[Match], list[OddsSnapshot]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV file has no header row")

        missing = REQUIRED_HISTORY_COLUMNS.difference(reader.fieldnames)
        if missing:
            raise ValueError(f"CSV missing required columns: {', '.join(sorted(missing))}")

        matches: list[Match] = []
        odds: list[OddsSnapshot] = []
        for row in reader:
            match = Match(
                match_id=row["match_id"],
                league=row["league"],
                start_time=row["start_time"],
                team_a=row["team_a"],
                team_b=row["team_b"],
                winner=row["winner"] or None,
                best_of=int(row["best_of"]) if row["best_of"] else None,
            )
            matches.append(match)

            closing_a = row.get("closing_odds_a", "")
            closing_b = row.get("closing_odds_b", "")
            if closing_a and closing_b:
                odds.append(
                    OddsSnapshot(
                        match_id=match.match_id,
                        provider="historical_csv",
                        bookmaker="closing_market",
                        captured_at=match.start_time,
                        team_a=match.team_a,
                        team_b=match.team_b,
                        odds_a=float(closing_a),
                        odds_b=float(closing_b),
                    )
                )

        return matches, odds


def load_oracles_elixir_matches(path: Path | str) -> list[Match]:
    """Load game-level match results from an Oracle's Elixir export.

    Oracle's Elixir files are row-per-participant. We only need the two team rows
    for baseline match history, so this importer ignores player rows.
    """
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV file has no header row")

        fieldnames = {name.lower().strip() for name in reader.fieldnames}
        missing = ORACLES_ELIXIR_REQUIRED_COLUMNS.difference(fieldnames)
        if missing:
            raise ValueError(f"Oracle's Elixir CSV missing columns: {', '.join(sorted(missing))}")

        games: dict[str, list[dict[str, str]]] = defaultdict(list)
        for raw_row in reader:
            row = {key.lower().strip(): value for key, value in raw_row.items() if key is not None}
            if not _is_oracles_elixir_team_row(row):
                continue
            games[row["gameid"]].append(row)

    matches: list[Match] = []
    for game_id, rows in games.items():
        if len(rows) != 2:
            continue

        rows = sorted(rows, key=_oracles_elixir_side_sort_key)
        team_a = rows[0]["teamname"]
        team_b = rows[1]["teamname"]
        winner = next((row["teamname"] for row in rows if row.get("result") == "1"), None)

        matches.append(
            Match(
                match_id=game_id,
                league=rows[0]["league"],
                start_time=_normalize_utc_datetime(rows[0]["date"]),
                team_a=team_a,
                team_b=team_b,
                winner=winner,
                best_of=1,
            )
        )

    return matches


def _is_oracles_elixir_team_row(row: dict[str, str]) -> bool:
    position = row.get("position", "").lower()
    participant_id = row.get("participantid", "")
    return position == "team" or participant_id in {"100", "200"}


def _oracles_elixir_side_sort_key(row: dict[str, str]) -> tuple[int, str]:
    side = row.get("side", "").lower()
    if side == "blue":
        return (0, row["teamname"])
    if side == "red":
        return (1, row["teamname"])
    participant_id = row.get("participantid", "")
    if participant_id == "100":
        return (0, row["teamname"])
    if participant_id == "200":
        return (1, row["teamname"])
    return (2, row["teamname"])


def _normalize_utc_datetime(value: str) -> str:
    clean = value.strip()
    if not clean:
        return clean
    if "T" not in clean and " " in clean:
        clean = clean.replace(" ", "T", 1)
    if clean.endswith("Z") or "+" in clean[10:] or clean[10:].count("-") > 0:
        return clean
    return f"{clean}Z"
