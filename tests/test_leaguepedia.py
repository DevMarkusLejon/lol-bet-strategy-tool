from __future__ import annotations

import json

import pytest

from lol_bet_strategy import leaguepedia
from lol_bet_strategy.leaguepedia import LeaguepediaQuery, fetch_scoreboard_games


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_fetch_scoreboard_games_maps_cargo_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "cargoquery": [
            {
                "title": {
                    "GameId": "LCK_2024_1",
                    "OverviewPage": "LCK/2024 Season/Spring Season",
                    "Team1": "T1",
                    "Team2": "Gen.G",
                    "WinTeam": "T1",
                    "DateTime UTC": "2024-01-17 08:00:00",
                    "N GameInMatch": "1",
                }
            }
        ]
    }

    monkeypatch.setattr(leaguepedia, "urlopen", lambda *_args, **_kwargs: FakeResponse(payload))

    matches = fetch_scoreboard_games(LeaguepediaQuery(start_date="2024-01-01", end_date="2024-02-01"))

    assert len(matches) == 1
    assert matches[0].match_id == "leaguepedia:LCK_2024_1"
    assert matches[0].league == "LCK/2024 Season/Spring Season"
    assert matches[0].winner == "T1"
    assert matches[0].start_time == "2024-01-17T08:00:00Z"


def test_fetch_scoreboard_games_raises_api_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"error": {"info": "You've exceeded your rate limit."}}
    monkeypatch.setattr(leaguepedia, "urlopen", lambda *_args, **_kwargs: FakeResponse(payload))

    with pytest.raises(RuntimeError, match="rate limit"):
        fetch_scoreboard_games(LeaguepediaQuery(start_date="2024-01-01", end_date="2024-02-01"))
