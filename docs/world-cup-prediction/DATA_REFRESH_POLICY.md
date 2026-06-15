# Data Refresh Policy

Updated: 2026-06-15

This project is a low-frequency World Cup prediction product. It does not need second-level live scraping. Data refreshes should prioritize stable model inputs, source traceability, and predictable operating cost.

## Refresh Rules

| Cadence | Data domains | Sources | Commands or jobs |
| --- | --- | --- | --- |
| Daily 00:00 | Schedule, scores, standings, player ranking, team ranking, news, injury signals, prediction recompute | Dongqiudi, BBC, Guardian, ESPN, FOX Sports, FIFA injury news | `world_cup_schedule_lineups`, `group_standings`, `player_recent_form`, `world_cup_team_details`, `public_news_rss`, `ai_news_insights`, prediction recompute |
| Daily 12:00 | Weather, news, injury signals, prediction recompute if feature data changed | Open-Meteo, BBC, Guardian, ESPN, FOX Sports, FIFA injury news | `venue_weather`, `public_news_rss`, `ai_news_insights`, prediction recompute |
| Post-match | Scores, standings, lineups, player ranking, team ranking, prediction review | Dongqiudi | `world_cup_schedule_lineups`, `group_standings`, `player_recent_form`, `world_cup_team_details`, prediction recompute/review |
| Weekly | Team roster, player market value, coach records, FIFA rank check | Dongqiudi, FIFA | `world_cup_team_details`, `coach_records`, `fifa_mens_world_ranking` |
| On schedule change | Static fixtures and venues | TheStatsAPI, manual verified venue facts | `official_schedule_venues`, venue enrichment |
| Offline batch | Historical national-team results and World Cup qualifier records | Stable historical provider or authorized/manual verified source | Historical import job, then audit |

## Weather Rule

Weather is refreshed only twice per day:

- `00:00` local time
- `12:00` local time

Do not run weather collection every few hours in the MVP. Weather is a model context feature, not a real-time product feature.

## Matchday Definition

Matchday is not a manual flag and is not "any day during the tournament".

The backend defines matchday as: at least one `matches.kickoff_at` falls on the current Asia/Shanghai local calendar date.

During the World Cup group-stage window, this can be true for many consecutive days. That only changes priority for news, injury, lineup and post-match refreshes. It does not change weather to high-frequency refresh and it does not make every collector run hourly.

## News Extraction Rule

News collection runs at `00:00` and `12:00` every day, plus one post-match refresh when a match has recently finished.

The public RSS collector keeps an item only when the title or summary matches at least one of:

- World Cup or FIFA context keywords.
- Injury, suspension, fitness, squad, lineup, training, coach or team-news keywords.
- National-team names and aliases derived from the Dongqiudi 48-team roster.

Three-letter team codes are not used as generic keywords because codes such as `CAN` can match normal English words. Explicit aliases such as `USA`, `USMNT`, `England`, `Brazil`, `South Korea` and full team names are allowed.

For every inserted news item, the collector writes:

- `news_items.related_team_ids` when a team can be matched.
- `data_source_links.metadata.matched_keywords`.
- `data_source_links.metadata.matched_teams`.
- `data_source_links.metadata.matchday_context`, including local date, today match count, next-24-hour match count and priority team codes.

## Model Recompute Rule

Recompute predictions after any update to:

- schedule or scores
- standings
- player form
- team ranking metrics
- lineups or lineup stability
- injury/news AI signals
- weather

Do not recompute after purely static source-link or raw-snapshot changes that do not alter feature tables.

## Acceptance Checks

Every scheduled refresh should finish with:

```powershell
python scripts/audit_real_data.py
```

Required result:

- `status=pass`
- `local_sample_records=0`
- all `*_without_source=0`
- `team_stat_snapshots_without_source=0`

## Current Canonical Sources

| Domain | Canonical source |
| --- | --- |
| Player roster and player identity | Dongqiudi `team/member_v2`, player code `DQD-P{person_id}` |
| Player market value | Dongqiudi team/player pages |
| Team ranking metrics | Dongqiudi `cid=61` team ranking APIs into `team_stat_snapshots` |
| Scores, schedule, standings, lineups | Dongqiudi sport-data |
| Static fixtures and venues | TheStatsAPI plus manual venue verification |
| FIFA rank | FIFA ranking API |
| Weather | Open-Meteo |
| News | Dongqiudi homepage, BBC, Guardian, ESPN, FOX Sports |
