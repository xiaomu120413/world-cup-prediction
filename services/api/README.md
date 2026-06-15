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

Admin API trigger:

```powershell
curl -X POST http://127.0.0.1:8000/api/admin/collectors/run `
  -H "Authorization: Bearer change-me" `
  -H "Content-Type: application/json" `
  -d '{"source":"local_sample","source_type":"schedule"}'
```

## Notes

Set `DATA_BACKEND=database` to read supported routes from PostgreSQL after schema and seed data are initialized.
