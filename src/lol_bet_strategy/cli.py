from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from .db import (
    connect,
    database_summary,
    get_match,
    init_db,
    insert_odds,
    insert_signals,
    latest_odds_snapshots,
    upsert_matches,
)
from .heuristics import find_value_signals
from .importers import load_historical_matches, load_odds_snapshots_csv, load_oracles_elixir_matches
from .leaguepedia import LeaguepediaQuery, fetch_scoreboard_games
from .models import Match, OddsSnapshot
from .odds_providers import MockOddsProvider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lol-bets")
    parser.add_argument("--db", default="data/lol_bets.sqlite3", help="SQLite database path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Create or migrate the SQLite database")
    subparsers.add_parser("db-summary", help="Print a short summary of imported data")
    subparsers.add_parser("latest-odds", help="Print latest odds per match and bookmaker")

    import_history = subparsers.add_parser("import-history", help="Import historical matches from CSV")
    import_history.add_argument("csv_path", type=Path)

    record_match = subparsers.add_parser("record-match", help="Create or update one match")
    record_match.add_argument("--match-id", required=True)
    record_match.add_argument("--league", required=True)
    record_match.add_argument("--start-time", required=True, help="UTC ISO time, for example 2026-06-01T17:00:00Z")
    record_match.add_argument("--team-a", required=True)
    record_match.add_argument("--team-b", required=True)
    record_match.add_argument("--best-of", type=int)

    record_odds = subparsers.add_parser("record-odds", help="Append one odds snapshot")
    record_odds.add_argument("--match-id", required=True)
    record_odds.add_argument("--provider", default="manual")
    record_odds.add_argument("--bookmaker", required=True)
    record_odds.add_argument("--odds-a", type=_decimal_odds_arg, required=True)
    record_odds.add_argument("--odds-b", type=_decimal_odds_arg, required=True)
    record_odds.add_argument("--captured-at", help="UTC ISO time. Defaults to now.")
    record_odds.add_argument("--league", help="Required if match-id is not already known")
    record_odds.add_argument("--start-time", help="Required if match-id is not already known")
    record_odds.add_argument("--team-a", help="Required if match-id is not already known")
    record_odds.add_argument("--team-b", help="Required if match-id is not already known")
    record_odds.add_argument("--best-of", type=int)

    import_odds = subparsers.add_parser("import-odds-csv", help="Append odds snapshots from CSV")
    import_odds.add_argument("csv_path", type=Path)

    import_oe = subparsers.add_parser(
        "import-oracles-elixir",
        help="Import historical game results from an Oracle's Elixir CSV export",
    )
    import_oe.add_argument("csv_path", type=Path)

    leaguepedia = subparsers.add_parser(
        "fetch-leaguepedia-games",
        help="Fetch completed historical games from Leaguepedia Cargo",
    )
    leaguepedia.add_argument(
        "--start-date",
        required=True,
        help="Inclusive UTC date, for example 2024-01-01",
    )
    leaguepedia.add_argument(
        "--end-date",
        required=True,
        help="Exclusive UTC date, for example 2024-02-01",
    )
    leaguepedia.add_argument("--league", help="Overview page filter, for example LCK or LEC")
    leaguepedia.add_argument("--limit", type=int, default=500)

    collect = subparsers.add_parser("collect-odds", help="Collect latest odds from a provider")
    collect.add_argument("--provider", default="mock", choices=["mock"])

    run = subparsers.add_parser("run-heuristics", help="Run strategy heuristics over stored odds")
    run.add_argument("--min-edge", type=float, default=0.05)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    conn = connect(args.db)
    init_db(conn)

    if args.command == "init-db":
        print(f"initialized {args.db}")
        return 0

    if args.command == "db-summary":
        summary = database_summary(conn)
        print(f"matches: {summary['matches']}")
        print(f"odds snapshots: {summary['odds_snapshots']}")
        print(f"date range: {summary['min_date']} to {summary['max_date']}")
        print("leagues:")
        for league, count in summary["leagues"]:
            print(f"  {league}: {count}")
        return 0

    if args.command == "latest-odds":
        rows = latest_odds_snapshots(conn)
        for row in rows:
            print(
                f"{row['match_id']} {row['league']} {row['start_time']} "
                f"{row['bookmaker']} {row['team_a']}={row['odds_a']:.2f} "
                f"{row['team_b']}={row['odds_b']:.2f} captured={row['captured_at']}"
            )
        print(f"latest odds rows: {len(rows)}")
        return 0

    if args.command == "import-history":
        matches, odds = load_historical_matches(args.csv_path)
        match_count = upsert_matches(conn, matches)
        odds_count = insert_odds(conn, odds)
        print(f"imported {match_count} matches and {odds_count} odds snapshots")
        return 0

    if args.command == "record-match":
        match = Match(
            match_id=args.match_id,
            league=args.league,
            start_time=args.start_time,
            team_a=args.team_a,
            team_b=args.team_b,
            winner=None,
            best_of=args.best_of,
        )
        upsert_matches(conn, [match])
        print(f"recorded match {match.match_id}: {match.team_a} vs {match.team_b}")
        return 0

    if args.command == "record-odds":
        match = _resolve_match_for_odds(conn, args)
        snapshot = OddsSnapshot(
            match_id=match.match_id,
            provider=args.provider,
            bookmaker=args.bookmaker,
            captured_at=args.captured_at or datetime.now(UTC).isoformat(),
            team_a=match.team_a,
            team_b=match.team_b,
            odds_a=args.odds_a,
            odds_b=args.odds_b,
        )
        insert_odds(conn, [snapshot])
        print(
            f"recorded odds for {match.match_id} at {snapshot.bookmaker}: "
            f"{match.team_a}={snapshot.odds_a:.2f}, {match.team_b}={snapshot.odds_b:.2f}"
        )
        return 0

    if args.command == "import-odds-csv":
        matches, odds = load_odds_snapshots_csv(args.csv_path)
        match_count = upsert_matches(conn, matches)
        odds_count = insert_odds(conn, odds)
        print(f"imported {odds_count} odds snapshots for {match_count} match rows")
        return 0

    if args.command == "import-oracles-elixir":
        matches = load_oracles_elixir_matches(args.csv_path)
        match_count = upsert_matches(conn, matches)
        print(f"imported {match_count} Oracle's Elixir games")
        return 0

    if args.command == "fetch-leaguepedia-games":
        matches = fetch_scoreboard_games(
            LeaguepediaQuery(
                start_date=args.start_date,
                end_date=args.end_date,
                league=args.league,
                limit=args.limit,
            )
        )
        match_count = upsert_matches(conn, matches)
        print(f"fetched and imported {match_count} Leaguepedia games")
        return 0

    if args.command == "collect-odds":
        provider = MockOddsProvider()
        matches, odds = provider.fetch_upcoming()
        match_count = upsert_matches(conn, matches)
        odds_count = insert_odds(conn, odds)
        print(f"collected {odds_count} odds snapshots for {match_count} matches from {provider.name}")
        return 0

    if args.command == "run-heuristics":
        signals = find_value_signals(conn, min_edge=args.min_edge)
        inserted = insert_signals(conn, signals)
        for signal in signals:
            print(
                f"{signal.match_id}: {signal.team} edge={signal.edge:.3f} "
                f"est={signal.estimated_probability:.3f} market={signal.market_probability:.3f}"
            )
        print(f"stored {inserted} heuristic signals")
        return 0

    return 1


def _resolve_match_for_odds(conn, args: argparse.Namespace) -> Match:
    match = get_match(conn, args.match_id)
    if match is not None:
        return match

    missing = [
        name
        for name in ("league", "start_time", "team_a", "team_b")
        if getattr(args, name.replace("-", "_"), None) is None
    ]
    if missing:
        raise SystemExit(
            "match-id is not known yet; provide --league, --start-time, --team-a, and --team-b"
        )

    match = Match(
        match_id=args.match_id,
        league=args.league,
        start_time=args.start_time,
        team_a=args.team_a,
        team_b=args.team_b,
        winner=None,
        best_of=args.best_of,
    )
    upsert_matches(conn, [match])
    return match


def _decimal_odds_arg(value: str) -> float:
    odds = float(value)
    if odds <= 1:
        raise argparse.ArgumentTypeError("decimal odds must be greater than 1.0")
    return odds


if __name__ == "__main__":
    raise SystemExit(main())
