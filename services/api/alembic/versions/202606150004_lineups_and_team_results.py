"""Add lineup and team result context tables."""

from alembic import op

revision = "202606150004"
down_revision = "202606150003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists lineup_snapshots (
            id uuid primary key default gen_random_uuid(),
            match_id uuid not null references matches(id) on delete cascade,
            team_id uuid not null references teams(id) on delete cascade,
            player_id uuid references players(id) on delete set null,
            source_player_id varchar(128),
            player_name varchar(128) not null,
            shirt_number int,
            position varchar(32),
            is_starting boolean not null default false,
            minutes int,
            rating numeric(4,2),
            status varchar(32) not null default 'unknown',
            source_confidence numeric(4,3) not null default 0.8,
            snapshot_id uuid references raw_snapshots(id) on delete set null,
            updated_at timestamptz not null default now(),
            constraint ck_lineup_snapshots_status_valid check (status in ('starter', 'substitute', 'bench', 'unknown')),
            constraint uq_lineup_snapshots_match_team_player unique (match_id, team_id, source_player_id, player_name)
        )
        """
    )
    op.execute("create index if not exists idx_lineup_snapshots_match_team on lineup_snapshots(match_id, team_id)")
    op.execute("create index if not exists idx_lineup_snapshots_team_player on lineup_snapshots(team_id, player_id)")
    op.execute(
        """
        create table if not exists team_match_results (
            id uuid primary key default gen_random_uuid(),
            team_id uuid not null references teams(id) on delete cascade,
            opponent_team_id uuid references teams(id) on delete set null,
            played_at timestamptz not null,
            competition_name varchar(128) not null,
            source_match_id varchar(128) not null,
            is_neutral boolean not null default true,
            goals_for int,
            goals_against int,
            result varchar(16) not null,
            opponent_rank int,
            opponent_rank_bucket varchar(16) not null default 'unknown',
            source_confidence numeric(4,3) not null default 0.8,
            snapshot_id uuid references raw_snapshots(id) on delete set null,
            updated_at timestamptz not null default now(),
            constraint ck_team_match_results_result_valid check (result in ('win', 'draw', 'loss', 'scheduled')),
            constraint ck_team_match_results_rank_bucket_valid check (
                opponent_rank_bucket in ('top10', 'top30', 'top50', 'other', 'unknown')
            ),
            constraint uq_team_match_results_team_match unique (team_id, source_match_id)
        )
        """
    )
    op.execute("create index if not exists idx_team_match_results_team_time on team_match_results(team_id, played_at desc)")


def downgrade() -> None:
    op.execute("drop index if exists idx_team_match_results_team_time")
    op.execute("drop table if exists team_match_results")
    op.execute("drop index if exists idx_lineup_snapshots_team_player")
    op.execute("drop index if exists idx_lineup_snapshots_match_team")
    op.execute("drop table if exists lineup_snapshots")
