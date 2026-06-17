from types import SimpleNamespace

from app.predictions.service import (
    DEFAULT_PREDICTION_MODEL_VERSION,
    DEFAULT_SCORELINE_MODEL_VERSION,
    BaselinePredictionService,
)


def test_default_prediction_model_keeps_scoreline_distribution_enabled():
    assert DEFAULT_PREDICTION_MODEL_VERSION == DEFAULT_SCORELINE_MODEL_VERSION


def test_tournament_ranking_score_rewards_live_group_form():
    base = SimpleNamespace(
        team_id="france",
        code="FRA",
        fifa_rank=3,
        elo_rating=2104,
        market_value_eur=1_523_000_000,
        group_rank=2,
        group_points=3,
        group_played=1,
        group_goal_diff=2,
        group_goals_for=3,
    )
    stale = SimpleNamespace(
        **{
            **base.__dict__,
            "group_points": 0,
            "group_played": 0,
            "group_goal_diff": 0,
            "group_goals_for": 0,
        }
    )

    updated_score = BaselinePredictionService.tournament_team_score(base)["score"]
    stale_score = BaselinePredictionService.tournament_team_score(stale)["score"]

    assert updated_score > stale_score
