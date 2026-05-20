from __future__ import annotations

import argparse
from pathlib import Path

from .db import connect, init_db, insert_odds, insert_signals, upsert_matches
from .heuristics import find_value_signals
from .importers import load_historical_matches
from .odds_providers import MockOddsProvider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lol-bets")
    parser.add_argument("--db", default="data/lol_bets.sqlite3", help="SQLite database path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Create or migrate the SQLite database")

    import_history = subparsers.add_parser("import-history", help="Import historical matches from CSV")
    import_history.add_argument("csv_path", type=Path)

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

    if args.command == "import-history":
        matches, odds = load_historical_matches(args.csv_path)
        match_count = upsert_matches(conn, matches)
        odds_count = insert_odds(conn, odds)
        print(f"imported {match_count} matches and {odds_count} odds snapshots")
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


if __name__ == "__main__":
    raise SystemExit(main())
