from __future__ import annotations

from pathlib import Path

from lol_bet_strategy.importers import load_oracles_elixir_matches


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
