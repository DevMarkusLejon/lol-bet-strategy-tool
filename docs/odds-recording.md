# Recording Odds Going Forward

The app can now build its own odds-history database over time. Every odds entry is appended to `odds_snapshots`, so repeated captures for the same match and bookmaker become line-movement history.

## One-Off Manual Entry

Use this when you see odds on a bookmaker site and want to capture them immediately.

```powershell
lol-bets record-odds `
  --match-id lck-2026-001 `
  --league LCK `
  --start-time 2026-06-01T17:00:00Z `
  --team-a T1 `
  --team-b Gen.G `
  --best-of 3 `
  --bookmaker pinnacle `
  --odds-a 1.91 `
  --odds-b 1.91
```

If the match already exists, only `--match-id`, `--bookmaker`, `--odds-a`, and `--odds-b` are required.

## CSV Batch Entry

Use this when collecting odds in a spreadsheet or from a small script.

```powershell
lol-bets import-odds-csv data/odds_snapshots.example.csv
```

Required columns:

```csv
match_id,league,start_time,team_a,team_b,provider,bookmaker,odds_a,odds_b
```

Optional columns:

```csv
best_of,captured_at,winner
```

If `captured_at` is blank, import time is used. Decimal odds are expected.

## Inspect Latest Prices

```powershell
lol-bets latest-odds
lol-bets db-summary
```

## Collection Routine

For a useful self-built dataset, capture each upcoming match at consistent times:

- opening price when first posted
- 24 hours before match start
- 6 hours before match start
- 1 hour before match start
- closing price right before the match starts

Bookmaker names should be stable strings such as `pinnacle`, `bet365`, or `unibet`. Provider should describe how the row was collected, for example `manual`, `spreadsheet`, or a future API provider name.
