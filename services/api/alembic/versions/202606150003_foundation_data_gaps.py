from alembic import op

revision = "202606150003"
down_revision = "202606150002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists coaches (
            id uuid primary key default gen_random_uuid(),
            team_id uuid not null references teams(id) on delete cascade,
            name_zh varchar(128) not null,
            name_en varchar(128),
            started_at date,
            matches_count int,
            wins int,
            draws int,
            losses int,
            win_rate numeric(5,2),
            major_tournament_record jsonb not null default '{}'::jsonb,
            source_confidence numeric(4,3) not null default 1.0,
            quality_status varchar(32) not null default 'partial',
            updated_at timestamptz not null default now(),
            constraint uq_coaches_team_name unique (team_id, name_zh)
        )
        """
    )
    op.execute("create index if not exists idx_coaches_team on coaches(team_id)")

    op.execute(
        """
        create table if not exists weather_snapshots (
            id uuid primary key default gen_random_uuid(),
            venue_id uuid not null references venues(id) on delete cascade,
            observed_at timestamptz not null,
            provider varchar(64) not null,
            temperature_c numeric(5,2),
            humidity_pct int,
            precipitation_mm numeric(6,2),
            wind_speed_kph numeric(6,2),
            wind_direction_deg int,
            weather_code int,
            source_url text,
            data_quality varchar(64) not null default 'current_observation',
            created_at timestamptz not null default now(),
            constraint uq_weather_snapshots_venue_provider_time unique (venue_id, provider, observed_at)
        )
        """
    )
    op.execute("create index if not exists idx_weather_snapshots_venue_time on weather_snapshots(venue_id, observed_at desc)")

    op.execute(
        """
        create table if not exists injury_reports (
            id uuid primary key default gen_random_uuid(),
            team_id uuid not null references teams(id) on delete cascade,
            player_id uuid references players(id) on delete set null,
            report_type varchar(32) not null,
            status varchar(32) not null,
            impact_score numeric(5,2),
            started_at date,
            expected_return_at date,
            source_url text not null,
            confidence numeric(4,3) not null,
            evidence_text text not null,
            is_model_eligible boolean not null default false,
            updated_at timestamptz not null default now(),
            constraint ck_injury_reports_report_type_valid check (report_type in ('injury', 'suspension', 'fitness')),
            constraint ck_injury_reports_status_valid check (status in ('confirmed', 'doubtful', 'returned', 'suspended'))
        )
        """
    )
    op.execute("create index if not exists idx_injury_reports_team_status on injury_reports(team_id, status)")


def downgrade() -> None:
    op.execute("drop index if exists idx_injury_reports_team_status")
    op.execute("drop table if exists injury_reports")
    op.execute("drop index if exists idx_weather_snapshots_venue_time")
    op.execute("drop table if exists weather_snapshots")
    op.execute("drop index if exists idx_coaches_team")
    op.execute("drop table if exists coaches")
