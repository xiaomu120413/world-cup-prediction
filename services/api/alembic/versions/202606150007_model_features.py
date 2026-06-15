"""Add model feature snapshots."""

from alembic import op

revision = "202606150007"
down_revision = "202606150006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists model_features (
            id uuid primary key default gen_random_uuid(),
            entity_type varchar(32) not null,
            entity_key varchar(128) not null,
            feature_set varchar(64) not null,
            feature_schema_version varchar(64) not null,
            as_of_at timestamptz not null,
            features jsonb not null default '{}'::jsonb,
            source_summary jsonb not null default '{}'::jsonb,
            missing_features jsonb not null default '[]'::jsonb,
            quality_status varchar(32) not null,
            generated_at timestamptz not null default now(),
            constraint ck_model_features_entity_type_valid check (entity_type in ('match', 'team', 'player')),
            constraint ck_model_features_quality_status_valid check (quality_status in ('complete', 'partial', 'insufficient')),
            constraint uq_model_features_entity_feature_set unique (entity_type, entity_key, feature_set)
        )
        """
    )
    op.execute("create index if not exists idx_model_features_entity on model_features(entity_type, entity_key)")
    op.execute("create index if not exists idx_model_features_feature_set on model_features(feature_set)")


def downgrade() -> None:
    op.execute("drop index if exists idx_model_features_feature_set")
    op.execute("drop index if exists idx_model_features_entity")
    op.execute("drop table if exists model_features")
