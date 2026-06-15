"""Add historical international match records."""

from alembic import op

revision = "202606150006"
down_revision = "202606150005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists historical_international_matches (
            id uuid primary key default gen_random_uuid(),
            source_match_id varchar(128) not null,
            match_date date not null,
            played_at timestamptz not null,
            home_team_id uuid not null references teams(id) on delete cascade,
            away_team_id uuid not null references teams(id) on delete cascade,
            home_team_name varchar(128) not null,
            away_team_name varchar(128) not null,
            home_score int not null,
            away_score int not null,
            tournament varchar(128) not null,
            city varchar(128),
            country varchar(128),
            neutral boolean not null default true,
            source varchar(64) not null,
            source_type varchar(64) not null,
            source_url text,
            source_line_number int,
            source_confidence numeric(4,3) not null default 0.9,
            snapshot_id uuid references raw_snapshots(id) on delete set null,
            metadata jsonb not null default '{}'::jsonb,
            updated_at timestamptz not null default now(),
            constraint ck_historical_international_matches_different_teams check (home_team_id <> away_team_id),
            constraint ck_historical_international_matches_non_negative_score check (home_score >= 0 and away_score >= 0),
            constraint uq_historical_international_matches_source_match unique (source_match_id)
        )
        """
    )
    op.execute(
        "create index if not exists idx_historical_international_matches_date "
        "on historical_international_matches(match_date desc)"
    )
    op.execute(
        "create index if not exists idx_historical_international_matches_home_team "
        "on historical_international_matches(home_team_id, match_date desc)"
    )
    op.execute(
        "create index if not exists idx_historical_international_matches_away_team "
        "on historical_international_matches(away_team_id, match_date desc)"
    )
    op.execute(
        "create index if not exists idx_historical_international_matches_tournament "
        "on historical_international_matches(tournament)"
    )


def downgrade() -> None:
    op.execute("drop index if exists idx_historical_international_matches_tournament")
    op.execute("drop index if exists idx_historical_international_matches_away_team")
    op.execute("drop index if exists idx_historical_international_matches_home_team")
    op.execute("drop index if exists idx_historical_international_matches_date")
    op.execute("drop table if exists historical_international_matches")
