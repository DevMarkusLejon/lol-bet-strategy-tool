from __future__ import annotations

import sqlite3

from .models import HeuristicSignal


def implied_probability(decimal_odds: float) -> float:
    if decimal_odds <= 1:
        raise ValueError("Decimal odds must be greater than 1.0")
    return 1 / decimal_odds


def normalize_two_way_market(odds_a: float, odds_b: float) -> tuple[float, float]:
    raw_a = implied_probability(odds_a)
    raw_b = implied_probability(odds_b)
    overround = raw_a + raw_b
    return raw_a / overround, raw_b / overround


def team_win_rate(
    conn: sqlite3.Connection,
    team: str,
    league: str | None = None,
    before_time: str | None = None,
) -> float | None:
    params: list[str] = [team, team]
    league_clause = ""
    if league:
        league_clause = " and league = ?"
        params.append(league)
    before_clause = ""
    if before_time:
        before_clause = " and start_time < ?"
        params.append(before_time)

    row = conn.execute(
        f"""
        select
            count(*) as games,
            sum(case when winner = ? then 1 else 0 end) as wins
        from matches
        where (team_a = ? or team_b = ?)
            and winner is not null
            {league_clause}
            {before_clause}
        """,
        [team, *params],
    ).fetchone()

    if row["games"] == 0:
        return None
    return row["wins"] / row["games"]


def latest_odds(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        select o.*, m.league, m.start_time as match_start_time
        from odds_snapshots o
        join matches m on m.match_id = o.match_id
        where o.id in (
            select max(id)
            from odds_snapshots
            group by match_id, bookmaker
        )
        order by o.captured_at desc
        """
    ).fetchall()


def find_value_signals(
    conn: sqlite3.Connection,
    min_edge: float = 0.05,
    heuristic_name: str = "historical_team_win_rate",
) -> list[HeuristicSignal]:
    signals: list[HeuristicSignal] = []
    for row in latest_odds(conn):
        market_a, market_b = normalize_two_way_market(row["odds_a"], row["odds_b"])
        candidates = [
            (
                row["team_a"],
                team_win_rate(conn, row["team_a"], row["league"], row["match_start_time"]),
                market_a,
            ),
            (
                row["team_b"],
                team_win_rate(conn, row["team_b"], row["league"], row["match_start_time"]),
                market_b,
            ),
        ]

        for team, estimated, market in candidates:
            if estimated is None:
                continue
            edge = estimated - market
            if edge >= min_edge:
                signals.append(
                    HeuristicSignal(
                        match_id=row["match_id"],
                        team=team,
                        heuristic=heuristic_name,
                        estimated_probability=estimated,
                        market_probability=market,
                        edge=edge,
                        recommendation="consider",
                    )
                )

    return signals
