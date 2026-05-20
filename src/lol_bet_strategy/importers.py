from __future__ import annotations

import csv
from pathlib import Path

from .models import Match, OddsSnapshot

REQUIRED_HISTORY_COLUMNS = {"match_id", "league", "start_time", "team_a", "team_b", "winner", "best_of"}


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
