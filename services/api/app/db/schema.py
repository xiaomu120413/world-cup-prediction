from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID, VARCHAR

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


def uuid_pk() -> Column:
    return Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


competitions = Table(
    "competitions",
    metadata,
    uuid_pk(),
    Column("code", VARCHAR(64), nullable=False, unique=True),
    Column("name", VARCHAR(128), nullable=False),
    Column("host_countries", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("start_date", Date, nullable=False),
    Column("end_date", Date, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
)

competition_stages = Table(
    "competition_stages",
    metadata,
    uuid_pk(),
    Column("competition_id", UUID(as_uuid=True), ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False),
    Column("code", VARCHAR(64), nullable=False),
    Column("name", VARCHAR(128), nullable=False),
    Column("stage_type", VARCHAR(32), nullable=False),
    Column("sort_order", Integer, nullable=False, server_default=text("0")),
    CheckConstraint("stage_type in ('group', 'knockout')", name="stage_type_valid"),
    UniqueConstraint("competition_id", "code", name="uq_competition_stages_competition_code"),
)

teams = Table(
    "teams",
    metadata,
    uuid_pk(),
    Column("code", VARCHAR(32), nullable=False, unique=True),
    Column("name_zh", VARCHAR(128), nullable=False),
    Column("name_en", VARCHAR(128)),
    Column("confederation", VARCHAR(32)),
    Column("fifa_rank", Integer),
    Column("elo_rating", Numeric(8, 2)),
    Column("market_value_eur", Numeric(14, 2)),
    Column("quality_status", VARCHAR(32), nullable=False, server_default=text("'estimated'")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
)
Index("idx_teams_rank", teams.c.fifa_rank)
Index("idx_teams_elo", teams.c.elo_rating)

team_aliases = Table(
    "team_aliases",
    metadata,
    uuid_pk(),
    Column("team_id", UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
    Column("source", VARCHAR(64), nullable=False),
    Column("source_team_id", VARCHAR(128)),
    Column("alias", VARCHAR(128), nullable=False),
    Column("confidence", Numeric(4, 3), nullable=False, server_default=text("1.0")),
    Column("is_primary", Boolean, nullable=False, server_default=text("false")),
    UniqueConstraint("source", "source_team_id", name="uq_team_aliases_source_team_id"),
    UniqueConstraint("source", "alias", name="uq_team_aliases_source_alias"),
)

players = Table(
    "players",
    metadata,
    uuid_pk(),
    Column("team_id", UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
    Column("code", VARCHAR(64), nullable=False, unique=True),
    Column("name_zh", VARCHAR(128), nullable=False),
    Column("name_en", VARCHAR(128)),
    Column("position", VARCHAR(32)),
    Column("shirt_number", Integer),
    Column("birth_date", Date),
    Column("club_name", VARCHAR(128)),
    Column("market_value_eur", Numeric(14, 2)),
    Column("is_key_player", Boolean, nullable=False, server_default=text("false")),
    Column("quality_status", VARCHAR(32), nullable=False, server_default=text("'estimated'")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
)
Index("idx_players_team_position", players.c.team_id, players.c.position)

player_aliases = Table(
    "player_aliases",
    metadata,
    uuid_pk(),
    Column("player_id", UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
    Column("team_id", UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
    Column("source", VARCHAR(64), nullable=False),
    Column("source_player_id", VARCHAR(128)),
    Column("alias", VARCHAR(128), nullable=False),
    Column("confidence", Numeric(4, 3), nullable=False, server_default=text("1.0")),
    Column("is_primary", Boolean, nullable=False, server_default=text("false")),
    UniqueConstraint("source", "source_player_id", name="uq_player_aliases_source_player_id"),
)
Index("idx_player_aliases_source_team_alias", player_aliases.c.source, player_aliases.c.team_id, player_aliases.c.alias)
Index("idx_player_aliases_player", player_aliases.c.player_id)

venues = Table(
    "venues",
    metadata,
    uuid_pk(),
    Column("code", VARCHAR(64), nullable=False, unique=True),
    Column("name", VARCHAR(128), nullable=False),
    Column("city", VARCHAR(128), nullable=False),
    Column("country", VARCHAR(128), nullable=False),
    Column("timezone", VARCHAR(64), nullable=False),
    Column("capacity", Integer),
    Column("altitude_m", Integer),
    Column("surface", VARCHAR(64)),
    Column("weather_profile", JSONB),
)

matches = Table(
    "matches",
    metadata,
    uuid_pk(),
    Column("public_id", VARCHAR(128), nullable=False, unique=True),
    Column("competition_id", UUID(as_uuid=True), ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False),
    Column("stage_id", UUID(as_uuid=True), ForeignKey("competition_stages.id", ondelete="CASCADE"), nullable=False),
    Column("home_team_id", UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False),
    Column("away_team_id", UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False),
    Column("venue_id", UUID(as_uuid=True), ForeignKey("venues.id")),
    Column("kickoff_at", DateTime(timezone=True), nullable=False),
    Column("status", VARCHAR(32), nullable=False, server_default=text("'scheduled'")),
    Column("home_score", Integer),
    Column("away_score", Integer),
    Column("neutral_site", Boolean, nullable=False, server_default=text("true")),
    Column("source_confidence", Numeric(4, 3), nullable=False, server_default=text("1.0")),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    CheckConstraint("home_team_id <> away_team_id", name="different_teams"),
    CheckConstraint("status in ('scheduled', 'live', 'finished', 'postponed')", name="status_valid"),
)
Index("idx_matches_kickoff", matches.c.kickoff_at)
Index("idx_matches_status", matches.c.status)
Index("idx_matches_stage", matches.c.stage_id)

raw_snapshots = Table(
    "raw_snapshots",
    metadata,
    uuid_pk(),
    Column("source", VARCHAR(64), nullable=False),
    Column("source_url", Text),
    Column("source_type", VARCHAR(64), nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    Column("checksum", VARCHAR(128), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("parser_version", VARCHAR(64), nullable=False),
    UniqueConstraint("source", "source_type", "checksum", name="uq_raw_snapshots_source_type_checksum"),
)

data_source_links = Table(
    "data_source_links",
    metadata,
    uuid_pk(),
    Column("entity_type", VARCHAR(64), nullable=False),
    Column("entity_key", VARCHAR(256), nullable=False),
    Column("source", VARCHAR(64), nullable=False),
    Column("source_type", VARCHAR(64), nullable=False),
    Column("source_url", Text),
    Column("raw_snapshot_id", UUID(as_uuid=True), ForeignKey("raw_snapshots.id", ondelete="SET NULL")),
    Column("source_record_id", VARCHAR(128)),
    Column("confidence", Numeric(4, 3), nullable=False, server_default=text("1.0")),
    Column("fetched_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    UniqueConstraint("entity_type", "entity_key", "source", "source_type", name="uq_data_source_links_entity_source"),
)
Index("idx_data_source_links_entity", data_source_links.c.entity_type, data_source_links.c.entity_key)
Index("idx_data_source_links_raw_snapshot", data_source_links.c.raw_snapshot_id)

collector_runs = Table(
    "collector_runs",
    metadata,
    uuid_pk(),
    Column("source", VARCHAR(64), nullable=False),
    Column("job_type", VARCHAR(64), nullable=False),
    Column("status", VARCHAR(32), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    Column("finished_at", DateTime(timezone=True)),
    Column("records_read", Integer, nullable=False, server_default=text("0")),
    Column("records_written", Integer, nullable=False, server_default=text("0")),
    Column("error_message", Text),
    Column("snapshot_ids", ARRAY(UUID(as_uuid=True))),
    CheckConstraint("status in ('success', 'failed', 'partial')", name="status_valid"),
)

team_form_snapshots = Table(
    "team_form_snapshots",
    metadata,
    uuid_pk(),
    Column("team_id", UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
    Column("as_of_at", DateTime(timezone=True), nullable=False),
    Column("recent_matches", Integer, nullable=False, server_default=text("10")),
    Column("points_per_match", Numeric(5, 2)),
    Column("goals_for_per_match", Numeric(5, 2)),
    Column("goals_against_per_match", Numeric(5, 2)),
    Column("lineup_stability_score", Numeric(5, 2)),
    Column("injury_impact_score", Numeric(5, 2)),
    Column("data_quality", VARCHAR(32), nullable=False, server_default=text("'partial'")),
)
Index("idx_team_form_team_time", team_form_snapshots.c.team_id, team_form_snapshots.c.as_of_at.desc())

player_form_snapshots = Table(
    "player_form_snapshots",
    metadata,
    uuid_pk(),
    Column("player_id", UUID(as_uuid=True), ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
    Column("team_id", UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
    Column("as_of_at", DateTime(timezone=True), nullable=False),
    Column("recent_matches", Integer, nullable=False, server_default=text("10")),
    Column("minutes", Integer),
    Column("goals", Integer),
    Column("assists", Integer),
    Column("shots", Integer),
    Column("key_passes", Integer),
    Column("rating", Numeric(4, 2)),
    Column("availability_status", VARCHAR(32), nullable=False, server_default=text("'available'")),
    Column("form_score", Numeric(5, 2)),
    Column("source_count", Integer, nullable=False, server_default=text("1")),
)
Index("idx_player_form_player_time", player_form_snapshots.c.player_id, player_form_snapshots.c.as_of_at.desc())

lineup_snapshots = Table(
    "lineup_snapshots",
    metadata,
    uuid_pk(),
    Column("match_id", UUID(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
    Column("team_id", UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
    Column("player_id", UUID(as_uuid=True), ForeignKey("players.id", ondelete="SET NULL")),
    Column("source_player_id", VARCHAR(128)),
    Column("player_name", VARCHAR(128), nullable=False),
    Column("shirt_number", Integer),
    Column("position", VARCHAR(32)),
    Column("is_starting", Boolean, nullable=False, server_default=text("false")),
    Column("minutes", Integer),
    Column("rating", Numeric(4, 2)),
    Column("status", VARCHAR(32), nullable=False, server_default=text("'unknown'")),
    Column("source_confidence", Numeric(4, 3), nullable=False, server_default=text("0.8")),
    Column("snapshot_id", UUID(as_uuid=True), ForeignKey("raw_snapshots.id", ondelete="SET NULL")),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    CheckConstraint("status in ('starter', 'substitute', 'bench', 'unknown')", name="status_valid"),
    UniqueConstraint("match_id", "team_id", "source_player_id", "player_name", name="uq_lineup_snapshots_match_team_player"),
)
Index("idx_lineup_snapshots_match_team", lineup_snapshots.c.match_id, lineup_snapshots.c.team_id)
Index("idx_lineup_snapshots_team_player", lineup_snapshots.c.team_id, lineup_snapshots.c.player_id)

historical_international_matches = Table(
    "historical_international_matches",
    metadata,
    uuid_pk(),
    Column("source_match_id", VARCHAR(128), nullable=False),
    Column("match_date", Date, nullable=False),
    Column("played_at", DateTime(timezone=True), nullable=False),
    Column("home_team_id", UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
    Column("away_team_id", UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
    Column("home_team_name", VARCHAR(128), nullable=False),
    Column("away_team_name", VARCHAR(128), nullable=False),
    Column("home_score", Integer, nullable=False),
    Column("away_score", Integer, nullable=False),
    Column("tournament", VARCHAR(128), nullable=False),
    Column("city", VARCHAR(128)),
    Column("country", VARCHAR(128)),
    Column("neutral", Boolean, nullable=False, server_default=text("true")),
    Column("source", VARCHAR(64), nullable=False),
    Column("source_type", VARCHAR(64), nullable=False),
    Column("source_url", Text),
    Column("source_line_number", Integer),
    Column("source_confidence", Numeric(4, 3), nullable=False, server_default=text("0.9")),
    Column("snapshot_id", UUID(as_uuid=True), ForeignKey("raw_snapshots.id", ondelete="SET NULL")),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    CheckConstraint("home_team_id <> away_team_id", name="different_teams"),
    CheckConstraint("home_score >= 0 and away_score >= 0", name="non_negative_score"),
    UniqueConstraint("source_match_id", name="uq_historical_international_matches_source_match"),
)
Index("idx_historical_international_matches_date", historical_international_matches.c.match_date.desc())
Index("idx_historical_international_matches_home_team", historical_international_matches.c.home_team_id, historical_international_matches.c.match_date.desc())
Index("idx_historical_international_matches_away_team", historical_international_matches.c.away_team_id, historical_international_matches.c.match_date.desc())
Index("idx_historical_international_matches_tournament", historical_international_matches.c.tournament)

team_match_results = Table(
    "team_match_results",
    metadata,
    uuid_pk(),
    Column("team_id", UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
    Column("opponent_team_id", UUID(as_uuid=True), ForeignKey("teams.id", ondelete="SET NULL")),
    Column("played_at", DateTime(timezone=True), nullable=False),
    Column("competition_name", VARCHAR(128), nullable=False),
    Column("source_match_id", VARCHAR(128), nullable=False),
    Column("is_neutral", Boolean, nullable=False, server_default=text("true")),
    Column("goals_for", Integer),
    Column("goals_against", Integer),
    Column("result", VARCHAR(16), nullable=False),
    Column("opponent_rank", Integer),
    Column("opponent_rank_bucket", VARCHAR(16), nullable=False, server_default=text("'unknown'")),
    Column("source_confidence", Numeric(4, 3), nullable=False, server_default=text("0.8")),
    Column("snapshot_id", UUID(as_uuid=True), ForeignKey("raw_snapshots.id", ondelete="SET NULL")),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    CheckConstraint("result in ('win', 'draw', 'loss', 'scheduled')", name="result_valid"),
    CheckConstraint("opponent_rank_bucket in ('top10', 'top30', 'top50', 'other', 'unknown')", name="rank_bucket_valid"),
    UniqueConstraint("team_id", "source_match_id", name="uq_team_match_results_team_match"),
)
Index("idx_team_match_results_team_time", team_match_results.c.team_id, team_match_results.c.played_at.desc())

team_stat_snapshots = Table(
    "team_stat_snapshots",
    metadata,
    uuid_pk(),
    Column("team_id", UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
    Column("metric_type", VARCHAR(64), nullable=False),
    Column("metric_name", VARCHAR(128), nullable=False),
    Column("rank", Integer),
    Column("raw_value", VARCHAR(64)),
    Column("numeric_value", Numeric(18, 4)),
    Column("value_unit", VARCHAR(32)),
    Column("source", VARCHAR(64), nullable=False),
    Column("source_type", VARCHAR(64), nullable=False),
    Column("source_team_id", VARCHAR(128)),
    Column("source_url", Text),
    Column("source_confidence", Numeric(4, 3), nullable=False, server_default=text("0.8")),
    Column("snapshot_id", UUID(as_uuid=True), ForeignKey("raw_snapshots.id", ondelete="SET NULL")),
    Column("as_of_at", DateTime(timezone=True), nullable=False),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    UniqueConstraint("team_id", "metric_type", "as_of_at", "source", name="uq_team_stat_snapshots_team_metric_time_source"),
)
Index("idx_team_stat_snapshots_team_metric", team_stat_snapshots.c.team_id, team_stat_snapshots.c.metric_type)
Index("idx_team_stat_snapshots_metric_rank", team_stat_snapshots.c.metric_type, team_stat_snapshots.c.rank)

coaches = Table(
    "coaches",
    metadata,
    uuid_pk(),
    Column("team_id", UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
    Column("name_zh", VARCHAR(128), nullable=False),
    Column("name_en", VARCHAR(128)),
    Column("started_at", Date),
    Column("matches_count", Integer),
    Column("wins", Integer),
    Column("draws", Integer),
    Column("losses", Integer),
    Column("win_rate", Numeric(5, 2)),
    Column("major_tournament_record", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("source_confidence", Numeric(4, 3), nullable=False, server_default=text("1.0")),
    Column("quality_status", VARCHAR(32), nullable=False, server_default=text("'partial'")),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    UniqueConstraint("team_id", "name_zh", name="uq_coaches_team_name"),
)
Index("idx_coaches_team", coaches.c.team_id)

weather_snapshots = Table(
    "weather_snapshots",
    metadata,
    uuid_pk(),
    Column("venue_id", UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"), nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("provider", VARCHAR(64), nullable=False),
    Column("temperature_c", Numeric(5, 2)),
    Column("humidity_pct", Integer),
    Column("precipitation_mm", Numeric(6, 2)),
    Column("wind_speed_kph", Numeric(6, 2)),
    Column("wind_direction_deg", Integer),
    Column("weather_code", Integer),
    Column("source_url", Text),
    Column("data_quality", VARCHAR(64), nullable=False, server_default=text("'current_observation'")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    UniqueConstraint("venue_id", "provider", "observed_at", name="uq_weather_snapshots_venue_provider_time"),
)
Index("idx_weather_snapshots_venue_time", weather_snapshots.c.venue_id, weather_snapshots.c.observed_at.desc())

injury_reports = Table(
    "injury_reports",
    metadata,
    uuid_pk(),
    Column("team_id", UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
    Column("player_id", UUID(as_uuid=True), ForeignKey("players.id", ondelete="SET NULL")),
    Column("report_type", VARCHAR(32), nullable=False),
    Column("status", VARCHAR(32), nullable=False),
    Column("impact_score", Numeric(5, 2)),
    Column("started_at", Date),
    Column("expected_return_at", Date),
    Column("source_url", Text, nullable=False),
    Column("confidence", Numeric(4, 3), nullable=False),
    Column("evidence_text", Text, nullable=False),
    Column("is_model_eligible", Boolean, nullable=False, server_default=text("false")),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    CheckConstraint("report_type in ('injury', 'suspension', 'fitness')", name="report_type_valid"),
    CheckConstraint("status in ('confirmed', 'doubtful', 'returned', 'suspended')", name="status_valid"),
)
Index("idx_injury_reports_team_status", injury_reports.c.team_id, injury_reports.c.status)

model_versions = Table(
    "model_versions",
    metadata,
    uuid_pk(),
    Column("name", VARCHAR(128), nullable=False),
    Column("version", VARCHAR(64), nullable=False),
    Column("model_type", VARCHAR(64), nullable=False),
    Column("training_data_start", Date),
    Column("training_data_end", Date),
    Column("feature_schema", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("metrics", JSONB),
    Column("is_active", Boolean, nullable=False, server_default=text("false")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    UniqueConstraint("name", "version", name="uq_model_versions_name_version"),
)

model_features = Table(
    "model_features",
    metadata,
    uuid_pk(),
    Column("entity_type", VARCHAR(32), nullable=False),
    Column("entity_key", VARCHAR(128), nullable=False),
    Column("feature_set", VARCHAR(64), nullable=False),
    Column("feature_schema_version", VARCHAR(64), nullable=False),
    Column("as_of_at", DateTime(timezone=True), nullable=False),
    Column("features", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("source_summary", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("missing_features", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("quality_status", VARCHAR(32), nullable=False),
    Column("generated_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    CheckConstraint("entity_type in ('match', 'team', 'player')", name="entity_type_valid"),
    CheckConstraint("quality_status in ('complete', 'partial', 'insufficient')", name="quality_status_valid"),
    UniqueConstraint("entity_type", "entity_key", "feature_set", name="uq_model_features_entity_feature_set"),
)
Index("idx_model_features_entity", model_features.c.entity_type, model_features.c.entity_key)
Index("idx_model_features_feature_set", model_features.c.feature_set)

prediction_snapshots = Table(
    "prediction_snapshots",
    metadata,
    uuid_pk(),
    Column("model_version_id", UUID(as_uuid=True), ForeignKey("model_versions.id"), nullable=False),
    Column("data_snapshot_id", UUID(as_uuid=True), ForeignKey("raw_snapshots.id")),
    Column("generated_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    Column("scope", VARCHAR(64), nullable=False),
    Column("status", VARCHAR(32), nullable=False),
    Column("seed", Integer),
    Column("notes", Text),
    CheckConstraint("status in ('success', 'failed')", name="status_valid"),
)

match_predictions = Table(
    "match_predictions",
    metadata,
    uuid_pk(),
    Column("match_id", UUID(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
    Column("prediction_snapshot_id", UUID(as_uuid=True), ForeignKey("prediction_snapshots.id", ondelete="CASCADE"), nullable=False),
    Column("model_version_id", UUID(as_uuid=True), ForeignKey("model_versions.id"), nullable=False),
    Column("home_win_prob", Numeric(6, 5), nullable=False),
    Column("draw_prob", Numeric(6, 5), nullable=False),
    Column("away_win_prob", Numeric(6, 5), nullable=False),
    Column("home_expected_goals", Numeric(5, 2), nullable=False),
    Column("away_expected_goals", Numeric(5, 2), nullable=False),
    Column("confidence", VARCHAR(32), nullable=False),
    Column("key_factors", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("generated_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    CheckConstraint("home_win_prob >= 0 and home_win_prob <= 1", name="home_win_prob_range"),
    CheckConstraint("draw_prob >= 0 and draw_prob <= 1", name="draw_prob_range"),
    CheckConstraint("away_win_prob >= 0 and away_win_prob <= 1", name="away_win_prob_range"),
    CheckConstraint("abs((home_win_prob + draw_prob + away_win_prob) - 1) < 0.001", name="probability_sum"),
)
Index("idx_match_predictions_match", match_predictions.c.match_id, match_predictions.c.generated_at.desc())

scoreline_predictions = Table(
    "scoreline_predictions",
    metadata,
    uuid_pk(),
    Column("match_prediction_id", UUID(as_uuid=True), ForeignKey("match_predictions.id", ondelete="CASCADE"), nullable=False),
    Column("home_goals", Integer, nullable=False),
    Column("away_goals", Integer, nullable=False),
    Column("probability", Numeric(6, 5), nullable=False),
    Column("rank", Integer, nullable=False),
    UniqueConstraint("match_prediction_id", "home_goals", "away_goals", name="uq_scoreline_predictions_match_score"),
)

group_standings = Table(
    "group_standings",
    metadata,
    uuid_pk(),
    Column("stage_id", UUID(as_uuid=True), ForeignKey("competition_stages.id", ondelete="CASCADE"), nullable=False),
    Column("team_id", UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False),
    Column("played", Integer, nullable=False, server_default=text("0")),
    Column("wins", Integer, nullable=False, server_default=text("0")),
    Column("draws", Integer, nullable=False, server_default=text("0")),
    Column("losses", Integer, nullable=False, server_default=text("0")),
    Column("goals_for", Integer, nullable=False, server_default=text("0")),
    Column("goals_against", Integer, nullable=False, server_default=text("0")),
    Column("goal_diff", Integer, nullable=False, server_default=text("0")),
    Column("points", Integer, nullable=False, server_default=text("0")),
    Column("rank", Integer, nullable=False),
    Column("snapshot_id", UUID(as_uuid=True), ForeignKey("raw_snapshots.id")),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
)

group_simulations = Table(
    "group_simulations",
    metadata,
    uuid_pk(),
    Column("stage_id", UUID(as_uuid=True), ForeignKey("competition_stages.id", ondelete="CASCADE"), nullable=False),
    Column("prediction_snapshot_id", UUID(as_uuid=True), ForeignKey("prediction_snapshots.id", ondelete="CASCADE"), nullable=False),
    Column("team_id", UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False),
    Column("rank_1_prob", Numeric(6, 5), nullable=False),
    Column("rank_2_prob", Numeric(6, 5), nullable=False),
    Column("qualify_prob", Numeric(6, 5), nullable=False),
    Column("expected_points", Numeric(5, 2), nullable=False),
    UniqueConstraint("stage_id", "prediction_snapshot_id", "team_id", name="uq_group_simulations_stage_snapshot_team"),
)

ranking_predictions = Table(
    "ranking_predictions",
    metadata,
    uuid_pk(),
    Column("prediction_snapshot_id", UUID(as_uuid=True), ForeignKey("prediction_snapshots.id", ondelete="CASCADE"), nullable=False),
    Column("ranking_type", VARCHAR(32), nullable=False),
    Column("team_id", UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False),
    Column("probability", Numeric(6, 5), nullable=False),
    Column("delta", Numeric(6, 5)),
    Column("rank", Integer, nullable=False),
    Column("reason", VARCHAR(128)),
    CheckConstraint("ranking_type in ('champion', 'semifinal', 'darkhorse')", name="ranking_type_valid"),
)

news_items = Table(
    "news_items",
    metadata,
    uuid_pk(),
    Column("source", VARCHAR(64), nullable=False),
    Column("source_url", Text, nullable=False, unique=True),
    Column("title", Text, nullable=False),
    Column("summary", Text),
    Column("language", VARCHAR(16), nullable=False, server_default=text("'zh'")),
    Column("published_at", DateTime(timezone=True)),
    Column("fetched_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    Column("related_team_ids", ARRAY(UUID(as_uuid=True))),
    Column("related_player_ids", ARRAY(UUID(as_uuid=True))),
    Column("checksum", VARCHAR(128), nullable=False, unique=True),
)

ai_insights = Table(
    "ai_insights",
    metadata,
    uuid_pk(),
    Column("news_item_id", UUID(as_uuid=True), ForeignKey("news_items.id", ondelete="SET NULL")),
    Column("event_type", VARCHAR(64), nullable=False),
    Column("team_id", UUID(as_uuid=True), ForeignKey("teams.id")),
    Column("player_id", UUID(as_uuid=True), ForeignKey("players.id")),
    Column("match_id", UUID(as_uuid=True), ForeignKey("matches.id")),
    Column("impact_area", VARCHAR(64), nullable=False),
    Column("impact_score", Numeric(5, 2), nullable=False),
    Column("confidence", Numeric(4, 3), nullable=False),
    Column("evidence_text", Text, nullable=False),
    Column("source_url", Text),
    Column("is_model_eligible", Boolean, nullable=False, server_default=text("false")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
)

ai_explanations = Table(
    "ai_explanations",
    metadata,
    uuid_pk(),
    Column("target_type", VARCHAR(32), nullable=False),
    Column("target_id", UUID(as_uuid=True), nullable=False),
    Column("prediction_snapshot_id", UUID(as_uuid=True), ForeignKey("prediction_snapshots.id")),
    Column("title", VARCHAR(128), nullable=False),
    Column("content", Text, nullable=False),
    Column("confidence_label", VARCHAR(32), nullable=False),
    Column("evidence_refs", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("generated_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
)
