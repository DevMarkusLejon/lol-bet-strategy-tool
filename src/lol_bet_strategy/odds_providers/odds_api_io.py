from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lol_bet_strategy.models import Match, OddsSnapshot
from lol_bet_strategy.odds_providers.base import OddsProvider

BASE_URL = "https://api.odds-api.io/v3"


class OddsApiIoProvider(OddsProvider):
    name = "odds-api-io"

    def __init__(
        self,
        api_key: str | None = None,
        bookmakers: list[str] | None = None,
        league: str | None = None,
        event_limit: int = 25,
    ) -> None:
        self.api_key = api_key or os.getenv("ODDS_API_IO_KEY")
        if not self.api_key:
            raise RuntimeError("ODDS_API_IO_KEY is required for the odds-api-io provider")

        env_bookmakers = os.getenv("ODDS_API_IO_BOOKMAKERS", "")
        self.bookmakers = bookmakers or _split_csv(env_bookmakers)
        self.league = league or os.getenv("ODDS_API_IO_LEAGUE")
        self.event_limit = event_limit

    def fetch_upcoming(self) -> tuple[list[Match], list[OddsSnapshot]]:
        events = [event for event in self._get_events() if event.get("status") == "pending"]
        matches: list[Match] = []
        snapshots: list[OddsSnapshot] = []

        for event in events:
            match = _event_to_match(event)
            try:
                event_snapshots = self._get_event_odds(match, str(event["id"]))
            except RuntimeError:
                continue
            if not event_snapshots:
                continue
            matches.append(match)
            snapshots.extend(event_snapshots)

        return matches, snapshots

    def fetch_leagues(self) -> list[dict]:
        payload = self._get_json(
            "/leagues",
            {
                "apiKey": self.api_key,
                "sport": "esports",
            },
        )
        if not isinstance(payload, list):
            raise RuntimeError("Unexpected Odds-API.io leagues response")
        return payload

    def _get_events(self) -> list[dict]:
        params = {
            "apiKey": self.api_key,
            "sport": "esports",
            "limit": str(self.event_limit),
        }
        if self.league:
            params["league"] = self.league

        payload = self._get_json("/events", params)
        if not isinstance(payload, list):
            raise RuntimeError("Unexpected Odds-API.io events response")
        return payload

    def _get_event_odds(self, match: Match, event_id: str) -> list[OddsSnapshot]:
        if not self.bookmakers:
            raise RuntimeError("ODDS_API_IO_BOOKMAKERS or --bookmakers is required")

        snapshots: list[OddsSnapshot] = []
        for bookmaker in self.bookmakers:
            params = {
                "apiKey": self.api_key,
                "eventId": event_id,
                "bookmakers": bookmaker,
            }
            try:
                payload = self._get_json("/odds", params)
            except RuntimeError:
                continue
            snapshots.extend(_odds_response_to_snapshots(match, payload))
        return snapshots

    def _get_json(self, path: str, params: dict[str, str]) -> object:
        url = f"{BASE_URL}{path}?{urlencode(params)}"
        request = Request(url, headers={"User-Agent": "lol-bet-strategy-tool/0.1"})
        for attempt in range(1, 4):
            try:
                with urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                break
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                if exc.code in {429, 500, 502, 503, 504} and attempt < 3:
                    time.sleep(attempt)
                    continue
                raise RuntimeError(f"Odds-API.io HTTP {exc.code}: {detail}") from exc
            except URLError as exc:
                if attempt < 3:
                    time.sleep(attempt)
                    continue
                raise RuntimeError(f"Odds-API.io request failed: {exc.reason}") from exc

        if isinstance(payload, dict) and "error" in payload:
            raise RuntimeError(str(payload["error"]))
        return payload


def _event_to_match(event: dict) -> Match:
    league = event.get("league") or {}
    return Match(
        match_id=f"odds-api-io:{event['id']}",
        league=league.get("name") or league.get("slug") or "esports",
        start_time=event.get("date", ""),
        team_a=event.get("home", ""),
        team_b=event.get("away", ""),
        winner=None,
        best_of=None,
    )


def _odds_response_to_snapshots(match: Match, payload: object) -> list[OddsSnapshot]:
    if not isinstance(payload, dict):
        raise RuntimeError("Unexpected Odds-API.io odds response")

    captured_fallback = datetime.now(UTC).isoformat()
    snapshots: list[OddsSnapshot] = []
    bookmakers = payload.get("bookmakers") or {}
    for bookmaker, markets in bookmakers.items():
        moneyline = _find_moneyline_market(markets)
        if moneyline is None:
            continue

        odds_rows = moneyline.get("odds") or []
        if not odds_rows:
            continue

        first_price = odds_rows[0]
        if "home" not in first_price or "away" not in first_price:
            continue

        odds_a = _decimal_odds(first_price["home"])
        odds_b = _decimal_odds(first_price["away"])
        if odds_a is None or odds_b is None:
            continue

        snapshots.append(
            OddsSnapshot(
                match_id=match.match_id,
                provider=OddsApiIoProvider.name,
                bookmaker=bookmaker,
                captured_at=moneyline.get("updatedAt") or captured_fallback,
                team_a=match.team_a,
                team_b=match.team_b,
                odds_a=odds_a,
                odds_b=odds_b,
            )
        )

    return snapshots


def _find_moneyline_market(markets: object) -> dict | None:
    if not isinstance(markets, list):
        return None
    for market in markets:
        if not isinstance(market, dict):
            continue
        name = str(market.get("name", "")).lower()
        if name in {"ml", "moneyline", "match winner", "winner"}:
            return market
    return None


def _decimal_odds(value: object) -> float | None:
    try:
        odds = float(value)
    except (TypeError, ValueError):
        return None
    if odds <= 1:
        return None
    return odds


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
