# World Cup Prediction API

FastAPI backend for the World Cup prediction mini program.

Current scope:

- Public API in database mode by default.
- Health/version endpoints.
- Match, group, ranking, team and AI report endpoints.
- Admin task trigger placeholders.
- PostgreSQL schema, Alembic migration entrypoint, collectors, feature snapshots and prediction services.

## Local Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
$env:DATA_BACKEND="database"
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
uvicorn app.main:app --reload --port 8001
```

Open:

```text
http://127.0.0.1:8001/docs
```

Use port `8001` for the local frontend integration unless another port is explicitly configured in `TARO_APP_API_BASE_URL`.

## Smoke Test

```bash
python -m pytest
```

## Database

Create a local `.env` from `.env.example`, then set `DATABASE_URL`.

Start local PostgreSQL and Redis:

```bash
docker compose up -d postgres redis
```

For the bundled compose file, use this local database URL:

```powershell
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
```

Run migrations:

```bash
alembic upgrade head
```

Or initialize the schema directly:

```bash
python scripts/init_db.py
```

The first migration reuses `db/migrations/001_initial_schema.sql`. Runtime data must come from real collectors, historical imports or recomputation scripts.

Run PostgreSQL-backed integration tests:

```powershell
$env:RUN_DATABASE_TESTS="1"
$env:DATA_BACKEND="database"
python -m pytest tests/test_database_backend.py
```

## Cache

Public database-backed read routes cache JSON responses by default. Redis is preferred when available; if Redis is unavailable, the API uses a short in-process TTL cache so hot UI reads do not repeatedly hit PostgreSQL.

Default local values:

```text
CACHE_ENABLED=true
CACHE_TTL_SECONDS=300
```

With the bundled Docker Compose Redis service:

```powershell
$env:CACHE_ENABLED="true"
$env:CACHE_TTL_SECONDS="300"
$env:REDIS_URL="redis://127.0.0.1:63791/0"
```

If Redis is unavailable, the in-process cache is used for the same TTL.

## Prediction Recompute

Run the current formal prediction pipeline locally. By default this writes today's pre-match `model_features` snapshot, trains or reuses the `small_outcome` model version, and writes `match_predictions` with `inference_mode`, base probabilities, feature snapshot and feature-source metadata:

```powershell
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
python scripts/recompute_predictions.py --scope matchday --match-id usa-paraguay-2026-06-13 --seed 20260616
```

Emergency baseline fallback remains available:

```powershell
python scripts/recompute_predictions.py --model-kind baseline --model-version baseline_2026_06_13 --scope matchday
```

Or trigger it through the admin API when `DATA_BACKEND=database`:

```powershell
curl -X POST http://127.0.0.1:8000/api/admin/predictions/recompute `
  -H "Authorization: Bearer change-me" `
  -H "Content-Type: application/json" `
  -d '{"scope":"matchday","match_ids":["usa-paraguay-2026-06-13"],"seed":20260616}'
```

## Collectors

Collectors write source snapshots and normalized records into PostgreSQL. Public API routes do not run collectors; they only read already ingested data.

The first real low-frequency source adapter is also available:

```powershell
python scripts/run_collector.py --source dongqiudi --source-type homepage --dry-run
python scripts/run_collector.py --source dongqiudi --source-type homepage
```

TheStatsAPI fixtures are no longer an active collector. Use the cleanup script after restoring an older local database that still has legacy fixture rows:

```powershell
python scripts/purge_legacy_thestatsapi_data.py
python scripts/purge_legacy_thestatsapi_data.py --apply
```

World Cup 2026 standings and player ranking data from Dongqiudi sport-data are available as:

```powershell
python scripts/run_collector.py --source dongqiudi --source-type world_cup_standings --dry-run
python scripts/run_collector.py --source dongqiudi --source-type world_cup_standings
python scripts/run_collector.py --source dongqiudi --source-type world_cup_player_rankings --dry-run
python scripts/run_collector.py --source dongqiudi --source-type world_cup_player_rankings
```

Enrich low-frequency foundation data, including venue capacity/surface/coordinates, Open-Meteo venue weather observations and derived team market values from the Dongqiudi roster:

```powershell
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
python scripts/enrich_foundation_data.py
python scripts/backfill_data_source_links.py
```

Normalize generated Dongqiudi `DQD...` teams back to canonical roster teams after importing older snapshots or refreshing multiple Dongqiudi sources:

```powershell
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
python scripts/merge_duplicate_roster_teams.py --dry-run
python scripts/merge_duplicate_roster_teams.py
python scripts/backfill_identity_mappings.py
python scripts/backfill_data_source_links.py
python scripts/audit_identity_mappings.py
python scripts/audit_real_data.py
```

Collect Dongqiudi World Cup national-team pages and team ranking metrics. This is the canonical player dataset: teams are matched by country/team first, and players are keyed by `DQD-P{person_id}` from `team/member_v2`:

```powershell
$env:PYTHONPATH="."
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
python scripts/collect_dongqiudi_team_details.py
python scripts/export_missing_market_values.py
python scripts/audit_real_data.py
```

The missing-value export checks only Dongqiudi roster rows. A healthy local run should export `0` rows because `team/member_v2` and team/player pages currently provide market values for all roster players.

If a licensed/provider export is added later, it must update existing `DQD-P*` player codes only. Do not create a parallel FIFA/offical player roster table for prediction features.

Collect or refresh the other public real-data sources:

```powershell
$env:PYTHONPATH="."
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
python scripts/collect_dongqiudi_match_context.py
python scripts/collect_fifa_rankings.py
python scripts/collect_public_news.py
python scripts/build_ai_news_insights.py
python scripts/audit_real_data.py
```

`collect_public_news.py` uses `--mode auto` by default. Matchday is derived from `matches.kickoff_at` on the Asia/Shanghai local date, not from a blanket tournament flag. News still runs on the low-frequency policy: 00:00, 12:00 and post-match. The collector expands keywords from the Dongqiudi 48-team roster, writes matched teams into `news_items.related_team_ids`, and records matched keywords/teams in `data_source_links.metadata`.

`build_ai_news_insights.py` is the first AI-news structuring baseline. It reads sourced `news_items`, extracts injury, suspension, fitness, lineup, squad, coach, training and tactic signals into `ai_insights`, and writes source links for every insight. Only high-confidence availability signals are marked `is_model_eligible=true`; lower-confidence context remains explainable but does not move the model.

Import historical men's national-team match results without depending on Kaggle authentication. This writes one actual source match per row into `historical_international_matches` first, then writes `team_match_results` rows only as compatibility data for existing model queries. By default this pulls the same public dataset from GitHub raw; use `--csv-path` for a local Kaggle export:

```powershell
$env:PYTHONPATH="."
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
python scripts/collect_historical_international_results.py --dry-run
python scripts/collect_historical_international_results.py
python scripts/collect_historical_international_results.py --csv-path path/to/results.csv
```

Export only actual national-team match records involving the 48 World Cup teams:

```powershell
$env:PYTHONPATH="."
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
python scripts/export_world_cup_48_national_team_matches.py
python scripts/export_world_cup_48_national_team_matches.py --refresh-source
```

The export writes only match data into `exports/world_cup_48_national_team_matches_latest.csv`,
`exports/world_cup_48_national_team_latest_match_by_team.csv` and
`exports/world_cup_48_national_team_matches_summary.json`. Use `--refresh-source` when the upstream historical
results CSV has changed; it imports the latest source first, then regenerates the 48-team match exports.

Build model-ready match feature snapshots after data refreshes and before prediction recompute:

```powershell
$env:PYTHONPATH="."
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
python scripts/build_match_features.py --dry-run
python scripts/build_match_features.py
```

By default this writes or updates one pre-match snapshot per local Asia/Shanghai day using `as_of_at=YYYY-MM-DDT00:00:00+08:00`. Re-running on the same day updates the same snapshot; passing `--as-of-at` stores a separate explicit snapshot for cases such as a T-90m lineup refresh.

By default this writes only matches where both teams have canonical Dongqiudi `DQD-P*` roster coverage. Use `--include-non-roster-matches` only for diagnostics, because non-roster matches are not training-ready.

The Dongqiudi homepage adapter stores a raw homepage snapshot, extracts World Cup match blocks and candidate football news, then normalizes them into canonical tables:

- `raw_snapshots`: immutable source payload and checksum.
- `collector_runs`: run status, record counts and linked snapshot ids.
- `news_items`: candidate news links from the homepage.
- `teams` / `team_aliases`: teams found in homepage match blocks.
- `matches`: World Cup homepage matches with score/status/kickoff fields.

Each adapter should emit the same canonical payload shape before normalization:

```python
{
    "matches": [
        {
            "public_id": "dongqiudi-home-away-2026-06-15",
            "competition_code": "world_cup_2026",
            "stage_code": "world-cup-homepage",
            "stage_name": "世界杯",
            "stage_type": "group",
            "home": "瑞典",
            "away": "突尼斯",
            "kickoff_at": "2026-06-15T00:00:00+08:00",
            "status": "live",
            "home_score": 3,
            "away_score": 1,
            "neutral_site": True,
            "source_confidence": 0.7,
        }
    ],
    "groups": [],
    "players": [],
    "items": [],
}
```

Homepage match data is used as the primary read source when `DATA_BACKEND=database` and at least one `dongqiudi-` match exists. Player form, team form, public market value, lineup stability and coach records now have real coverage from public sources. Player rows use a single canonical source: Dongqiudi `team/member_v2` with code `DQD-P{person_id}`. Source names and player ids map through `team_aliases` and `player_aliases`; exports should read canonical names from `teams` and `players`, not raw source-name columns.

Dongqiudi schedule rows are the canonical match source. Unresolved knockout placeholders stay in raw snapshots and are skipped from `matches` until both sides resolve to roster-backed national teams. Venue fields are shown only when a source-bound venue exists; the API no longer copies venue data from legacy fixture rows.

Dongqiudi sport-data normalizes World Cup 2026 group standings into `group_standings` and derived current-tournament `team_form_snapshots`. Player ranking data is normalized into `players` plus `player_form_snapshots`. Current player ranking fields cover goals, assists, shots, shots on target, key passes and matched EUR market values. `collect_dongqiudi_team_details.py` starts from the World Cup team list, then fetches each team page, `detail/team/{team_id}`, `team/member_v2/{team_id}` and the `cid=61` team ranking page APIs. It canonicalizes the national team first, then writes exactly one player row per Dongqiudi `person_id` as `DQD-P{person_id}`. It writes squad players, player avatars from `person_logo`, player market values, player appearance/goal/assist rows, team market values, Dongqiudi team aliases, coach/staff history and all available team-stat ranking metrics into `team_stat_snapshots` plus source links. These team-stat rows include cards, fouls, shots, passes, duels, saves, ratings and market value with both raw and numeric values for later model features. Historical `FIFA-*` player rows are removed during the run so prediction features consume only this one roster dataset.

All normalized data must have a provenance row in `data_source_links`. The collector runner writes these rows for canonical entities such as `match`, `venue`, `team`, `team_alias`, `group_standing`, `team_form`, `player`, `player_form` and `news_item`.

Backfill and audit source links after migrations or historical imports:

```powershell
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
python scripts/backfill_data_source_links.py
python scripts/backfill_identity_mappings.py
python scripts/audit_identity_mappings.py
python scripts/audit_real_data.py
```

The source-link audit should print `0` for every `*_without_source` check. The real-data audit must return `"status": "pass"` before data is used by the prediction pipeline or production mini program.

The executable collection matrix, source readiness, payload contracts, quality gates and acceptance tests are documented in `docs/world-cup-prediction/DATA_COLLECTION_PLAN.md`.
The operational refresh cadence is documented in `docs/world-cup-prediction/DATA_REFRESH_POLICY.md`. Weather refresh is fixed at 00:00 and 12:00 local time for the MVP; the 12:00 refresh also updates and exports the 48-team national-team match dataset. Matchday only raises news/injury/lineup priority and post-match refreshes.

Run the executable refresh scheduler:

```powershell
$env:PYTHONPATH="."
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
python scripts/run_refresh_schedule.py --cadence daily_00 --dry-run
python scripts/run_refresh_schedule.py --cadence daily_12
python scripts/run_refresh_schedule.py --cadence post_match
python scripts/run_refresh_schedule.py --cadence pre_match_90m
python scripts/run_refresh_schedule.py --cadence weekly
```

The scheduler writes its own `collector_runs` records with `source=scheduler`. Daily and weekly jobs use `job_type=refresh:{cadence}`; event jobs include the scoped match key. It uses PostgreSQL advisory locks so the same cadence cannot run concurrently. Use `--force` only for manual reruns after checking the previous run.

Admin API trigger:

```powershell
curl -X POST http://127.0.0.1:8001/api/admin/collectors/run `
  -H "Authorization: Bearer change-me" `
  -H "Content-Type: application/json" `
  -d '{"source":"dongqiudi","source_type":"homepage","dry_run":true}'
```

Refresh scheduler API trigger:

```powershell
curl -X POST http://127.0.0.1:8001/api/admin/refresh/run `
  -H "Authorization: Bearer change-me" `
  -H "Content-Type: application/json" `
  -d '{"cadence":"daily_12","dry_run":true}'
```

## Notes

Set `DATA_BACKEND=database` to read supported routes from PostgreSQL after schema and real source data are initialized.
