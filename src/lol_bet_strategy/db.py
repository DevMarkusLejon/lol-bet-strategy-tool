from __future__ import annotations

import os
import re
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from .models import HeuristicSignal, Match, OddsSnapshot

DEFAULT_DB_PATH = Path(os.getenv("LOL_BETS_DB_PATH", "data/lol_bets.sqlite3"))


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists matches (
            match_id text primary key,
            league text not null,
            start_time text not null,
            team_a text not null,
            team_b text not null,
            winner text,
            best_of integer
        );

        create table if not exists odds_snapshots (
            id integer primary key autoincrement,
            match_id text not null,
            provider text not null,
            bookmaker text not null,
            captured_at text not null,
            team_a text not null,
            team_b text not null,
            odds_a real not null,
            odds_b real not null,
            foreign key (match_id) references matches(match_id)
        );

        create table if not exists heuristic_signals (
            id integer primary key autoincrement,
            match_id text not null,
            team text not null,
            heuristic text not null,
            estimated_probability real not null,
            market_probability real not null,
            edge real not null,
            recommendation text not null,
            created_at text not null default current_timestamp,
            foreign key (match_id) references matches(match_id)
        );

        create index if not exists idx_matches_teams on matches(team_a, team_b);
        create index if not exists idx_odds_match on odds_snapshots(match_id, captured_at);
        create unique index if not exists idx_odds_unique_snapshot
            on odds_snapshots(match_id, provider, bookmaker, captured_at, odds_a, odds_b);
        create index if not exists idx_signals_edge on heuristic_signals(edge);
        """
    )
    conn.commit()


def upsert_matches(conn: sqlite3.Connection, matches: Iterable[Match]) -> int:
    rows = list(matches)
    conn.executemany(
        """
        insert into matches (match_id, league, start_time, team_a, team_b, winner, best_of)
        values (?, ?, ?, ?, ?, ?, ?)
        on conflict(match_id) do update set
            league = excluded.league,
            start_time = excluded.start_time,
            team_a = excluded.team_a,
            team_b = excluded.team_b,
            winner = excluded.winner,
            best_of = excluded.best_of
        """,
        [
            (m.match_id, m.league, m.start_time, m.team_a, m.team_b, m.winner, m.best_of)
            for m in rows
        ],
    )
    conn.commit()
    return len(rows)


def insert_odds(conn: sqlite3.Connection, snapshots: Iterable[OddsSnapshot]) -> int:
    rows = list(snapshots)
    before_count = conn.execute("select count(*) as count from odds_snapshots").fetchone()["count"]
    conn.executemany(
        """
        insert or ignore into odds_snapshots (
            match_id, provider, bookmaker, captured_at, team_a, team_b, odds_a, odds_b
        )
        values (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                s.match_id,
                s.provider,
                s.bookmaker,
                s.captured_at,
                s.team_a,
                s.team_b,
                s.odds_a,
                s.odds_b,
            )
            for s in rows
        ],
    )
    conn.commit()
    after_count = conn.execute("select count(*) as count from odds_snapshots").fetchone()["count"]
    return after_count - before_count


def get_match(conn: sqlite3.Connection, match_id: str) -> Match | None:
    row = conn.execute(
        """
        select match_id, league, start_time, team_a, team_b, winner, best_of
        from matches
        where match_id = ?
        """,
        (match_id,),
    ).fetchone()
    if row is None:
        return None
    return Match(
        match_id=row["match_id"],
        league=row["league"],
        start_time=row["start_time"],
        team_a=row["team_a"],
        team_b=row["team_b"],
        winner=row["winner"],
        best_of=row["best_of"],
    )


def latest_odds_snapshots(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        select o.*, m.league, m.start_time
        from odds_snapshots o
        join matches m on m.match_id = o.match_id
        where o.id in (
            select max(id)
            from odds_snapshots
            group by match_id, bookmaker
        )
        order by m.start_time asc, o.bookmaker asc
        """
    ).fetchall()


def upcoming_matches_with_latest_odds(
    conn: sqlite3.Connection,
    now_utc: str,
    limit: int = 25,
    league: str | None = None,
    with_odds_only: bool = False,
) -> list[sqlite3.Row]:
    filters = ["m.start_time > ?"]
    params: list[object] = [now_utc]

    if league:
        filters.append("lower(m.league) like ?")
        params.append(f"%{league.lower()}%")

    if with_odds_only:
        filters.append("o.id is not null")

    params.append(limit)
    return conn.execute(
        f"""
        select
            m.match_id,
            m.league,
            m.start_time,
            m.team_a,
            m.team_b,
            m.best_of,
            o.provider,
            o.bookmaker,
            o.captured_at,
            o.odds_a,
            o.odds_b
        from matches m
        left join odds_snapshots o on o.match_id = m.match_id
            and o.id in (
                select max(id)
                from odds_snapshots
                group by match_id, provider, bookmaker
            )
        where {" and ".join(filters)}
        order by m.start_time asc, m.league asc, m.team_a asc, o.bookmaker asc
        limit ?
        """,
        params,
    ).fetchall()


def enrich_match_best_of_from_schedule(conn: sqlite3.Connection, schedule: Iterable[Match]) -> int:
    existing = conn.execute(
        """
        select match_id, league, start_time, team_a, team_b, best_of
        from matches
        where winner is null
        """
    ).fetchall()
    updated = 0

    for scheduled in schedule:
        if scheduled.best_of is None:
            continue
        match_id = _find_schedule_match(existing, scheduled)
        if match_id is None:
            continue
        cursor = conn.execute(
            """
            update matches
            set best_of = ?
            where match_id = ?
                and (best_of is null or best_of != ?)
            """,
            (scheduled.best_of, match_id, scheduled.best_of),
        )
        updated += cursor.rowcount

    conn.commit()
    return updated


def insert_signals(conn: sqlite3.Connection, signals: Iterable[HeuristicSignal]) -> int:
    rows = list(signals)
    conn.executemany(
        """
        insert into heuristic_signals (
            match_id, team, heuristic, estimated_probability, market_probability, edge,
            recommendation
        )
        values (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                s.match_id,
                s.team,
                s.heuristic,
                s.estimated_probability,
                s.market_probability,
                s.edge,
                s.recommendation,
            )
            for s in rows
        ],
    )
    conn.commit()
    return len(rows)


def database_summary(conn: sqlite3.Connection) -> dict[str, object]:
    total = conn.execute("select count(*) as count from matches").fetchone()["count"]
    odds_total = conn.execute("select count(*) as count from odds_snapshots").fetchone()["count"]
    date_range = conn.execute(
        "select min(start_time) as min_date, max(start_time) as max_date from matches"
    ).fetchone()
    leagues = conn.execute(
        """
        select league, count(*) as count
        from matches
        group by league
        order by count desc, league asc
        """
    ).fetchall()
    return {
        "matches": total,
        "odds_snapshots": odds_total,
        "min_date": date_range["min_date"],
        "max_date": date_range["max_date"],
        "leagues": [(row["league"], row["count"]) for row in leagues],
    }


def _find_schedule_match(rows: list[sqlite3.Row], scheduled: Match) -> str | None:
    candidates = [
        row
        for row in rows
        if row["start_time"] == scheduled.start_time
        and _league_matches(row["league"], scheduled.league)
        and _teams_match(row["team_a"], row["team_b"], scheduled.team_a, scheduled.team_b)
    ]
    if len(candidates) != 1:
        return None
    return candidates[0]["match_id"]


def _league_matches(existing: str, scheduled: str) -> bool:
    existing_norm = _normalize_text(existing)
    scheduled_norm = _normalize_text(scheduled)
    if not existing_norm or not scheduled_norm:
        return False
    if existing_norm in scheduled_norm or scheduled_norm in existing_norm:
        return True
    return bool(set(existing_norm.split()).intersection(scheduled_norm.split()))


def _teams_match(existing_a: str, existing_b: str, scheduled_a: str, scheduled_b: str) -> bool:
    return (
        _team_name_matches(existing_a, scheduled_a)
        and _team_name_matches(existing_b, scheduled_b)
    ) or (
        _team_name_matches(existing_a, scheduled_b)
        and _team_name_matches(existing_b, scheduled_a)
    )


def _team_name_matches(left: str, right: str) -> bool:
    left_norm = _normalize_team(left)
    right_norm = _normalize_team(right)
    if left_norm == right_norm:
        return True
    if left_norm and right_norm and (left_norm in right_norm or right_norm in left_norm):
        return True
    left_tokens = set(left_norm.split())
    right_tokens = set(right_norm.split())
    return bool(left_tokens and right_tokens and left_tokens.intersection(right_tokens))


def _normalize_team(value: str) -> str:
    words = [
        word
        for word in _normalize_text(value).split()
        if word not in {"esports", "esport", "gaming", "team", "kia", "dn"}
    ]
    return " ".join(words)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()
