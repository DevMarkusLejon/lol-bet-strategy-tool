from __future__ import annotations

from lol_bet_strategy.db import init_db, insert_odds, upsert_matches
from lol_bet_strategy.heuristics import find_value_signals, implied_probability, normalize_two_way_market
from lol_bet_strategy.models import Match, OddsSnapshot


def test_implied_probability_from_decimal_odds() -> None:
    assert implied_probability(2.0) == 0.5


def test_normalize_two_way_market_removes_overround() -> None:
    market_a, market_b = normalize_two_way_market(1.91, 1.91)
    assert round(market_a, 3) == 0.5
    assert round(market_b, 3) == 0.5


def test_find_value_signals_uses_historical_team_win_rate(sqlite_conn) -> None:
    init_db(sqlite_conn)
    upsert_matches(
        sqlite_conn,
        [
            Match("past-1", "LCK", "2026-01-01T10:00:00Z", "T1", "Gen.G", "T1", 3),
            Match("past-2", "LCK", "2026-01-02T10:00:00Z", "T1", "DK", "T1", 3),
            Match("future-1", "LCK", "2026-01-03T10:00:00Z", "T1", "Gen.G", None, 3),
        ],
    )
    insert_odds(
        sqlite_conn,
        [
            OddsSnapshot(
                "future-1",
                "mock",
                "mockbook",
                "2026-01-02T12:00:00Z",
                "T1",
                "Gen.G",
                2.20,
                1.70,
            )
        ],
    )

    signals = find_value_signals(sqlite_conn, min_edge=0.05)

    assert len(signals) == 1
    assert signals[0].team == "T1"
    assert signals[0].recommendation == "consider"


def test_find_value_signals_does_not_use_target_match_result(sqlite_conn) -> None:
    init_db(sqlite_conn)
    upsert_matches(
        sqlite_conn,
        [
            Match("target", "LCK", "2026-01-01T10:00:00Z", "T1", "Gen.G", "T1", 3),
        ],
    )
    insert_odds(
        sqlite_conn,
        [
            OddsSnapshot(
                "target",
                "historical_csv",
                "closing_market",
                "2026-01-01T10:00:00Z",
                "T1",
                "Gen.G",
                2.20,
                1.70,
            )
        ],
    )

    assert find_value_signals(sqlite_conn, min_edge=0.01) == []
