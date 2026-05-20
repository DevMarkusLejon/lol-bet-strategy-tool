# Historical LoL Data Sources

## Best First Source: Oracle's Elixir

Oracle's Elixir publishes downloadable historical professional LoL match files covering major leagues and tournaments. Files from 2020 onward are CSV; older files are XLSX. This is the best bulk source for backtesting because it already normalizes game, team, player, draft, and stat fields.

Use:

```powershell
lol-bets import-oracles-elixir path\to\oracles_elixir_export.csv
```

Notes:

- Current importer stores one record per completed game using the two team rows.
- It does not yet persist champion picks, bans, patch, side, or team stat features.
- Older XLSX files should be exported to CSV before import, or we can add an XLSX dependency later.

## Best API Source: Leaguepedia Cargo

Leaguepedia exposes structured tables through MediaWiki Cargo. The app can fetch completed games from the `ScoreboardGames` table by UTC date range and optional overview-page filter.

Use:

```powershell
lol-bets fetch-leaguepedia-games --start-date 2024-01-01 --end-date 2024-02-01 --league LCK
```

Notes:

- Fandom applies rate limits, so use narrow date windows and cache results in SQLite.
- The `--league` filter matches the `OverviewPage` string, so `LCK` can include LCK CL. Use a more specific page fragment when needed.
- Leaguepedia is useful for filling gaps, checking schedules, and enriching Oracle's Elixir imports with page IDs or VOD links.

## Snapshot Source: Kaggle Mirrors

Kaggle has mirrors of Oracle's Elixir datasets. These are convenient for notebooks and quick experiments, but they may lag behind the official downloads and may require a Kaggle account or API token.

## Odds History

Historical match result data is easier to get than historical odds. For odds backtesting, likely options are:

- Paid odds APIs that expose esports historical odds.
- Bookmaker archive scraping where allowed by terms.
- Manually maintained closing-line CSVs for early experiments.

Keep odds imports separate from match imports so we can compare multiple books and providers against the same game IDs.
