# Data Source And Refresh Summary

Updated: 2026-06-15

This document is the execution-facing summary for the current real-data pipeline. It consolidates source ownership, refresh cadence, matchday/news rules, provenance requirements, and acceptance checks so the data can be safely used by the prediction model.

## Scope

The MVP does not need second-level live scraping. It needs complete, traceable, low-frequency feature data:

- One canonical player identity system: Dongqiudi `team/member_v2`, stored as `DQD-P{person_id}`.
- Every model-facing record must have `data_source_links`.
- Weather only refreshes at `00:00` and `12:00` Asia/Shanghai.
- News is collected daily and re-prioritized by actual match context, not by treating every tournament day as a high-frequency matchday.
- Model recomputation only runs after feature data changes.

## Canonical Sources

| Data domain | Canonical source | Collector or job | Target tables | Current use |
| --- | --- | --- | --- | --- |
| National-team roster | Dongqiudi team pages and `team/member_v2` | `collect_dongqiudi_team_details.py` | `teams`, `team_aliases`, `players`, `coaches` | Model and UI canonical identity |
| Player market value | Dongqiudi team/player data | `collect_dongqiudi_team_details.py` | `players.market_value_eur`, `data_source_links` | Model feature and team detail |
| Team market value | Aggregated from Dongqiudi roster players | `enrich_foundation_data.py` | `teams.market_value_eur`, `data_source_links` | Model feature |
| Team ranking metrics | Dongqiudi World Cup team board `cid=61&tab=team` | `collect_dongqiudi_team_details.py` | `team_stat_snapshots`, `raw_snapshots`, `data_source_links` | Model candidate features |
| Schedule, scores, played lineups | Dongqiudi World Cup match context | `collect_dongqiudi_match_context.py` | `matches`, `lineup_snapshots`, `team_match_results` | Match page and feature builder |
| Group standings | Dongqiudi sport-data World Cup standings | `run_collector.py --source dongqiudi --source-type world_cup_standings` | `group_standings`, `team_form_snapshots` | Group page and current-form feature |
| Player recent form | Dongqiudi World Cup player rankings and team statistics | `run_collector.py --source dongqiudi --source-type world_cup_player_rankings` | `player_form_snapshots` | Player form feature |
| FIFA ranking | FIFA rankings API | `collect_fifa_rankings.py` | `teams.fifa_rank`, `data_source_links` | Team strength feature |
| Venue static data | Verified fixture/venue enrichment | `enrich_foundation_data.py` | `venues`, `data_source_links` | Venue context |
| Weather | Open-Meteo by venue coordinates | `enrich_foundation_data.py` | `weather_snapshots`, `data_source_links` | Weather context feature |
| Verified injuries | FIFA official injury news | `collect_verified_injuries.py` | `injury_reports`, `data_source_links` | Availability feature |
| Public news | Dongqiudi, BBC, Guardian, ESPN, FOX Sports | `collect_public_news.py` | `news_items`, `raw_snapshots`, `data_source_links` | AI insight input |
| AI news insight | Existing `news_items` with local extractor | `build_ai_news_insights.py` | `ai_insights`, `data_source_links` | Availability, lineup, tactic signals |
| Historical national-team results | Historical import job | `collect_historical_international_results.py` | `team_match_results` | Opponent-strength record feature |

## Dongqiudi Team Board Metrics

The Dongqiudi World Cup team board is the canonical source for current team-stat metrics. The collector must keep each metric as a structured `team_stat_snapshots` row instead of flattening only a few columns.

Required metric coverage includes the visible board categories such as:

- Goals and attacking: `进球`, `射门`, `射正`, `击中门框`, `成功过人`, `创造进球机会`, `错失绝佳机会`.
- Passing and possession: `助攻`, `关键传球`, `传球`, `传球成功率`, `触球`, `长传`, `成功长传`, `抢断`.
- Defense and discipline: `黄牌`, `红牌`, `犯规`, `拦截`, `解围`, `争顶总数`, `争顶成功`, `扑救`.
- Goalkeeping and errors: `失误导致丢球`, `失误导致射门`, `丢失球权`, `零封`.
- Team quality context: `评分`, `身价`.

Acceptance requirement: `team_stat_metrics >= 45`, `team_stat_snapshots_without_source = 0`, and each snapshot has source metadata pointing back to Dongqiudi `cid=61` team-board data.

## Refresh Cadence

| Cadence | Trigger | Jobs |
| --- | --- | --- |
| `daily_00` | Every day at 00:00 Asia/Shanghai | Schedule/scores/lineups, standings, player rankings, team details, FIFA ranking, verified injuries, public news, AI insights, prediction recompute, real-data audit |
| `daily_12` | Every day at 12:00 Asia/Shanghai | Weather/foundation refresh, verified injuries, public news, AI insights, prediction recompute, real-data audit |
| `post_match` | 30-60 minutes after a finished match | Scores/lineups, standings, player rankings, matchday news, AI insights, prediction recompute, real-data audit |
| `weekly` | Weekly low-traffic window | Rosters, market values, coaches, FIFA ranks, historical results, missing-market-value export, prediction recompute, real-data audit |
| `auto` | Optional frequent runner | Resolves to `daily_00`, `daily_12`, or `post_match`; otherwise skips |

Command examples from repo root:

```powershell
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
python services/api/scripts/run_refresh_schedule.py --cadence daily_00
python services/api/scripts/run_refresh_schedule.py --cadence daily_12
python services/api/scripts/run_refresh_schedule.py --cadence post_match
python services/api/scripts/run_refresh_schedule.py --cadence weekly
python services/api/scripts/run_refresh_schedule.py --cadence auto
```

Use `--dry-run` before enabling any scheduled job:

```powershell
python services/api/scripts/run_refresh_schedule.py --cadence daily_00 --dry-run
```

## Matchday Rule

Matchday is computed from data, not set manually.

Definition: a local date is a matchday only when at least one `matches.kickoff_at` falls on that Asia/Shanghai calendar date.

This means:

- Consecutive tournament days can be matchdays, but that only raises priority for news, injury, lineup, and post-match refreshes.
- Weather still refreshes only at `00:00` and `12:00`.
- Collectors do not become hourly jobs just because the tournament is active.
- `post_match` is only due when a match finished recently, currently within the scheduler's recent-finished-match window.

## News Extraction Rule

News collection runs:

- Daily at `00:00`.
- Daily at `12:00`.
- Once after relevant matches finish.

The collector keeps an item only when title or summary matches at least one valid context:

- World Cup or FIFA tournament terms.
- Injury, suspension, fitness, squad, lineup, training, coach, tactic, or team-news terms.
- Full national-team names and aliases derived from the Dongqiudi 48-team roster.

Three-letter codes are not generic keywords because codes such as `CAN` can match normal English words. Explicit aliases such as `USA`, `USMNT`, `England`, `Brazil`, and `South Korea` are allowed.

Each inserted news item must write:

- `news_items.related_team_ids` when a team can be matched.
- `data_source_links.metadata.matched_keywords`.
- `data_source_links.metadata.matched_teams`.
- `data_source_links.metadata.matchday_context`, including local date, today's match count, next-24-hour match count, and priority team codes.

AI insights must remain evidence-bound. Only confidence-qualified availability signals are allowed to become model features.

## Provenance And Trust Gate

Hard requirements before data can be treated as real production data:

- No `local_sample` records in the real database.
- No canonical records without source links.
- `players.code` must use `DQD-P{person_id}` for roster players.
- Historical `FIFA-*` player rows must remain `0`; FIFA can be used for team ranking and injury news, not player roster identity.
- Each source link must include entity type/key, source, source type, source URL or stable source reference, confidence, and raw snapshot when available.

Current confidence defaults:

| Source class | Example | Default confidence |
| --- | --- | --- |
| `official` | FIFA ranking, FIFA injury news | `0.95` |
| `public_api` | Open-Meteo | `0.85` |
| `public_source` | Dongqiudi pages and sport-data | `0.80` |
| `public_news` | BBC, Guardian, ESPN, FOX Sports | `0.75-0.85` depending on source |
| `manual_verified` | Venue static enrichment | `0.90` |
| `sample_for_tests_only` | `local_sample` | Not allowed in real-data DB |

## Concurrency And Idempotency

The scheduler and collectors must stay safe under repeated local runs or overlapping scheduled invocations:

- `run_refresh_schedule.py` records `collector_runs` with `source=scheduler` and `job_type=refresh:{cadence}`.
- Scheduler uses a once-per-slot check to skip a cadence that already succeeded in the current slot.
- Scheduler uses a PostgreSQL advisory lock to prevent concurrent runs of the same cadence.
- Raw snapshots are deduplicated by source, source type, and checksum.
- Canonical tables use stable keys/upserts for matches, players, teams, aliases, standings, and snapshots.
- Jobs that write the same `source_type` should not be run concurrently outside the scheduler.

## Model Feature Readiness

Feature builder can use:

- FIFA ranking difference.
- Dongqiudi team-stat metric differences.
- Team market value and player market value differences.
- Current tournament player-form differences.
- Group/team current form from standings and played matches.
- Played-lineup stability where lineups exist.
- Injury/news AI availability signals only when source-bound and confidence-qualified.
- Venue/weather context with neutral fallback when unavailable.

Feature builder must not use:

- Unsourced news claims.
- Low-confidence AI guesses.
- Player rows outside the Dongqiudi canonical identity system.
- Sample data.
- Missing values silently filled as real facts.

## Acceptance Checks

Run these from repo root after each scheduled refresh:

```powershell
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
python services/api/scripts/audit_real_data.py
```

Required audit result:

- `status = pass`
- `local_sample_records = 0`
- all `*_without_source = 0`
- `team_stat_snapshots_without_source = 0`
- `ai_insights_without_source = 0`

Smoke checks:

```powershell
$env:PYTHONPATH="services/api"
python services/api/scripts/run_refresh_schedule.py --cadence daily_00 --dry-run
python services/api/scripts/run_refresh_schedule.py --cadence daily_12 --dry-run
python services/api/scripts/run_refresh_schedule.py --cadence post_match --dry-run
python services/api/scripts/run_refresh_schedule.py --cadence weekly --dry-run
python -m pytest services/api/tests/test_refresh_scheduler.py services/api/tests/test_ai_news_insights.py
```

Current local coverage snapshot is tracked in `REAL_DATA_CONTEXT_UPDATE_2026_06_15.md`.
