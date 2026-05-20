from __future__ import annotations

import json

from lol_bet_strategy.odds_providers import odds_api_io
from lol_bet_strategy.odds_providers.odds_api_io import OddsApiIoProvider


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_odds_api_io_provider_fetches_events_and_moneyline_odds(monkeypatch) -> None:
    responses = [
        [
            {
                "id": 123,
                "league": {"name": "League of Legends Champions Korea", "slug": "lck"},
                "home": "T1",
                "away": "Gen.G",
                "date": "2026-06-01T17:00:00Z",
                "status": "pending",
            }
        ],
        {
            "id": 123,
            "home": "T1",
            "away": "Gen.G",
            "date": "2026-06-01T17:00:00Z",
            "bookmakers": {
                "Bet365": [
                    {
                        "name": "ML",
                        "odds": [{"home": "1.91", "away": "1.91"}],
                        "updatedAt": "2026-05-20T12:00:00Z",
                    }
                ],
                "BookWithoutMoneyline": [{"name": "Totals", "odds": [{"over": "1.9"}]}],
            },
        },
    ]

    def fake_urlopen(request, timeout):
        assert timeout == 30
        return FakeResponse(responses.pop(0))

    monkeypatch.setattr(odds_api_io, "urlopen", fake_urlopen)

    provider = OddsApiIoProvider(api_key="test-key", bookmakers=["Bet365"], league="lck")
    matches, snapshots = provider.fetch_upcoming()

    assert len(matches) == 1
    assert matches[0].match_id == "odds-api-io:123"
    assert matches[0].league == "League of Legends Champions Korea"
    assert matches[0].team_a == "T1"
    assert matches[0].team_b == "Gen.G"
    assert len(snapshots) == 1
    assert snapshots[0].bookmaker == "Bet365"
    assert snapshots[0].odds_a == 1.91
    assert snapshots[0].odds_b == 1.91


def test_odds_api_io_provider_fetches_each_bookmaker_separately(monkeypatch) -> None:
    requested_urls: list[str] = []
    responses = [
        [
            {
                "id": 123,
                "league": {"name": "League of Legends Champions Korea", "slug": "lck"},
                "home": "T1",
                "away": "Gen.G",
                "date": "2026-06-01T17:00:00Z",
                "status": "pending",
            }
        ],
        {
            "bookmakers": {
                "Bet365": [
                    {
                        "name": "ML",
                        "odds": [{"home": "1.91", "away": "1.91"}],
                    }
                ]
            }
        },
        {"bookmakers": {"Unibet": []}},
    ]

    def fake_urlopen(request, timeout):
        requested_urls.append(request.full_url)
        return FakeResponse(responses.pop(0))

    monkeypatch.setattr(odds_api_io, "urlopen", fake_urlopen)

    provider = OddsApiIoProvider(api_key="test-key", bookmakers=["Bet365", "Unibet"])
    _matches, snapshots = provider.fetch_upcoming()

    assert len(snapshots) == 1
    assert any("bookmakers=Bet365" in url for url in requested_urls)
    assert any("bookmakers=Unibet" in url for url in requested_urls)


def test_odds_api_io_provider_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ODDS_API_IO_KEY", raising=False)

    try:
        OddsApiIoProvider()
    except RuntimeError as exc:
        assert "ODDS_API_IO_KEY" in str(exc)
    else:
        raise AssertionError("Expected provider to require an API key")
