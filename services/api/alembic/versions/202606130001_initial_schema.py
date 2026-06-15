from pathlib import Path

from alembic import op

revision = "202606130001"
down_revision = None
branch_labels = None
depends_on = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_SQL = PROJECT_ROOT / "db" / "migrations" / "001_initial_schema.sql"


def upgrade() -> None:
    op.execute("create extension if not exists pgcrypto")
    op.get_bind().exec_driver_sql(SCHEMA_SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute(
        """
        drop table if exists ai_explanations cascade;
        drop table if exists ai_insights cascade;
        drop table if exists news_items cascade;
        drop table if exists ranking_predictions cascade;
        drop table if exists group_simulations cascade;
        drop table if exists group_standings cascade;
        drop table if exists scoreline_predictions cascade;
        drop table if exists match_predictions cascade;
        drop table if exists prediction_snapshots cascade;
        drop table if exists model_versions cascade;
        drop table if exists player_form_snapshots cascade;
        drop table if exists team_form_snapshots cascade;
        drop table if exists collector_runs cascade;
        drop table if exists raw_snapshots cascade;
        drop table if exists matches cascade;
        drop table if exists venues cascade;
        drop table if exists players cascade;
        drop table if exists team_aliases cascade;
        drop table if exists teams cascade;
        drop table if exists competition_stages cascade;
        drop table if exists competitions cascade;
        """
    )
