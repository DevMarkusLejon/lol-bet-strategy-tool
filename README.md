# LoL Bet Strategy Tool

Research tool for collecting professional League of Legends match odds, importing historical match results, and running betting heuristics against stored data.

This is for analysis and strategy testing. It does not place bets.

## Features

- SQLite storage for matches, odds snapshots, and heuristic signals
- CSV importer for historical pro LoL match data
- Pluggable odds provider interface
- Mock odds provider for local development and tests
- CLI commands for ingestion and heuristic runs
- Baseline value heuristic comparing market implied probability with historical team win rate

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Initialize the local database:

```powershell
lol-bets init-db
```

Import historical match results from CSV:

```powershell
lol-bets import-history data/historical_matches.csv
```

Import Oracle's Elixir historical exports:

```powershell
lol-bets import-oracles-elixir path\to\oracles_elixir_export.csv
```

Fetch historical games from Leaguepedia Cargo:

```powershell
lol-bets fetch-leaguepedia-games --start-date 2024-01-01 --end-date 2024-02-01 --league LCK
```

Collect sample odds with the mock provider:

```powershell
lol-bets collect-odds --provider mock
```

Run heuristics:

```powershell
lol-bets run-heuristics --min-edge 0.05
```

## Historical CSV Format

Required columns:

```csv
match_id,league,start_time,team_a,team_b,winner,best_of
```

Optional odds columns:

```csv
opening_odds_a,opening_odds_b,closing_odds_a,closing_odds_b
```

Decimal odds are expected. Example:

```csv
match_id,league,start_time,team_a,team_b,winner,best_of,closing_odds_a,closing_odds_b
lck-2026-001,LCK,2026-01-14T10:00:00Z,T1,Gen.G,T1,3,1.85,1.95
```

## Historical Data Sources

See `docs/data-sources.md` for practical options. The best first source is Oracle's Elixir bulk exports. Leaguepedia Cargo is useful for targeted API queries by date range, tournament, or league page. Historical odds are a separate problem and will likely need a paid odds-history API or curated closing-line CSVs.

## Odds Providers

The core app expects odds providers to return decimal prices for upcoming matches. Add real providers under `src/lol_bet_strategy/odds_providers/` by implementing `OddsProvider`.

Common options to integrate later:

- The Odds API esports markets
- PandaScore odds or fixture metadata
- OddsJam, Sportradar, or bookmaker-specific feeds

Use `.env.example` as the starting point for API credentials.

## Development

```powershell
python -m pip install -e ".[dev]"
pytest
ruff check .
```

## Roadmap

- Add provider implementation for a chosen paid odds API
- Track odds movement over time by bookmaker
- Add champion draft metadata and patch version features
- Backtest staking strategies such as flat stake, Kelly fraction, and stop-loss windows
- Export heuristic signals to CSV and notebooks
