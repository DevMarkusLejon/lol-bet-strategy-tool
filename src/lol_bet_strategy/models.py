from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Match:
    match_id: str
    league: str
    start_time: str
    team_a: str
    team_b: str
    winner: str | None = None
    best_of: int | None = None


@dataclass(frozen=True)
class OddsSnapshot:
    match_id: str
    provider: str
    bookmaker: str
    captured_at: str
    team_a: str
    team_b: str
    odds_a: float
    odds_b: float


@dataclass(frozen=True)
class HeuristicSignal:
    match_id: str
    team: str
    heuristic: str
    estimated_probability: float
    market_probability: float
    edge: float
    recommendation: str
