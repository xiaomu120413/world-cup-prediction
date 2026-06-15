from app.db.schema import metadata


def test_metadata_contains_core_tables():
    expected = {
        "competitions",
        "competition_stages",
        "teams",
        "players",
        "venues",
        "matches",
        "raw_snapshots",
        "collector_runs",
        "team_form_snapshots",
        "player_form_snapshots",
        "model_versions",
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


def test_match_public_id_is_unique():
    table = metadata.tables["matches"]
    assert table.c.public_id.unique is True
