from __future__ import annotations

from pathlib import Path

from lol_bet_strategy.importers import load_odds_snapshots_csv, load_oracles_elixir_matches


def test_load_oracles_elixir_matches_reads_team_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "oracle.csv"
    csv_path.write_text(
        "\n".join(
            [
                "gameid,league,date,participantid,side,position,teamname,result",
                "game-1,LCK,2024-01-17 08:00:00,100,Blue,team,T1,1",
                "game-1,LCK,2024-01-17 08:00:00,200,Red,team,Gen.G,0",
                "game-1,LCK,2024-01-17 08:00:00,1,Blue,top,T1,1",
            ]
        ),
        encoding="utf-8",
    )

    matches = load_oracles_elixir_matches(csv_path)

    assert len(matches) == 1
    assert matches[0].match_id == "game-1"
    assert matches[0].team_a == "T1"
    assert matches[0].team_b == "Gen.G"
    assert matches[0].winner == "T1"
    assert matches[0].start_time == "2024-01-17T08:00:00Z"


def test_load_oracles_elixir_matches_reads_real_export_column_names(tmp_path: Path) -> None:
    csv_path = tmp_path / "oracle-real.csv"
    csv_path.write_text(
        "\n".join(
            [
                "gameid,league,date,playerid,side,position,player,team,result",
                "5655-7249,LPL,2020-01-13 09:22:22,100,Blue,team,Invictus Gaming,Invictus Gaming,1",
                "5655-7249,LPL,2020-01-13 09:22:22,200,Red,team,FunPlus Phoenix,FunPlus Phoenix,0",
            ]
        ),
        encoding="utf-8",
    )

    matches = load_oracles_elixir_matches(csv_path)

    assert len(matches) == 1
    assert matches[0].team_a == "Invictus Gaming"
    assert matches[0].team_b == "FunPlus Phoenix"
    assert matches[0].winner == "Invictus Gaming"


def test_load_odds_snapshots_csv_reads_match_and_snapshot_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "odds.csv"
    csv_path.write_text(
        "\n".join(
            [
                "match_id,league,start_time,team_a,team_b,best_of,provider,bookmaker,captured_at,odds_a,odds_b",
                "lck-2026-001,LCK,2026-06-01T17:00:00Z,T1,Gen.G,3,manual,pinnacle,2026-05-20T12:00:00Z,1.91,1.91",
            ]
        ),
        encoding="utf-8",
    )

    matches, odds = load_odds_snapshots_csv(csv_path)

    assert len(matches) == 1
    assert matches[0].match_id == "lck-2026-001"
    assert matches[0].best_of == 3
    assert len(odds) == 1
    assert odds[0].bookmaker == "pinnacle"
    assert odds[0].odds_a == 1.91
    assert odds[0].odds_b == 1.91
