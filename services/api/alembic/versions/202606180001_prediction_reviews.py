"""Add prediction review metrics."""

from alembic import op

revision = "202606180001"
down_revision = "202606170001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        alter table ai_insights
            add column if not exists importance varchar(32) not null default 'rotation',
            add column if not exists impact_direction varchar(16) not null default 'neutral',
            add column if not exists impact_value_source varchar(32) not null default 'rule_mapping'
        """
    )
    op.execute("alter table ai_insights drop constraint if exists ai_insights_importance_valid")
    op.execute("alter table ai_insights drop constraint if exists ai_insights_impact_direction_valid")
    op.execute(
        """
        alter table ai_insights
            add constraint ai_insights_importance_valid check (importance in ('core', 'key', 'rotation')),
            add constraint ai_insights_impact_direction_valid check (impact_direction in ('positive', 'negative', 'neutral'))
        """
    )
    op.execute(
        """
        create table if not exists prediction_reviews (
            id uuid primary key default gen_random_uuid(),
            match_prediction_id uuid not null references match_predictions(id) on delete cascade,
            match_id uuid not null references matches(id) on delete cascade,
            prediction_snapshot_id uuid not null references prediction_snapshots(id) on delete cascade,
            model_version_id uuid not null references model_versions(id),
            actual_outcome varchar(16) not null,
            actual_home_goals integer not null,
            actual_away_goals integer not null,
            home_win_prob numeric(6, 5) not null,
            draw_prob numeric(6, 5) not null,
            away_win_prob numeric(6, 5) not null,
            actual_outcome_prob numeric(8, 6) not null,
            predicted_outcome varchar(16) not null,
            predicted_outcome_prob numeric(8, 6) not null,
            predicted_outcome_correct boolean not null,
            log_loss numeric(10, 6) not null,
            brier_score numeric(10, 6) not null,
            calibration_bucket integer not null,
            actual_scoreline_prob numeric(8, 6),
            top_scoreline_hit boolean,
            review_metadata jsonb not null default '{}'::jsonb,
            reviewed_at timestamptz not null default now(),
            constraint actual_outcome_valid check (actual_outcome in ('home_win', 'draw', 'away_win')),
            constraint predicted_outcome_valid check (predicted_outcome in ('home_win', 'draw', 'away_win')),
            constraint actual_outcome_prob_range check (actual_outcome_prob >= 0 and actual_outcome_prob <= 1),
            constraint predicted_outcome_prob_range check (predicted_outcome_prob >= 0 and predicted_outcome_prob <= 1),
            constraint calibration_bucket_range check (calibration_bucket >= 0 and calibration_bucket <= 9),
            constraint uq_prediction_reviews_match_prediction unique (match_prediction_id)
        )
        """
    )
    op.execute("create index if not exists idx_prediction_reviews_model on prediction_reviews(model_version_id, reviewed_at desc)")
    op.execute("create index if not exists idx_prediction_reviews_snapshot on prediction_reviews(prediction_snapshot_id)")
    op.execute("create index if not exists idx_prediction_reviews_match on prediction_reviews(match_id)")


def downgrade() -> None:
    op.execute("drop index if exists idx_prediction_reviews_match")
    op.execute("drop index if exists idx_prediction_reviews_snapshot")
    op.execute("drop index if exists idx_prediction_reviews_model")
    op.execute("drop table if exists prediction_reviews")
    op.execute("alter table ai_insights drop constraint if exists ai_insights_impact_direction_valid")
    op.execute("alter table ai_insights drop constraint if exists ai_insights_importance_valid")
    op.execute(
        """
        alter table ai_insights
            drop column if exists impact_value_source,
            drop column if exists impact_direction,
            drop column if exists importance
        """
    )
