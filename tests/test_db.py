from __future__ import annotations

from lol_bet_strategy.db import (
    enrich_match_best_of_from_schedule,
    init_db,
    insert_odds,
    upcoming_matches_with_latest_odds,
    update_match_results,
    upsert_matches,
)
from lol_bet_strategy.models import Match, OddsSnapshot


def test_upcoming_matches_with_latest_odds_returns_latest_bookmaker_prices(sqlite_conn) -> None:
    init_db(sqlite_conn)
    upsert_matches(
        sqlite_conn,
        [
            Match("past", "LCK", "2026-05-20T08:00:00Z", "Past A", "Past B", None, 3),
            Match("future", "League of Legends - LCK", "2026-05-22T08:00:00Z", "T1", "Gen.G", None, 3),
            Match("future-no-odds", "LEC", "2026-05-23T08:00:00Z", "G2", "Fnatic", None, 3),
        ],
    )
    insert_odds(
        sqlite_conn,
        [
            OddsSnapshot(
                "future",
                "odds-api-io",
                "Bet365",
                "2026-05-21T08:00:00Z",
                "T1",
                "Gen.G",
                1.90,
                1.90,
            ),
            OddsSnapshot(
                "future",
                "odds-api-io",
                "Bet365",
                "2026-05-21T09:00:00Z",
                "T1",
                "Gen.G",
                1.85,
                1.95,
            ),
        ],
    )

    rows = upcoming_matches_with_latest_odds(
        sqlite_conn,
        now_utc="2026-05-21T00:00:00Z",
        league="LCK",
        with_odds_only=True,
    )

    assert len(rows) == 1
    assert rows[0]["match_id"] == "future"
    assert rows[0]["winner"] is None
    assert rows[0]["bookmaker"] == "Bet365"
    assert rows[0]["odds_a"] == 1.85
    assert rows[0]["odds_b"] == 1.95


def test_enrich_match_best_of_from_schedule_matches_by_time_league_and_teams(sqlite_conn) -> None:
    init_db(sqlite_conn)
    upsert_matches(
        sqlite_conn,
        [
            Match(
                "odds-api-io:1",
                "League of Legends - LCK",
                "2026-05-22T10:00:00Z",
                "kt Rolster",
                "Gen.g Esports",
                None,
                None,
            ),
        ],
    )

    updated = enrich_match_best_of_from_schedule(
        sqlite_conn,
        [
            Match(
                "leaguepedia-schedule:lck-1",
                "LCK 2026 Rounds 1-2",
                "2026-05-22T10:00:00Z",
                "KT Rolster",
                "Gen.G",
                None,
                3,
            )
        ],
    )

    row = sqlite_conn.execute("select best_of from matches where match_id = ?", ("odds-api-io:1",)).fetchone()
    assert updated == 1
    assert row["best_of"] == 3


def test_update_match_results_sets_winner_for_existing_unsettled_match(sqlite_conn) -> None:
    init_db(sqlite_conn)
    upsert_matches(
        sqlite_conn,
        [Match("odds-api-io:1", "LCK", "2026-05-22T10:00:00Z", "T1", "Gen.G", None, 3)],
    )

    updated = update_match_results(
        sqlite_conn,
        [Match("odds-api-io:1", "LCK", "2026-05-22T10:00:00Z", "T1", "Gen.G", "Gen.G", 3)],
    )

    row = sqlite_conn.execute("select winner from matches where match_id = ?", ("odds-api-io:1",)).fetchone()
    assert updated == 1
    assert row["winner"] == "Gen.G"
