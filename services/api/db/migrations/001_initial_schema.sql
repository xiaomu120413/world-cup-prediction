create extension if not exists pgcrypto;

create table if not exists competitions (
    id uuid primary key default gen_random_uuid(),
    code varchar(64) not null unique,
    name varchar(128) not null,
    host_countries jsonb not null default '[]'::jsonb,
    start_date date not null,
    end_date date not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists competition_stages (
    id uuid primary key default gen_random_uuid(),
    competition_id uuid not null references competitions(id) on delete cascade,
    code varchar(64) not null,
    name varchar(128) not null,
    stage_type varchar(32) not null check (stage_type in ('group', 'knockout')),
    sort_order int not null default 0,
    unique (competition_id, code)
);

create table if not exists teams (
    id uuid primary key default gen_random_uuid(),
    code varchar(32) not null unique,
    name_zh varchar(128) not null,
    name_en varchar(128),
    confederation varchar(32),
    fifa_rank int,
    elo_rating numeric(8,2),
    market_value_eur numeric(14,2),
    quality_status varchar(32) not null default 'estimated',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_teams_rank on teams(fifa_rank);
create index if not exists idx_teams_elo on teams(elo_rating);

create table if not exists team_aliases (
    id uuid primary key default gen_random_uuid(),
    team_id uuid not null references teams(id) on delete cascade,
    source varchar(64) not null,
    source_team_id varchar(128),
    alias varchar(128) not null,
    confidence numeric(4,3) not null default 1.0,
    is_primary boolean not null default false,
    unique (source, source_team_id),
    unique (source, alias)
);

create table if not exists players (
    id uuid primary key default gen_random_uuid(),
    team_id uuid not null references teams(id) on delete cascade,
    code varchar(64) not null unique,
    name_zh varchar(128) not null,
    name_en varchar(128),
    position varchar(32),
    shirt_number int,
    birth_date date,
    club_name varchar(128),
    market_value_eur numeric(14,2),
    is_key_player boolean not null default false,
    quality_status varchar(32) not null default 'estimated',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_players_team_position on players(team_id, position);

create table if not exists venues (
    id uuid primary key default gen_random_uuid(),
    code varchar(64) not null unique,
    name varchar(128) not null,
    city varchar(128) not null,
    country varchar(128) not null,
    timezone varchar(64) not null,
    capacity int,
    altitude_m int,
    surface varchar(64),
    weather_profile jsonb
);

create table if not exists matches (
    id uuid primary key default gen_random_uuid(),
    public_id varchar(128) not null unique,
    competition_id uuid not null references competitions(id) on delete cascade,
    stage_id uuid not null references competition_stages(id) on delete cascade,
    home_team_id uuid not null references teams(id),
    away_team_id uuid not null references teams(id),
    venue_id uuid references venues(id),
    kickoff_at timestamptz not null,
    status varchar(32) not null default 'scheduled',
    home_score int,
    away_score int,
    neutral_site boolean not null default true,
    source_confidence numeric(4,3) not null default 1.0,
    updated_at timestamptz not null default now(),
    check (home_team_id <> away_team_id),
    check (status in ('scheduled', 'live', 'finished', 'postponed'))
);

create index if not exists idx_matches_kickoff on matches(kickoff_at);
create index if not exists idx_matches_status on matches(status);
create index if not exists idx_matches_stage on matches(stage_id);

create table if not exists raw_snapshots (
    id uuid primary key default gen_random_uuid(),
    source varchar(64) not null,
    source_url text,
    source_type varchar(64) not null,
    fetched_at timestamptz not null default now(),
    checksum varchar(128) not null,
    payload jsonb not null,
    parser_version varchar(64) not null,
    unique (source, source_type, checksum)
);

create table if not exists data_source_links (
    id uuid primary key default gen_random_uuid(),
    entity_type varchar(64) not null,
    entity_key varchar(256) not null,
    source varchar(64) not null,
    source_type varchar(64) not null,
    source_url text,
    raw_snapshot_id uuid references raw_snapshots(id) on delete set null,
    source_record_id varchar(128),
    confidence numeric(4,3) not null default 1.0,
    fetched_at timestamptz not null default now(),
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (entity_type, entity_key, source, source_type)
);

create index if not exists idx_data_source_links_entity on data_source_links(entity_type, entity_key);
create index if not exists idx_data_source_links_raw_snapshot on data_source_links(raw_snapshot_id);

create table if not exists collector_runs (
    id uuid primary key default gen_random_uuid(),
    source varchar(64) not null,
    job_type varchar(64) not null,
    status varchar(32) not null,
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    records_read int not null default 0,
    records_written int not null default 0,
    error_message text,
    snapshot_ids uuid[],
    check (status in ('success', 'failed', 'partial'))
);

create table if not exists team_form_snapshots (
    id uuid primary key default gen_random_uuid(),
    team_id uuid not null references teams(id) on delete cascade,
    as_of_at timestamptz not null,
    recent_matches int not null default 10,
    points_per_match numeric(5,2),
    goals_for_per_match numeric(5,2),
    goals_against_per_match numeric(5,2),
    lineup_stability_score numeric(5,2),
    injury_impact_score numeric(5,2),
    data_quality varchar(32) not null default 'partial'
);

create index if not exists idx_team_form_team_time on team_form_snapshots(team_id, as_of_at desc);

create table if not exists player_form_snapshots (
    id uuid primary key default gen_random_uuid(),
    player_id uuid not null references players(id) on delete cascade,
    team_id uuid not null references teams(id) on delete cascade,
    as_of_at timestamptz not null,
    recent_matches int not null default 10,
    minutes int,
    goals int,
    assists int,
    shots int,
    key_passes int,
    rating numeric(4,2),
    availability_status varchar(32) not null default 'available',
    form_score numeric(5,2),
    source_count int not null default 1
);

create index if not exists idx_player_form_player_time on player_form_snapshots(player_id, as_of_at desc);

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
    status varchar(32) not null default 'unknown' check (status in ('starter', 'substitute', 'bench', 'unknown')),
    source_confidence numeric(4,3) not null default 0.8,
    snapshot_id uuid references raw_snapshots(id) on delete set null,
    updated_at timestamptz not null default now(),
    unique (match_id, team_id, source_player_id, player_name)
);

create index if not exists idx_lineup_snapshots_match_team on lineup_snapshots(match_id, team_id);
create index if not exists idx_lineup_snapshots_team_player on lineup_snapshots(team_id, player_id);

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
    result varchar(16) not null check (result in ('win', 'draw', 'loss', 'scheduled')),
    opponent_rank int,
    opponent_rank_bucket varchar(16) not null default 'unknown' check (opponent_rank_bucket in ('top10', 'top30', 'top50', 'other', 'unknown')),
    source_confidence numeric(4,3) not null default 0.8,
    snapshot_id uuid references raw_snapshots(id) on delete set null,
    updated_at timestamptz not null default now(),
    unique (team_id, source_match_id)
);

create index if not exists idx_team_match_results_team_time on team_match_results(team_id, played_at desc);

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
    unique (team_id, name_zh)
);

create index if not exists idx_coaches_team on coaches(team_id);

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
    unique (venue_id, provider, observed_at)
);

create index if not exists idx_weather_snapshots_venue_time on weather_snapshots(venue_id, observed_at desc);

create table if not exists injury_reports (
    id uuid primary key default gen_random_uuid(),
    team_id uuid not null references teams(id) on delete cascade,
    player_id uuid references players(id) on delete set null,
    report_type varchar(32) not null check (report_type in ('injury', 'suspension', 'fitness')),
    status varchar(32) not null check (status in ('confirmed', 'doubtful', 'returned', 'suspended')),
    impact_score numeric(5,2),
    started_at date,
    expected_return_at date,
    source_url text not null,
    confidence numeric(4,3) not null,
    evidence_text text not null,
    is_model_eligible boolean not null default false,
    updated_at timestamptz not null default now()
);

create index if not exists idx_injury_reports_team_status on injury_reports(team_id, status);

create table if not exists model_versions (
    id uuid primary key default gen_random_uuid(),
    name varchar(128) not null,
    version varchar(64) not null,
    model_type varchar(64) not null,
    training_data_start date,
    training_data_end date,
    feature_schema jsonb not null default '{}'::jsonb,
    metrics jsonb,
    is_active boolean not null default false,
    created_at timestamptz not null default now(),
    unique (name, version)
);

create table if not exists prediction_snapshots (
    id uuid primary key default gen_random_uuid(),
    model_version_id uuid not null references model_versions(id),
    data_snapshot_id uuid references raw_snapshots(id),
    generated_at timestamptz not null default now(),
    scope varchar(64) not null,
    status varchar(32) not null,
    seed int,
    notes text,
    check (status in ('success', 'failed'))
);

create table if not exists match_predictions (
    id uuid primary key default gen_random_uuid(),
    match_id uuid not null references matches(id) on delete cascade,
    prediction_snapshot_id uuid not null references prediction_snapshots(id) on delete cascade,
    model_version_id uuid not null references model_versions(id),
    home_win_prob numeric(6,5) not null,
    draw_prob numeric(6,5) not null,
    away_win_prob numeric(6,5) not null,
    home_expected_goals numeric(5,2) not null,
    away_expected_goals numeric(5,2) not null,
    confidence varchar(32) not null,
    key_factors jsonb not null default '[]'::jsonb,
    generated_at timestamptz not null default now(),
    check (home_win_prob >= 0 and home_win_prob <= 1),
    check (draw_prob >= 0 and draw_prob <= 1),
    check (away_win_prob >= 0 and away_win_prob <= 1),
    check (abs((home_win_prob + draw_prob + away_win_prob) - 1) < 0.001)
);

create index if not exists idx_match_predictions_match on match_predictions(match_id, generated_at desc);

create table if not exists scoreline_predictions (
    id uuid primary key default gen_random_uuid(),
    match_prediction_id uuid not null references match_predictions(id) on delete cascade,
    home_goals int not null,
    away_goals int not null,
    probability numeric(6,5) not null,
    rank int not null,
    unique (match_prediction_id, home_goals, away_goals)
);

create table if not exists group_standings (
    id uuid primary key default gen_random_uuid(),
    stage_id uuid not null references competition_stages(id) on delete cascade,
    team_id uuid not null references teams(id),
    played int not null default 0,
    wins int not null default 0,
    draws int not null default 0,
    losses int not null default 0,
    goals_for int not null default 0,
    goals_against int not null default 0,
    goal_diff int not null default 0,
    points int not null default 0,
    rank int not null,
    snapshot_id uuid references raw_snapshots(id),
    updated_at timestamptz not null default now()
);

create table if not exists group_simulations (
    id uuid primary key default gen_random_uuid(),
    stage_id uuid not null references competition_stages(id) on delete cascade,
    prediction_snapshot_id uuid not null references prediction_snapshots(id) on delete cascade,
    team_id uuid not null references teams(id),
    rank_1_prob numeric(6,5) not null,
    rank_2_prob numeric(6,5) not null,
    qualify_prob numeric(6,5) not null,
    expected_points numeric(5,2) not null,
    unique (stage_id, prediction_snapshot_id, team_id)
);

create table if not exists ranking_predictions (
    id uuid primary key default gen_random_uuid(),
    prediction_snapshot_id uuid not null references prediction_snapshots(id) on delete cascade,
    ranking_type varchar(32) not null,
    team_id uuid not null references teams(id),
    probability numeric(6,5) not null,
    delta numeric(6,5),
    rank int not null,
    reason varchar(128),
    check (ranking_type in ('champion', 'semifinal', 'darkhorse'))
);

create table if not exists news_items (
    id uuid primary key default gen_random_uuid(),
    source varchar(64) not null,
    source_url text not null unique,
    title text not null,
    summary text,
    language varchar(16) not null default 'zh',
    published_at timestamptz,
    fetched_at timestamptz not null default now(),
    related_team_ids uuid[],
    related_player_ids uuid[],
    checksum varchar(128) not null unique
);

create table if not exists ai_insights (
    id uuid primary key default gen_random_uuid(),
    news_item_id uuid references news_items(id) on delete set null,
    event_type varchar(64) not null,
    team_id uuid references teams(id),
    player_id uuid references players(id),
    match_id uuid references matches(id),
    impact_area varchar(64) not null,
    impact_score numeric(5,2) not null,
    confidence numeric(4,3) not null,
    evidence_text text not null,
    source_url text,
    is_model_eligible boolean not null default false,
    created_at timestamptz not null default now()
);

create table if not exists ai_explanations (
    id uuid primary key default gen_random_uuid(),
    target_type varchar(32) not null,
    target_id uuid not null,
    prediction_snapshot_id uuid references prediction_snapshots(id),
    title varchar(128) not null,
    content text not null,
    confidence_label varchar(32) not null,
    evidence_refs jsonb not null default '[]'::jsonb,
    generated_at timestamptz not null default now()
);
