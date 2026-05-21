from __future__ import annotations

import argparse
import time
from datetime import UTC, datetime
from pathlib import Path

from .db import (
    connect,
    database_summary,
    enrich_match_best_of_from_schedule,
    get_match,
    init_db,
    insert_odds,
    insert_signals,
    latest_odds_snapshots,
    upcoming_matches_with_latest_odds,
    upsert_matches,
)
from .heuristics import find_value_signals
from .importers import load_historical_matches, load_odds_snapshots_csv, load_oracles_elixir_matches
from .leaguepedia import LeaguepediaQuery, fetch_match_schedule, fetch_scoreboard_games
from .models import Match, OddsSnapshot
from .odds_providers import MockOddsProvider, OddsApiIoProvider

PROVIDER_CHOICES = ["mock", "odds-api-io"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lol-bets")
    parser.add_argument("--db", default="data/lol_bets.sqlite3", help="SQLite database path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Create or migrate the SQLite database")
    subparsers.add_parser("db-summary", help="Print a short summary of imported data")
    subparsers.add_parser("latest-odds", help="Print latest odds per match and bookmaker")

    upcoming = subparsers.add_parser("upcoming-matches", help="Print upcoming matches and latest odds")
    upcoming.add_argument("--league", help="Filter by league text, for example LCK or LEC")
    upcoming.add_argument("--limit", type=_positive_int_arg, default=25)
    upcoming.add_argument("--with-odds-only", action="store_true")
    upcoming.add_argument(
        "--now",
        help="Override current UTC time for testing, for example 2026-05-21T00:00:00Z",
    )

    provider_leagues = subparsers.add_parser(
        "provider-leagues",
        help="List provider leagues for configuring odds collection",
    )
    provider_leagues.add_argument("--provider", default="odds-api-io", choices=["odds-api-io"])
    provider_leagues.add_argument("--contains", default="League of Legends")

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

    enrich_schedule = subparsers.add_parser(
        "enrich-match-format",
        help="Fill best-of values for upcoming matches from Leaguepedia MatchSchedule",
    )
    enrich_schedule.add_argument("--start-date", required=True)
    enrich_schedule.add_argument("--end-date", required=True)
    enrich_schedule.add_argument("--league", help="Overview page filter, for example LCK or LEC")
    enrich_schedule.add_argument("--limit", type=int, default=500)

    collect = subparsers.add_parser("collect-odds", help="Collect latest odds from a provider")
    collect.add_argument("--provider", default="mock", choices=PROVIDER_CHOICES)
    collect.add_argument("--league", help="Provider league slug, for example league-of-legends-lck")
    collect.add_argument("--bookmakers", help="Comma-separated bookmaker names, for example Bet365,Unibet")
    collect.add_argument("--event-limit", type=_positive_int_arg, default=25)

    collect_loop = subparsers.add_parser("collect-loop", help="Collect odds repeatedly from a provider")
    collect_loop.add_argument("--provider", default="mock", choices=PROVIDER_CHOICES)
    collect_loop.add_argument("--league", help="Provider league slug, for example league-of-legends-lck")
    collect_loop.add_argument("--bookmakers", help="Comma-separated bookmaker names, for example Bet365,Unibet")
    collect_loop.add_argument("--event-limit", type=_positive_int_arg, default=25)
    collect_loop.add_argument("--interval-seconds", type=_positive_int_arg, default=900)
    collect_loop.add_argument(
        "--max-runs",
        type=_positive_int_arg,
        help="Stop after this many captures. Omit to run until interrupted.",
    )

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

    if args.command == "upcoming-matches":
        now_utc = args.now or _now_utc_iso()
        rows = upcoming_matches_with_latest_odds(
            conn,
            now_utc=now_utc,
            limit=args.limit,
            league=args.league,
            with_odds_only=args.with_odds_only,
        )
        for row in rows:
            best_of = f"bo{row['best_of']}" if row["best_of"] else "bo?"
            start_time = _format_match_time(row["start_time"])
            base = (
                f"{start_time} | {row['league']} | {best_of} | "
                f"{row['team_a']} vs {row['team_b']} | {row['match_id']}"
            )
            if row["bookmaker"]:
                print(
                    f"{base} | {row['bookmaker']} "
                    f"{row['team_a']}={row['odds_a']:.2f} {row['team_b']}={row['odds_b']:.2f} "
                    f"captured={row['captured_at']}"
                )
            else:
                print(f"{base} | no odds yet")
        print(f"upcoming rows: {len(rows)}")
        return 0

    if args.command == "provider-leagues":
        provider = _provider_from_name(args.provider)
        leagues = provider.fetch_leagues()
        needle = args.contains.lower() if args.contains else ""
        for league in leagues:
            name = league.get("name", "")
            slug = league.get("slug", "")
            if needle and needle not in name.lower() and needle not in slug.lower():
                continue
            print(f"{slug}: {name} ({league.get('eventsCount', 0)} events)")
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
        try:
            matches = fetch_scoreboard_games(
                LeaguepediaQuery(
                    start_date=args.start_date,
                    end_date=args.end_date,
                    league=args.league,
                    limit=args.limit,
                )
            )
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc
        match_count = upsert_matches(conn, matches)
        print(f"fetched and imported {match_count} Leaguepedia games")
        return 0

    if args.command == "enrich-match-format":
        try:
            schedule = fetch_match_schedule(
                LeaguepediaQuery(
                    start_date=args.start_date,
                    end_date=args.end_date,
                    league=args.league,
                    limit=args.limit,
                )
            )
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc
        updated = enrich_match_best_of_from_schedule(conn, schedule)
        print(f"updated best-of for {updated} existing matches from {len(schedule)} schedule rows")
        return 0

    if args.command == "collect-odds":
        try:
            match_count, odds_count, provider_name = _collect_provider_odds(conn, args)
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from exc
        print(f"collected {odds_count} odds snapshots for {match_count} matches from {provider_name}")
        return 0

    if args.command == "collect-loop":
        run_count = 0
        while args.max_runs is None or run_count < args.max_runs:
            run_count += 1
            captured_at = datetime.now(UTC).isoformat()
            try:
                match_count, odds_count, provider_name = _collect_provider_odds(conn, args)
            except RuntimeError as exc:
                raise SystemExit(str(exc)) from exc
            print(
                f"[{captured_at}] run={run_count} provider={provider_name} "
                f"matches={match_count} odds_snapshots={odds_count}",
                flush=True,
            )
            if args.max_runs is not None and run_count >= args.max_runs:
                break
            time.sleep(args.interval_seconds)
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


def _positive_int_arg(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return number


def _collect_provider_odds(conn, args: argparse.Namespace) -> tuple[int, int, str]:
    provider = _provider_from_name(
        args.provider,
        bookmakers=_split_cli_csv(getattr(args, "bookmakers", None)),
        league=getattr(args, "league", None),
        event_limit=getattr(args, "event_limit", 25),
    )
    matches, odds = provider.fetch_upcoming()
    match_count = upsert_matches(conn, matches)
    odds_count = insert_odds(conn, odds)
    return match_count, odds_count, provider.name


def _provider_from_name(
    provider_name: str,
    bookmakers: list[str] | None = None,
    league: str | None = None,
    event_limit: int = 25,
):
    if provider_name == "mock":
        return MockOddsProvider()
    if provider_name == "odds-api-io":
        return OddsApiIoProvider(bookmakers=bookmakers, league=league, event_limit=event_limit)
    raise ValueError(f"Unknown provider: {provider_name}")


def _split_cli_csv(value: str | None) -> list[str] | None:
    if value is None:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _now_utc_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _format_match_time(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    utc_time = parsed.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    local_time = parsed.astimezone().strftime("%H:%M local")
    return f"{utc_time} ({local_time})"


if __name__ == "__main__":
    raise SystemExit(main())
