from app.db.schema import metadata


def test_metadata_contains_core_tables():
    expected = {
        "competitions",
        "competition_stages",
        "teams",
        "players",
        "player_aliases",
        "venues",
        "matches",
        "raw_snapshots",
        "data_source_links",
        "collector_runs",
        "team_form_snapshots",
        "player_form_snapshots",
        "lineup_snapshots",
        "historical_international_matches",
        "team_match_results",
        "team_stat_snapshots",
        "coaches",
        "weather_snapshots",
        "injury_reports",
        "model_versions",
        "model_features",
        "prediction_snapshots",
        "match_predictions",
        "scoreline_predictions",
        "group_standings",
        "group_simulations",
        "ranking_predictions",
        "news_items",
        "ai_insights",
        "ai_explanations",
    }
    assert expected.issubset(metadata.tables.keys())


def test_prediction_probability_constraint_is_declared():
    table = metadata.tables["match_predictions"]
    constraints = {constraint.name for constraint in table.constraints}
    assert "ck_match_predictions_probability_sum" in constraints


def test_model_features_declares_idempotent_feature_key():
    table = metadata.tables["model_features"]
    constraints = {constraint.name for constraint in table.constraints}

    assert "uq_model_features_entity_feature_set_as_of" in constraints
    assert "ck_model_features_quality_status_valid" in constraints
    assert {"entity_type", "entity_key", "feature_set", "as_of_at"}.issubset(table.c.keys())


def test_player_aliases_declares_source_identity_key():
    table = metadata.tables["player_aliases"]
    constraints = {constraint.name for constraint in table.constraints}

    assert "uq_player_aliases_source_player_id" in constraints
    assert {"player_id", "team_id", "source", "source_player_id", "alias"}.issubset(table.c.keys())


def test_match_public_id_is_unique():
    table = metadata.tables["matches"]
    assert table.c.public_id.unique is True
