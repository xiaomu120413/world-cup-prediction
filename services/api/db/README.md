# Database

PostgreSQL schema files for the World Cup prediction API.

Current scope:

- `migrations/001_initial_schema.sql`: MVP tables for teams, matches, predictions, groups, news and AI explanations.

## Local Apply

```bash
psql "$DATABASE_URL" -f db/migrations/001_initial_schema.sql
```

Alembic can be added after the raw schema stabilizes.
