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

Run migrations:

```bash
alembic upgrade head
```

Or initialize schema and mock seed data directly:

```bash
python scripts/init_db.py
```

The first migration reuses `db/migrations/001_initial_schema.sql`, and mock data lives in `db/seeds/001_mock_data.sql`.

## Notes

Public routes still read mock data while the database layer is being wired in. The next step is replacing route reads with repository queries and keeping the same response contract.
Set `DATA_BACKEND=database` to read supported routes from PostgreSQL after schema and seed data are initialized.
