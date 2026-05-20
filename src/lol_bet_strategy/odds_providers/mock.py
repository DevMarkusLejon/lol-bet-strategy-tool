from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lol_bet_strategy.models import Match, OddsSnapshot
from lol_bet_strategy.odds_providers.base import OddsProvider


class MockOddsProvider(OddsProvider):
    name = "mock"

    def fetch_upcoming(self) -> tuple[list[Match], list[OddsSnapshot]]:
        now = datetime.now(UTC)
        match = Match(
            match_id=f"mock-{now:%Y%m%d}-t1-geng",
            league="LCK",
            start_time=(now + timedelta(days=1)).isoformat(),
            team_a="T1",
            team_b="Gen.G",
            winner=None,
            best_of=3,
        )
        snapshot = OddsSnapshot(
            match_id=match.match_id,
            provider=self.name,
            bookmaker="mockbook",
            captured_at=now.isoformat(),
            team_a=match.team_a,
            team_b=match.team_b,
            odds_a=2.15,
            odds_b=1.72,
        )
        return [match], [snapshot]
