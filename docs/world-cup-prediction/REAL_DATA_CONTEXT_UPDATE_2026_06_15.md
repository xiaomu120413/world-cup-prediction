# Real Data Context Update - 2026-06-15

This update locks the player dataset to one canonical source: Dongqiudi national-team pages and `team/member_v2`.

## Implemented Data

| Domain | Source | Target tables | Current status |
| --- | --- | --- | --- |
| Canonical national-team squads | Dongqiudi team pages + `team/member_v2` + `detail/team` | `teams`, `team_aliases`, `players`, `data_source_links` | Real 48-team squad coverage |
| Player market values | Dongqiudi `team/member_v2`, player profile pages and team pages | `players.market_value_eur`, `teams.market_value_eur`, `data_source_links` | Complete for Dongqiudi roster |
| Player appearances and form | Dongqiudi `world_cup_player_rankings` and `team/member_v2` statistics | `player_form_snapshots`, `data_source_links` | Real partial/current-tournament coverage |
| Team ranking metrics | Dongqiudi `cid=61` team ranking APIs | `team_stat_snapshots`, `raw_snapshots`, `data_source_links.team_stat` | Real 45-metric team-stat coverage |
| Full World Cup schedule and scores | Dongqiudi `world_cup_schedule` | `matches`, `team_match_results`, `data_source_links` | Real tournament coverage |
| Played-match lineups | Dongqiudi `match_lineup` | `lineup_snapshots`, `players`, `data_source_links` | Real played-match coverage |
| Lineup stability | Derived from `lineup_snapshots` | `team_form_snapshots.lineup_stability_score` | Real but played-match limited |
| FIFA rankings | FIFA `api.fifa.com/api/v3/rankings` | `teams.fifa_rank`, `data_source_links` | Official coverage for all Dongqiudi roster teams |
| Injury reports | FIFA official injury news | `injury_reports`, `data_source_links` | Official verified first batch |
| Multi-source news | Dongqiudi homepage, Guardian, BBC, ESPN, FOX Sports RSS | `news_items`, `raw_snapshots`, `data_source_links` | Real public news coverage with matched keyword/team metadata |
| AI news insights | `news_items` via internal extractor `news_insight_v1` | `ai_insights`, `data_source_links.ai_insight` | Rules baseline with sourced confidence and model-eligibility gate |

## Current Local Counts

After the Dongqiudi-only player refresh on 2026-06-15:

- `matches=211`
- `players=1248`
- `dongqiudi_roster_players=1248`
- `fifa_players=0`
- `player_market_values=1248`
- `dongqiudi_roster_player_market_values=1248`
- `dongqiudi_roster_teams=48`
- `ranked_dongqiudi_roster_teams=48`
- `player_form_snapshots=5272`
- `player_form_snapshots with minutes=151`
- `lineup_snapshots=264`
- `team_match_results=208`
- `injury_reports=4`
- `news_items=221` (`dongqiudi=62`, `bbc=67`, `guardian=56`, `espn=22`, `foxsports=14`)
- `ai_insights=67`
- `model_eligible_ai_insights=8`
- `team_market_values=84`
- `coaches=1051`
- `venues=16`
- `weather_snapshots=32`
- `group_standings=48`
- `team_form_snapshots=24`
- `team_stat_snapshots=868`
- `team_stat_metrics=45`
- `dongqiudi_team_stat_links=868`
- `data_source_links=161317`

## Player Identity Rule

Prediction features must use only `players.code` values shaped as `DQD-P{person_id}`.

The collector first canonicalizes the national team, then writes one player row per Dongqiudi `person_id`. Historical `FIFA-*` player rows and FIFA squad-list-only coach rows are removed by `collect_dongqiudi_team_details.py`. FIFA remains allowed for team rankings and verified injury news, but not as a player roster source.

## Coverage Audit

`GET /api/v1/data-status` returns both:

- `real_data_audit`: verifies that records are real, sourced, approved, and not sample data.
- `coverage_audit`: verifies whether each data domain has enough coverage to be production-ready.

Current coverage state:

- Dongqiudi rosters: pass, `1248 / 1248`.
- Dongqiudi roster market values: pass, `1248 / 1248`.
- FIFA rankings for Dongqiudi roster teams: pass, `48 / 48`.
- Venue enrichment: pass, `16 / 16`.
- Multi-source news: pass, `5` sources: Dongqiudi, Guardian, BBC, ESPN, FOX Sports.
- AI news insights: pass, `67` sourced insight rows, `8` model-eligible availability signals.
- Team match result context: pass, `208 / 208` team-perspective rows for the Dongqiudi World Cup schedule.
- Team market value coverage: pass, at least `48 / 48` participating teams have sourced team-level market values.
- Team ranking metrics: pass, `45` ranking metrics, `868` structured `team_stat_snapshots`, and `868` team-stat source links from Dongqiudi `cid=61` APIs.

## Validation Commands

```powershell
$env:PYTHONPATH='.'
$env:DATABASE_URL='postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction'
python scripts/run_collector.py --source dongqiudi --source-type world_cup_player_rankings
python scripts/collect_dongqiudi_match_context.py
python scripts/collect_verified_injuries.py
python scripts/collect_fifa_rankings.py
python scripts/collect_public_news.py
python scripts/build_ai_news_insights.py
python scripts/collect_dongqiudi_team_details.py
python scripts/enrich_foundation_data.py
python scripts/export_missing_market_values.py
python scripts/audit_real_data.py
```

Current audit result:

- `status=pass`
- `local_sample_records=0`
- all `*_without_source=0`
- `team_stat_snapshots_without_source=0`
- `ai_insights_without_source=0`
- `FIFA-*` player rows: `0`
- missing Dongqiudi roster market values exported by `export_missing_market_values.py`: `0`

## Known Limits

- `lineup_stability_score` is based only on matches that have already been played and have available Dongqiudi lineups.
- `team_match_results` currently covers World Cup 2026 match context from Dongqiudi. It is not yet a full multi-year national-team results history.
- Full World Cup qualifier records versus Top10/Top30/Top50 teams still require a stable historical national-team results source or authorized provider. The `team_match_results` schema already supports `opponent_rank` and `opponent_rank_bucket`.
- Dongqiudi is a public source. If licensed market data is added later, it must update existing `DQD-P*` rows instead of creating a second player roster.

## Refresh Policy

The active refresh cadence is documented in `DATA_REFRESH_POLICY.md`.

- Daily 00:00: refresh schedule/scores, standings, player ranking, team ranking, news, injury signals, and predictions.
- Daily 12:00: refresh weather, news, injury signals, and predictions if feature data changed.
- Weather is intentionally limited to 00:00 and 12:00 local time for MVP operations.
- Matchday is defined by `matches.kickoff_at` on the Asia/Shanghai local date. Consecutive tournament matchdays only raise news/injury/lineup priority and post-match refreshes; they do not create hourly scraping.
- Public news extraction now uses World Cup context terms, injury/lineup/team-news terms, and national-team names/aliases from the Dongqiudi 48-team roster. Matched keywords, matched teams and matchday context are stored in `data_source_links.metadata`.
- AI news insight extraction runs after news refresh. The first baseline extracts injury, suspension, fitness, lineup, squad, coach, training and tactic signals; only confidence-qualified availability signals are marked `is_model_eligible=true`.
