# World Cup Prediction API

FastAPI backend for the World Cup prediction mini program.

Current scope:

- Public API contract with in-memory mock data.
- Health/version endpoints.
- Match, group, ranking, team and AI report endpoints.
- Admin task trigger placeholders.

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

## Notes

This M2 skeleton intentionally uses mock data. Database models, Alembic migrations, collectors and prediction jobs will be added after the API contract is stable.
