# World Cup Prediction Mini Program

World Cup pre-match prediction mini program with a FastAPI backend, PostgreSQL canonical data, real-source audit, prediction snapshots, and a Taro mini program/H5 frontend.

## Docs

Project documents live in [docs/world-cup-prediction](./docs/world-cup-prediction).

Core documents:

- [PRD](./docs/world-cup-prediction/PRD.md)
- [Architecture](./docs/world-cup-prediction/ARCHITECTURE.md)
- [Design](./docs/world-cup-prediction/DESIGN.md)
- [Data Model](./docs/world-cup-prediction/DATA_MODEL.md)
- [API Contract](./docs/world-cup-prediction/API_CONTRACT.md)
- [Functional Design](./docs/world-cup-prediction/FUNCTIONAL_DESIGN.md)
- [Technical Execution Plan](./docs/world-cup-prediction/TECHNICAL_EXECUTION_PLAN.md)
- [Execution Checklist](./docs/world-cup-prediction/EXECUTION_CHECKLIST.md)

## Apps

- [Miniapp](./apps/miniapp): Taro React mini program and H5 frontend. API builds read the database-backed service through `TARO_APP_API_BASE_URL`.

## Services

- [API](./services/api): FastAPI backend with PostgreSQL canonical tables, real-source audit, data collectors, feature snapshots, and prediction services.

## Current Status

- Database mode is the default runtime path.
- Core H5 pages are connected to the API: matches, match detail, groups, prediction rankings, and team detail.
- Real-data audit must pass before a build is treated as usable.
- Mock fixtures remain only for isolated contract tests and offline component development.

## Local Preview

Start the backend in database mode:

```powershell
cd services/api
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
$env:DATA_BACKEND="database"
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Build and serve H5:

```powershell
cd apps/miniapp
$env:TARO_APP_API_BASE_URL="http://127.0.0.1:8001"
npm.cmd run build:h5
cd dist
python -m http.server 4173
```

Open:

```text
http://127.0.0.1:4173
```
