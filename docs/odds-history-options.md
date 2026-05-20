# Odds History Options

Historical match results are easy enough to bootstrap from Oracle's Elixir and Leaguepedia. Historical odds are the harder part because esports odds history is usually sold as a betting data product, not a public analytics dataset.

## Practical Recommendation

Start with two tracks:

1. Use Oracle's Elixir and Leaguepedia for historical game results, teams, patches, drafts, and outcomes.
2. For odds, start with one provider that has historical esports coverage and clear pricing, then normalize everything into our `odds_snapshots` table.

For this project, the strongest low-friction odds-history candidate is BettingIsCool if Pinnacle-only odds are acceptable. It publishes pricing and says esports standard markets are covered from May 2025 onward. That is not enough for deep historical LoL backtests before 2025, but it is enough to validate ingestion, line movement, opening/closing price logic, and CLV workflows.

## Provider Notes

| Provider | LoL/esports odds fit | Published cost | Notes |
| --- | --- | ---: | --- |
| BettingIsCool Pinnacle Data API | Good for sharp-book benchmark odds; esports standard markets from May 2025 onward | 49 EUR/mo starter, 149 EUR/mo pro, 249 EUR/mo enterprise | Pinnacle-only. Includes full odds history, opening/closing lines, results, and settlements. Useful for CLV and market-probability baselines. |
| Odds-API.io | Good first live-odds provider for building our own history from today onward; docs list esports support | Free key available; public docs list 5,000 requests/hour on all plans | Implemented in this app as `odds-api-io`. Need API key and coverage validation for League of Legends events on the account. |
| OddsPapi | Potentially useful broad-bookmaker source; claims esports and free historical data | Free historical data claimed; pricing not fully evaluated yet | Needs an API key and coverage validation for League of Legends specifically before we rely on it. |
| PandaScore Odds | Esports-native vendor | Contact sales for odds; non-betting stats plans start at 400 EUR/game/mo for historical data | Their public stats pricing explicitly excludes betting-related use; bookmaker odds are a separate product. |
| Oddin.gg | Strong esports-operator odds feed with League of Legends live coverage | Contact/demo | B2B sportsbook-oriented. Likely overkill for a hobby analytics tool unless they offer a research plan. |
| Abios | Esports data and odds feed | Contact sales | Strong esports coverage; public site does not list pricing. |
| The Odds API | Good general sports odds-history benchmark | 30 USD/mo for 20k credits, 59 USD/mo for 100k, 119 USD/mo for 5M, 249 USD/mo for 15M | Historical odds are paid, but current public sports list does not show esports/LoL, so it is not a current LoL solution. |
| SportsGameOdds | General sports odds/history | Free tier; 99 USD/mo Rookie; 299 USD/mo Pro with historical data | Public plan list focuses on traditional sports leagues. Validate esports/LoL before using. |

## Cost Expectations

For a realistic LoL odds-history prototype:

- Results and game metadata: 0 USD using Oracle's Elixir and Leaguepedia.
- Pinnacle-only historical odds: about 49-149 EUR/month if BettingIsCool coverage is sufficient.
- Multi-bookmaker historical esports odds: unknown until vendor contact; likely sales-led because the esports-first providers publish demo/contact flows rather than self-serve prices.
- DIY current-odds collection going forward: infrastructure cost only, but it starts collecting from today onward and does not solve old odds history.

## Implementation Shape

Add provider-specific odds importers that produce this normalized shape:

```text
provider, bookmaker, captured_at, match_id, team_a, team_b, odds_a, odds_b
```

The hard part is matching provider event IDs to our match IDs. Store provider event mappings separately before writing odds snapshots:

```text
provider, provider_event_id, match_id, confidence, matched_at
```

Matching should use team names, start time, league/tournament, and a manual override path for ambiguous cases.

## Source Links

- Oracle's Elixir match downloads: https://lol.timsevenhuysen.com/matchdata/
- Leaguepedia ScoreboardGames fields: https://lol.fandom.com/wiki/Module%3ACargoDeclare/ScoreboardGames
- BettingIsCool Pinnacle Data API: https://api.bettingiscool.com/
- OddsPapi: https://oddspapi.io/us/
- PandaScore pricing: https://www.pandascore.co/pricing
- PandaScore bookmaker odds FAQ: https://developers.pandascore.co/docs/frequently-asked-questions
- Oddin.gg esports odds feed: https://oddin.gg/esports-odds-feed
- Abios esports data and odds: https://abiosgaming.com/
- The Odds API pricing and sports list: https://the-odds-api.com/ and https://the-odds-api.com/sports-odds-data/sports-apis.html
- The Odds API historical odds docs: https://the-odds-api.com/historical-odds-data/
- SportsGameOdds pricing: https://sportsgameodds.com/
