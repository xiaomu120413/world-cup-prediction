# World Cup Prediction API

FastAPI backend for the World Cup prediction mini program.

Current scope:

- Public API contract with in-memory mock data.
- Health/version endpoints.
- Match, group, ranking, team and AI report endpoints.
- Admin task trigger placeholders.
- PostgreSQL schema, Alembic migration entrypoint and local seed script.

## Local Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open:

```text
http://127.0.0.1:8000/docs
```

If port 8000 is occupied locally, use:

```bash
uvicorn app.main:app --reload --port 8001
```

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

Or initialize schema and mock seed data directly:

```bash
python scripts/init_db.py
```

The first migration reuses `db/migrations/001_initial_schema.sql`, and mock data lives in `db/seeds/001_mock_data.sql`.

Run PostgreSQL-backed integration tests:

```powershell
$env:RUN_DATABASE_TESTS="1"
$env:DATA_BACKEND="database"
python -m pytest tests/test_database_backend.py
```

## Cache

Public database-backed read routes support optional Redis JSON caching.

The cache is disabled by default:

```text
CACHE_ENABLED=false
```

To enable it with the bundled Docker Compose Redis service:

```powershell
$env:CACHE_ENABLED="true"
$env:CACHE_TTL_SECONDS="60"
$env:REDIS_URL="redis://127.0.0.1:63791/0"
```

If Redis is unavailable, the API falls back to direct repository reads.

## Prediction Recompute

Run the deterministic MVP baseline locally:

```powershell
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
python scripts/recompute_predictions.py --scope matchday --match-id usa-paraguay-2026-06-13 --seed 20260615
```

Or trigger it through the admin API when `DATA_BACKEND=database`:

```powershell
curl -X POST http://127.0.0.1:8000/api/admin/predictions/recompute `
  -H "Authorization: Bearer change-me" `
  -H "Content-Type: application/json" `
  -d '{"scope":"matchday","match_ids":["usa-paraguay-2026-06-13"],"seed":20260615}'
```

## Collectors

Run the local sample collector to verify the raw snapshot and collector run flow:

```powershell
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
python scripts/run_collector.py --source local_sample --source-type schedule
```

Supported sample source types:

```text
schedule
standings
player_ranking
```

The first real low-frequency source adapter is also available:

```powershell
python scripts/run_collector.py --source dongqiudi --source-type homepage --dry-run
python scripts/run_collector.py --source dongqiudi --source-type homepage
```

The full World Cup 2026 static fixture source is available as a second real collector:

```powershell
python scripts/run_collector.py --source thestatsapi --source-type fixtures --dry-run
python scripts/run_collector.py --source thestatsapi --source-type fixtures
```

World Cup 2026 standings and player ranking data from Dongqiudi sport-data are available as:

```powershell
python scripts/run_collector.py --source dongqiudi --source-type world_cup_standings --dry-run
python scripts/run_collector.py --source dongqiudi --source-type world_cup_standings
python scripts/run_collector.py --source dongqiudi --source-type world_cup_player_rankings --dry-run
python scripts/run_collector.py --source dongqiudi --source-type world_cup_player_rankings
```

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

Homepage match data is used as the primary read source when `DATA_BACKEND=database` and at least one `dongqiudi-` match exists. Player form, team form, market value, lineup stability and coach records still need dedicated adapters or an authorized data source before they should be treated as production-grade.

TheStatsAPI fixtures normalize 104 scheduled matches plus venue name, city, country and timezone into `matches`, `teams`, `team_aliases` and `venues`. This source covers static schedule data only; it does not cover live scores, player form, standings or match stats.

Dongqiudi sport-data normalizes World Cup 2026 group standings into `group_standings` and derived current-tournament `team_form_snapshots`. Player ranking data is normalized into `players` plus `player_form_snapshots`. Current player ranking fields cover goals, assists, shots, shots on target, key passes and matched EUR market values; minutes, ratings, injuries and availability still need a dedicated source.

The executable collection matrix, source readiness, payload contracts, quality gates and acceptance tests are documented in `docs/world-cup-prediction/DATA_COLLECTION_PLAN.md`.

Admin API trigger:

```powershell
curl -X POST http://127.0.0.1:8000/api/admin/collectors/run `
  -H "Authorization: Bearer change-me" `
  -H "Content-Type: application/json" `
  -d '{"source":"local_sample","source_type":"schedule"}'
```

## Notes

Set `DATA_BACKEND=database` to read supported routes from PostgreSQL after schema and seed data are initialized.
