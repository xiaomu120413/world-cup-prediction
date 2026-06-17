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
| `post_match` | Event check every 30 minutes; due when Dongqiudi matches finished recently | Scoped score/lineup refresh for finished matches, standings, player rankings, matchday news, AI insights, scoped feature/prediction recompute, real-data audit |
| `weekly` | Weekly low-traffic window | Rosters, market values, coaches, FIFA ranks, historical results, missing-market-value export, prediction recompute, real-data audit |
| `pre_match_90m` | Event check every 30 minutes; due when Dongqiudi matches kick off in 75-105 minutes | Scoped final start list / lineup confirmation, T-90m feature snapshot, scoped prediction recompute |
| `auto` | Optional frequent runner | Resolves to `daily_00`, `daily_12`, `pre_match_90m`, or `post_match`; otherwise skips |

`pre_match_90m` is enabled through a fixture-aware scheduler check. It runs only when a Dongqiudi match is in the T-90m window. `post_match` also runs only when recently finished Dongqiudi matches exist. Both cadences pass scoped `--match-id` values to downstream feature and prediction scripts; they do not rebuild all match predictions. Event cadences write per-match success markers in `collector_runs`, and later checks exclude already marked matches so an overlapping morning window does not repeat the same refresh.

All cadences that can change model inputs must run `backfill_identity_mappings.py`, `audit_identity_mappings.py`, and `build_match_features.py` before prediction recompute. Daily jobs write daily `model_features` snapshots keyed by `entity_type`, `entity_key`, `feature_set`, and `as_of_at`; event jobs pass an explicit `--as-of-at` so T-90m and post-match snapshots can be audited separately.

Command examples from repo root:

```powershell
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
python services/api/scripts/run_refresh_schedule.py --cadence daily_00
python services/api/scripts/run_refresh_schedule.py --cadence daily_12
python services/api/scripts/run_refresh_schedule.py --cadence post_match
python services/api/scripts/run_refresh_schedule.py --cadence pre_match_90m
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
- `post_match` is only due when a Dongqiudi match finished recently, currently within the scheduler's recent-finished-match window.
- `pre_match_90m` is only due when a Dongqiudi match kicks off in the scheduler's 75-105 minute window.

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

- No blocked test-source records in the real database.
- No canonical records without source links.
- `players.code` must use `DQD-P{person_id}` for roster players.
- Historical `FIFA-*` player rows must remain `0`; FIFA can be used for team ranking and injury news, not player roster identity.
- Each source link must include entity type/key, source, source type, source URL or stable source reference, confidence, and raw snapshot when available.

## Team Identity Matching

Dongqiudi schedule/homepage payloads can emit generated `DQD...` team codes even when the same national team already exists from the roster collector. Those generated teams are not canonical model identities.

The ingestion rule is:

- Canonical roster teams are teams with at least one Dongqiudi roster player code matching `DQD-P%`.
- Incoming teams are matched against canonical roster teams by normalized code, Chinese name, English name, and stored aliases.
- If a name maps to exactly one canonical roster team, new matches, aliases, standings, and form rows use that canonical team.
- If a name is ambiguous, it is not merged automatically.
- Knockout placeholders such as `第1场1/16决赛胜者` remain non-roster teams until the actual team is known.

- Player identity uses `players.code = DQD-P{person_id}` as the canonical key and `player_aliases` as the source/name mapping layer.
- Player name-only mapping is allowed only when a team/name pair resolves to exactly one player. Same-name players stay warning-only and must use `source_player_id`.

Use the repair script after importing older snapshots or restoring a database that may already contain generated teams:

```powershell
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
python services/api/scripts/merge_duplicate_roster_teams.py --dry-run
python services/api/scripts/merge_duplicate_roster_teams.py
python services/api/scripts/backfill_identity_mappings.py
python services/api/scripts/backfill_data_source_links.py
python services/api/scripts/audit_identity_mappings.py
python services/api/scripts/audit_real_data.py
```

Current local identity snapshot:

- Canonical Dongqiudi roster teams: `48`.
- Canonical Dongqiudi roster players: `1248`.
- Player identity mappings: `3744`.
- Roster-backed matches for feature generation: `147`.
- Remaining non-roster matches: knockout placeholders only.
- Warning-only same-name aliases: Austria `施拉格尔` and Croatia `苏契奇`; use `source_player_id` for these.

Current confidence defaults:

| Source class | Example | Default confidence |
| --- | --- | --- |
| `official` | FIFA ranking, FIFA injury news | `0.95` |
| `public_api` | Open-Meteo | `0.85` |
| `public_source` | Dongqiudi pages and sport-data | `0.80` |
| `public_news` | BBC, Guardian, ESPN, FOX Sports | `0.75-0.85` depending on source |
| `manual_verified` | Venue static enrichment | `0.90` |
| blocked test sources | n/a | Not allowed in real-data DB |

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

The first feature set is `match_pre_match_v1`, stored in `model_features` as JSONB:

- `features.numeric`: flat numeric fields for training, including raw home/away values and diff fields.
- `features.team_context`: structured home/away feature context for debugging and explainability.
- `source_summary`: source tables and source families used to derive the feature row.
- `missing_features`: explicit missing fields; nulls are not silently treated as facts.
- `quality_status`: `complete`, `partial`, or `insufficient`.

The feature builder is transformation only. It does not assign hand-written model weights.

Win/draw/loss probabilities are generated by the small outcome model pipeline:

- `history_core` learns from leakage-safe historical match features.
- `context_calibrator` learns corrections from current context features when both teams have roster-backed context.
- Missing context falls back to `history_core_fallback` and must be exposed in prediction output.
- Formal recompute writes the selected small model into `model_versions` and stores `inference_mode`, `base_probabilities`, `feature_snapshot`, feature quality and feature sources in `match_predictions`.

Current context features are not a substitute for historical pre-match snapshots. Any future LightGBM/CatBoost training must prove that every training feature was known before the historical match kickoff.

## Acceptance Checks

Run these from repo root after each scheduled refresh:

```powershell
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
python services/api/scripts/audit_real_data.py
```

Required audit result:

- `status = pass`
- `blocked_source_records = 0`
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
