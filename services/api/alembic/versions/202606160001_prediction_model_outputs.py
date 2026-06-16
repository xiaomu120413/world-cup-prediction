"""Add model output fields and retain daily feature snapshots."""

from alembic import op

revision = "202606160001"
down_revision = "202606150008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        alter table match_predictions
            add column if not exists inference_mode varchar(64) not null default 'baseline',
            add column if not exists calibration_applied boolean not null default false,
            add column if not exists fallback_reason varchar(128),
            add column if not exists base_probabilities jsonb,
            add column if not exists feature_snapshot jsonb,
            add column if not exists feature_quality_status varchar(32),
            add column if not exists feature_missing_count int,
            add column if not exists feature_sources jsonb not null default '[]'::jsonb
        """
    )
    op.execute(
        """
        do $$
        begin
            if not exists (
                select 1 from pg_constraint where conname = 'inference_mode_valid'
            ) then
                alter table match_predictions
                    add constraint inference_mode_valid
                    check (inference_mode in ('baseline', 'context_calibrated', 'history_core_fallback', 'history_core'));
            end if;
        end $$;
        """
    )

    op.execute("alter table model_features drop constraint if exists uq_model_features_entity_feature_set")
    op.execute("alter table model_features drop constraint if exists model_features_entity_type_entity_key_feature_set_key")
    op.execute(
        """
        do $$
        begin
            if not exists (
                select 1 from pg_constraint where conname = 'uq_model_features_entity_feature_set_as_of'
            ) then
                alter table model_features
                    add constraint uq_model_features_entity_feature_set_as_of
                    unique (entity_type, entity_key, feature_set, as_of_at);
            end if;
        end $$;
        """
    )
    op.execute(
        """
        create index if not exists idx_model_features_latest
        on model_features(entity_type, entity_key, feature_set, as_of_at desc)
        """
    )


def downgrade() -> None:
    op.execute("drop index if exists idx_model_features_latest")
    op.execute("alter table model_features drop constraint if exists uq_model_features_entity_feature_set_as_of")
    op.execute(
        """
        delete from model_features a
        using model_features b
        where a.id < b.id
          and a.entity_type = b.entity_type
          and a.entity_key = b.entity_key
          and a.feature_set = b.feature_set
        """
    )
    op.execute(
        """
        alter table model_features
            add constraint uq_model_features_entity_feature_set
            unique (entity_type, entity_key, feature_set)
        """
    )
    op.execute("alter table match_predictions drop constraint if exists inference_mode_valid")
    op.execute(
        """
        alter table match_predictions
            drop column if exists feature_sources,
            drop column if exists feature_missing_count,
            drop column if exists feature_quality_status,
            drop column if exists feature_snapshot,
            drop column if exists base_probabilities,
            drop column if exists fallback_reason,
            drop column if exists calibration_applied,
            drop column if exists inference_mode
        """
    )
