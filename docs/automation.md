# Automating Odds Collection

The app has two automation modes:

- `collect-odds`: run one capture and exit.
- `collect-loop`: keep running and capture every N seconds.

Both commands append rows to `odds_snapshots`, so repeated runs create odds movement history.

## Local Loop

Use this on a machine that stays on:

```powershell
lol-bets collect-loop --provider mock --interval-seconds 900
```

That captures every 15 minutes until the process is stopped. Use `--max-runs` for testing:

```powershell
lol-bets collect-loop --provider mock --interval-seconds 5 --max-runs 3
```

## Windows Task Scheduler

Use Task Scheduler when you want the collector to run in the background without keeping a terminal open.

Create a task that runs every 15 minutes with:

```powershell
python -m lol_bet_strategy.cli --db C:\path\to\lol_bets.sqlite3 collect-odds --provider mock
```

Set the task's working directory to the repository root. For this workspace, that is:

```powershell
C:\Users\User\Documents\Codex\2026-05-20\create-a-repo-in-github-for
```

## GitHub Actions

GitHub Actions can run on a cron schedule, but SQLite data written inside the runner disappears unless we commit it, upload it as an artifact, or write to a hosted database. For this project, local Task Scheduler is simpler until we move storage to Postgres, Supabase, S3, or another persistent service.

## Real Provider Requirement

The automation is ready, but `mock` is still the only provider implemented. To collect real odds automatically we need one of:

- a paid/self-serve odds API
- a permitted bookmaker data feed
- a small script that transforms a downloaded CSV into `import-odds-csv`

Do not scrape bookmaker websites unless their terms allow it. An API provider is cleaner because it gives stable event IDs, timestamps, bookmaker names, and price formats.
