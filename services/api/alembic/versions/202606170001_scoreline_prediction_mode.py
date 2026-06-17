"""Allow scoreline model prediction mode."""

from alembic import op

revision = "202606170001"
down_revision = "202606160001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table match_predictions drop constraint if exists inference_mode_valid")
    op.execute(
        """
        alter table match_predictions
            add constraint inference_mode_valid
            check (inference_mode in (
                'baseline',
                'context_calibrated',
                'history_core_fallback',
                'history_core',
                'scoreline_model'
            ))
        """
    )


def downgrade() -> None:
    op.execute("alter table match_predictions drop constraint if exists inference_mode_valid")
    op.execute(
        """
        alter table match_predictions
            add constraint inference_mode_valid
            check (inference_mode in (
                'baseline',
                'context_calibrated',
                'history_core_fallback',
                'history_core'
            ))
        """
    )
