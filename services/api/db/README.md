# Database

PostgreSQL schema and seed files for the World Cup prediction API.

Current scope:

- `migrations/001_initial_schema.sql`: MVP tables for teams, matches, predictions, groups, news and AI explanations.
- `seeds/001_mock_data.sql`: small seed dataset matching the current API mock response.

## Local Apply

```bash
psql "$DATABASE_URL" -f db/migrations/001_initial_schema.sql
psql "$DATABASE_URL" -f db/seeds/001_mock_data.sql
```

Alembic can be added after the raw schema stabilizes.

