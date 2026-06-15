"""Add structured team stat snapshots."""

from alembic import op

revision = "202606150005"
down_revision = "202606150004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists team_stat_snapshots (
            id uuid primary key default gen_random_uuid(),
            team_id uuid not null references teams(id) on delete cascade,
            metric_type varchar(64) not null,
            metric_name varchar(128) not null,
            rank int,
            raw_value varchar(64),
            numeric_value numeric(18,4),
            value_unit varchar(32),
            source varchar(64) not null,
            source_type varchar(64) not null,
            source_team_id varchar(128),
            source_url text,
            source_confidence numeric(4,3) not null default 0.8,
            snapshot_id uuid references raw_snapshots(id) on delete set null,
            as_of_at timestamptz not null,
            metadata jsonb not null default '{}'::jsonb,
            updated_at timestamptz not null default now(),
            constraint uq_team_stat_snapshots_team_metric_time_source unique (team_id, metric_type, as_of_at, source)
        )
        """
    )
    op.execute(
        "create index if not exists idx_team_stat_snapshots_team_metric "
        "on team_stat_snapshots(team_id, metric_type)"
    )
    op.execute(
        "create index if not exists idx_team_stat_snapshots_metric_rank "
        "on team_stat_snapshots(metric_type, rank)"
    )


def downgrade() -> None:
    op.execute("drop index if exists idx_team_stat_snapshots_metric_rank")
    op.execute("drop index if exists idx_team_stat_snapshots_team_metric")
    op.execute("drop table if exists team_stat_snapshots")
