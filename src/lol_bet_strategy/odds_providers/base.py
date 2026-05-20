from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from lol_bet_strategy.models import Match, OddsSnapshot


class OddsProvider(ABC):
    name: str

    @abstractmethod
    def fetch_upcoming(self) -> tuple[Iterable[Match], Iterable[OddsSnapshot]]:
        """Return upcoming matches and their latest odds snapshots."""
