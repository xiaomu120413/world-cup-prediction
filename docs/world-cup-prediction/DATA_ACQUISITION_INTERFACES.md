# Data Acquisition Interfaces

Last checked: 2026-06-17

This document is the working contract for real-data collection. The core rule is simple: model-facing and API-facing canonical data must come from a recorded source link. UI empty states are allowed; synthetic data and silent fallback values are not allowed in canonical tables or model features.

## Source Policy

| Source | Role | Trust class | Production use |
| --- | --- | --- | --- |
| Dongqiudi | Primary identity, roster, player value, team metrics, schedule, venue, lineup, standings, current tournament player stats | Public source | Allowed |
| FIFA | Team ranking and manually verified injury/news URLs | Official | Allowed |
| Open-Meteo | Venue current weather observation | Public API | Allowed |
| Mart Jurisoo international results dataset | Historical national-team match results | Public dataset | Allowed |
| BBC / Guardian / ESPN / FOX Sports | Public news RSS | Public news | Allowed |
| `ai_news_extractor` | Internal extraction from sourced news | Internal derived | Allowed only with source news links |
| `manual_verified` | Venue coordinates/surface/capacity enrichment | Manual verified public facts | Allowed with source note |
| `local_sample` | Local/sample data | Sample | Blocked |
| TheStatsAPI | Legacy prototype fixture source | Legacy/blocked | Blocked for production; `run_collector` must not expose it |

Hard gates:

- Every canonical row in `teams`, `players`, `matches`, `venues`, `group_standings`, `team_stat_snapshots`, `team_match_results`, `lineup_snapshots`, `news_items`, `ai_insights`, `weather_snapshots`, and model feature outputs needs `data_source_links`.
- Missing model features stay missing and are recorded in `model_features.missing_features`; do not fill missing real features with zero.
- Prediction fallback is allowed only as an explicit model mode, for example `history_core_fallback` with `fallback_reason=missing_context_features`.
- Frontend copy such as "no real data yet" or "sync pending" is an empty state, not data. It must not be persisted as a metric.

## Interface Inventory

| Data domain | Collector | External interface | Writes | Source types | Refresh cadence |
| --- | --- | --- | --- | --- | --- |
| 48-team roster, player identity, club, position, shirt number, player market value, player avatar, coaches | `services/api/scripts/collect_dongqiudi_team_details.py` | `https://pc.dongqiudi.com/team/{team_id}`; `https://www.dongqiudi.com/api/data/v1/detail/team/{team_id}?app=dqd&lang=zh-cn`; `https://www.dongqiudi.com/sport-data/soccer/biz/dqd/v1/team/member_v2/{team_id}?app=dqd`; `https://www.dongqiudi.com/player/{person_id}.html` | `teams`, `team_aliases`, `players`, `player_aliases`, `player_form_snapshots`, `coaches`, `data_source_links`, `app/data/dongqiudi_player_avatars.json` | `team_detail_profile`, `team_member_v2`, `team_member_v2_market_value`, `player_profile_market_value`, `team_member_v2_person_logo`, `team_member_v2_statistic`, `team_member_v2_coach`, `team_history_coach`, `team_profile_market_value` | Low frequency; daily at 00:00 is acceptable during tournament, weekly backstop |
| Dongqiudi team board metrics | `services/api/scripts/collect_dongqiudi_team_details.py` | `https://sport-data.dongqiudi.com/soccer/biz/data/ranking/team?season_id=26123&app=dqd&version=853&platform=ios&language=zh-cn&app_type=&type=team` plus metric tabs | `team_stat_snapshots`, `raw_snapshots`, `data_source_links` | `world_cup_team_ranking` | Daily 00:00; post-match refresh if standings/stat boards change |
| World Cup schedule, scores, match identity | `services/api/scripts/collect_dongqiudi_match_context.py` | `https://sport-data.dongqiudi.com/soccer/biz/data/schedule?season_id=26123&app=dqd&version=853&platform=ios&language=zh-cn&round_all=1` | `matches`, `team_match_results`, `raw_snapshots`, `data_source_links` | `world_cup_schedule` | Daily 00:00/12:00; post-match scoped refresh |
| Match venue | `services/api/scripts/collect_dongqiudi_match_context.py` | `https://m.dongqiudi.com/matchDetail/{match_id}/analysis` (`window.__INITIAL_STATE__.venue`) | `venues`, `matches.venue_id`, `raw_snapshots`, `data_source_links` | `match_detail_venues`, `match_detail_venue` | Same as schedule; no venue fallback from fixture rows |
| Played lineup and lineup stability | `services/api/scripts/collect_dongqiudi_match_context.py` | `https://sport-data.dongqiudi.com/soccer/biz/match/lineup/{match_id}?app=dqd&lang=zh-cn` | `lineup_snapshots`, `team_form_snapshots.lineup_stability_score`, `raw_snapshots`, `data_source_links` | `match_lineup` | Post-match; T-90m scoped refresh with `--include-scheduled-lineups` |
| Group standings | `services/api/scripts/run_collector.py --source dongqiudi --source-type world_cup_standings` | `https://sport-data.dongqiudi.com/soccer/biz/data/standing?season_id=26123&app=dqd&version=830&platform=miniprogram&language=zh-cn&app_type=` | `group_standings`, `team_form_snapshots`, `raw_snapshots`, `data_source_links` | `world_cup_standings` | Daily 00:00/12:00; post-match |
| Player current tournament rankings | `services/api/scripts/run_collector.py --source dongqiudi --source-type world_cup_player_rankings` | `https://sport-data.dongqiudi.com/soccer/biz/data/person_ranking?app=dqd&version=830&platform=miniprogram&type={goals,assists,shots,shots_on_target,key_passes,appearances,time_played,starts,yellow_cards,red_cards}&season_id=26123`; `market_value_ranking` | `players`, `player_form_snapshots`, `raw_snapshots`, `data_source_links` | `world_cup_player_rankings`, `market_value_ranking` | Daily 00:00/12:00; post-match |
| FIFA ranking | `services/api/scripts/collect_fifa_rankings.py` | `https://api.fifa.com/api/v3/rankings?gender=1&count=300` | `teams.fifa_rank`, `raw_snapshots`, `data_source_links` | `mens_world_ranking` | After FIFA ranking update; weekly backstop |
| Venue static enrichment | `services/api/scripts/enrich_foundation_data.py` | FIFA stadium information page plus manually verified coordinates/capacity/surface | `venues.capacity`, `venues.surface`, `venues.weather_profile`, `data_source_links` | `venue_enrichment` | Daily 00:00/12:00 with weather job; update when venue codes change |
| Weather snapshots | `services/api/scripts/enrich_foundation_data.py` | `https://api.open-meteo.com/v1/forecast` with venue latitude/longitude | `weather_snapshots`, `raw_snapshots`, `data_source_links` | `venue_current_weather` | 00:00 and 12:00; current observation only, not matchday forecast |
| Historical international results | `services/api/scripts/collect_historical_international_results.py` | `https://raw.githubusercontent.com/martj42/international_results/master/results.csv` or local CSV override | `historical_international_matches`, `team_match_results`, `raw_snapshots`, `data_source_links` | `historical_results` | Weekly or before model retraining |
| Public news | `services/api/scripts/collect_public_news.py` | Guardian football RSS, BBC football RSS, ESPN soccer RSS, FOX Sports World Cup RSS | `news_items`, `raw_snapshots`, `data_source_links` | `football_rss`, `soccer_rss`, `world_cup_rss` | 00:00/12:00; post-match; matchday mode only when local date has at least one kickoff |
| Verified injury seed items | `services/api/scripts/collect_verified_injuries.py` | FIFA article URLs listed in script | `injury_reports`, `raw_snapshots`, `data_source_links` | `verified_injury_news` | Daily; replace manual list with live official feed if available |
| AI news insights | `services/api/scripts/build_ai_news_insights.py` | Internal rules over sourced `news_items` | `ai_insights`, `data_source_links` | `news_insight_v1` | After news collection; confidence >= 0.65 to be model eligible |

## Fallback Audit Rules

| Area | Required behavior | Current status |
| --- | --- | --- |
| Match venue | Must use Dongqiudi match detail venue. Do not copy old fixture venue fallback. | Pass: 72/72 Dongqiudi matches have `venue_id`; 16/16 used venues have weather profile. |
| Player roster | Must use Dongqiudi `team/member_v2` identity only. No FIFA PDF or local sample roster rows. | Pass: 1248/1248 roster players are `DQD-P*`. |
| Player market value | Must be sourced from Dongqiudi member statistic, player profile, or market ranking. No estimated value. | Pass: 1248/1248 Dongqiudi roster players have market value. |
| Player avatar | Must come from Dongqiudi `person_logo`; local cache is only a persisted copy of source URLs. | Pass: 1248 avatar source links and 1248 local cache entries. |
| Team market value | Must be source-bound team profile value or derived from sourced Dongqiudi roster values. | Pass: 48/48 roster teams have market value. |
| Team board metrics | Missing metric rows are absent, not zero-filled. | Pass: 45 metrics, 868 source-linked rows. |
| Top30 record | Must be calculated from `team_match_results.opponent_rank` / `opponent_rank_bucket`. If there is no sample, expose "sample too small" rather than `0 wins` or fake values. | Pass for teams with match-result rows; keep as audit item on team detail API. |
| Lineup stability | Only from real lineup endpoint rows. Scheduled matches without lineup should stay missing until T-90m/post-match. | Pass: 440 lineup rows currently source-linked. |
| Injuries/suspensions | Only sourced reports or AI insights backed by news source links; no fabricated availability status. | Pass: source audit passes; small verified FIFA seed exists. |
| Weather | Current Open-Meteo observation is allowed but marked `current_observation_not_matchday`; do not treat it as forecast certainty. | Pass: 16 venue set, 58 weather rows, no legacy venue links. |
| Prediction fallback | Model fallback must be explicit in `inference_mode` / `fallback_reason`; missing features must remain visible. | Pass after 2026-06-17 guard: current-context calibration requires complete critical context and does not treat missing form features as zero. |
| Current-context model features | Missing player form, coach, and team-board features may be padded to `0.0` only for vector shape after the missing mask is recorded. They must not make `CurrentContextFeatureStore.has_team()` return true. | Pass by regression test; current audit shows 48/48 teams have roster context rows but 0/48 teams are context-ready because `ctx_avg_form_score` and player count-rate features are missing. |
| Frontend empty states | Empty strings such as "no real data yet" are allowed only when API data is absent. | Allowed; not model data. |
| Team detail score display | Derived score cards may use only available sourced inputs. Do not emit default attack/stability/depth scores from hard-coded constants when all inputs are absent. | Pass after 2026-06-17 guard: rating rows are omitted when real inputs are missing. |
| Flag/image fallback | `fallback.svg` is allowed only for image rendering failure; all 48 teams should still have mapped local flags. | Needs periodic UI audit after team-resource changes. |

## Current Data Coverage Snapshot

Collected from local database on 2026-06-17 after the venue cleanup:

| Check | Value |
| --- | ---: |
| Dongqiudi matches | 72 |
| Dongqiudi matches with venue | 72 |
| Used venue records | 16 |
| Used venues with weather profile | 16 |
| Legacy unused venue records | 0 |
| Open-Meteo weather rows | 58 |
| Blocked `local_sample` / TheStatsAPI source records | 0 |
| Dongqiudi roster players | 1248 |
| Roster players with market value | 1248 |
| Roster players with avatar source | 1248 |
| Roster teams | 48 |
| Roster teams with market value | 48 |
| Team stat snapshots | 868 |
| Distinct team stat metrics | 45 |
| Lineup rows | 440 |
| Public news items | 359 |
| AI insights | 109 |
| Historical international matches | 49421 |
| Team-perspective match results | 98986 |
| Current-context roster teams | 48 |
| Current-context teams ready for calibration | 0 |

`scripts/audit_real_data.py` status: `pass`

## Refresh Scope

| Cadence | Jobs | Scope rule |
| --- | --- | --- |
| Daily 00:00 | Schedule/venue/lineup context, standings, player rankings, team details, FIFA ranking check, news, AI insights, features, predictions, audit | Full current dataset |
| Daily 12:00 | Schedule/venue/lineup context, standings, player rankings, venue weather, news, AI insights, scoped model refresh | Full current dataset where low cost; avoid unnecessary retraining |
| Weather 00:00/12:00 | `enrich_foundation_data.py` | All 16 used venues |
| Post-match | Schedule/score/lineup, standings, player rankings, news, insights, feature snapshot, prediction review | Only recently finished Dongqiudi matches and affected future matches |
| T-90m | Schedule + final lineup endpoint, feature snapshot, prediction recompute | Only matches in the 75-105 minute pre-kickoff window |
| Weekly/backstop | Team details, FIFA rankings, historical results, model retraining candidates | Full source refresh |

Concurrency rules:

- Use scheduler advisory locks; do not run the same cadence concurrently.
- Event jobs must pass scoped `--match-id` arguments and write per-match scheduler markers so morning match batches do not repeat.
- Data collection should be low-frequency. Do not continuously poll Dongqiudi.

## Verification Commands

Run these before a release candidate:

```powershell
cd C:\Users\mu\Desktop\code\world-cup-prediction\services\api
.\.venv\Scripts\python.exe scripts\audit_real_data.py
.\.venv\Scripts\python.exe scripts\purge_legacy_thestatsapi_data.py
.\.venv\Scripts\python.exe -m pytest -q
```

Useful targeted SQL checks:

```sql
select count(*) filter (where venue_id is not null) as with_venue, count(*) as total
from matches
where public_id like 'dongqiudi-%';

select count(*)
from data_source_links
where source in ('local_sample', 'thestatsapi')
   or source_url ilike '%thestatsapi%'
   or entity_key like 'thestatsapi-%';

select count(*) as players,
       count(*) filter (where market_value_eur is not null) as with_market
from players
where code like 'DQD-P%';

select metric_type, count(*) records, count(distinct team_id) teams
from team_stat_snapshots
group by metric_type
order by metric_type;
```

## Open Risk Register

| Risk | Impact | Handling |
| --- | --- | --- |
| Dongqiudi public endpoints may change fields or block requests | Collector failure or missing data | Keep raw snapshots, parser versioning, and low-frequency schedule; fail visibly instead of writing fallback. |
| Public source licensing is not a commercial data license | Launch/legal risk | MVP/internal validation only; keep adapter boundary for authorized API replacement. |
| Current weather is not kickoff weather | Weather feature can mislead | Mark data quality; add forecast endpoint later before treating weather as a high-weight feature. |
| Some team board metrics have sparse rows because only non-zero ranked teams appear | Model may overread absence as zero | Missing metric must remain missing; feature builder and current-context store both record missing features before any vector padding. |
| Player recent form snapshots currently lack real form/rating fields | Context calibrator could overread zero-filled player form | Context calibration is gated off until critical current-context fields are present; keep `history_core` for formal predictions until player form coverage is restored. |
| News extraction is rules-based | Could miss nuanced injury/lineup news | Keep source evidence; add LLM extraction only as source-linked derived data. |
| TheStatsAPI adapter/test remnants | Developer confusion | Production adapter already rejects source; remove test-only legacy code in a separate cleanup if desired. |
