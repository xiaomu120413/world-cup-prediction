# Real Data Context Update - 2026-06-15

This update adds the missing high-impact data fields needed for prediction features.

## Implemented Data

| Domain | Source | Target tables | Current status |
| --- | --- | --- | --- |
| Player appearances and minutes | Dongqiudi `world_cup_player_rankings` | `players`, `player_form_snapshots`, `data_source_links` | Real partial coverage |
| Full World Cup schedule and scores | Dongqiudi `world_cup_schedule` | `matches`, `team_match_results`, `data_source_links` | Real tournament coverage |
| Played-match lineups | Dongqiudi `match_lineup` | `lineup_snapshots`, `players`, `data_source_links` | Real played-match coverage |
| Lineup stability | Derived from `lineup_snapshots` | `team_form_snapshots.lineup_stability_score` | Real but sample-limited |
| Injury reports | FIFA official injury news | `injury_reports`, `data_source_links` | Official verified first batch |
| FIFA rankings | FIFA `api.fifa.com/api/v3/rankings` | `teams.fifa_rank`, `data_source_links` | Official coverage for all roster teams |
| Multi-source news | Guardian, BBC, ESPN RSS | `news_items`, `raw_snapshots`, `data_source_links` | Real public news coverage |

## Current Local Counts

After running the collectors on 2026-06-15:

- `matches=211`
- `player_form_snapshots=376`
- `player_form_snapshots with minutes=151`
- `lineup_snapshots=264`
- `team_match_results=208`
- `injury_reports=4`
- `news_items=186`
- `data_source_links=3901`

## Coverage Audit

`GET /api/v1/data-status` now returns both:

- `real_data_audit`: verifies that records are real, sourced, approved, and not sample data.
- `coverage_audit`: verifies whether each data domain has enough coverage to be production-ready.

Current coverage state:

- Official rosters: pass, `1248 / 1248`.
- FIFA rankings for roster teams: pass, `48 / 48`.
- Venue enrichment: pass, `16 / 16`.
- Multi-source news: pass, `4` sources: Dongqiudi, Guardian, BBC, ESPN.
- Team match result context: pass, `208 / 208` team-perspective rows for the Dongqiudi World Cup schedule.
- Player market value coverage: needs attention, `129 / 1624`.
- Team market value coverage: needs attention, `18 / 48`.

Market values remain the main blocker. There is no official free full player-market-value source in the current stack. This should be solved with an authorized provider or a controlled manual import rather than synthetic fill.

## Validation Commands

```powershell
$env:PYTHONPATH='.'
$env:DATABASE_URL='postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction'
python scripts/run_collector.py --source dongqiudi --source-type world_cup_player_rankings
python scripts/collect_dongqiudi_match_context.py
python scripts/collect_verified_injuries.py
python scripts/collect_fifa_rankings.py
python scripts/collect_public_news.py
python scripts/audit_real_data.py
```

Current audit result:

- `status=pass`
- `local_sample_records=0`
- all `*_without_source=0`
- all source links use approved real sources: `dongqiudi`, `fifa`, `thestatsapi`, `open_meteo`, `manual_verified`, `guardian`, `bbc`, `espn`

## Known Limits

- `lineup_stability_score` is based only on matches that have already been played and have available Dongqiudi lineups.
- `team_match_results` currently covers World Cup 2026 match context from Dongqiudi. It is not yet a full multi-year national-team results history.
- Full World Cup qualifier records versus Top10/Top30/Top50 teams still require a stable historical national-team results source or authorized provider. The `team_match_results` schema already supports `opponent_rank` and `opponent_rank_bucket`.
