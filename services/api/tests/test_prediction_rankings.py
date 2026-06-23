from types import SimpleNamespace

from app.predictions.service import (
    DEFAULT_PREDICTION_MODEL_VERSION,
    DEFAULT_SCORELINE_MODEL_VERSION,
    DEFAULT_SMALL_MODEL_VERSION,
    BaselinePredictionService,
    simulate_group_table,
)


def test_default_prediction_model_uses_calibrated_outcome_model():
    assert DEFAULT_PREDICTION_MODEL_VERSION == DEFAULT_SMALL_MODEL_VERSION
    assert DEFAULT_SCORELINE_MODEL_VERSION.startswith("scoreline")


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


def test_group_simulation_uses_remaining_match_probabilities():
    standings = [
        SimpleNamespace(team_id="france", rank=1, points=6, goal_diff=5, goals_for=6),
        SimpleNamespace(team_id="norway", rank=2, points=6, goal_diff=4, goals_for=7),
        SimpleNamespace(team_id="senegal", rank=3, points=0, goal_diff=-3, goals_for=3),
        SimpleNamespace(team_id="iraq", rank=4, points=0, goal_diff=-6, goals_for=1),
    ]
    remaining_matches = [
        {
            "home_team_id": "norway",
            "away_team_id": "france",
            "home_win_prob": 0.13807,
            "draw_prob": 0.24368,
            "away_win_prob": 0.61825,
            "home_expected_goals": 0.74,
            "away_expected_goals": 1.75,
        },
        {
            "home_team_id": "senegal",
            "away_team_id": "iraq",
            "home_win_prob": 0.67494,
            "draw_prob": 0.21062,
            "away_win_prob": 0.11444,
            "home_expected_goals": 1.89,
            "away_expected_goals": 0.61,
        },
    ]

    simulation = simulate_group_table(standings, remaining_matches)

    assert simulation["france"]["rank_1_prob"] == 0.86193
    assert simulation["france"]["rank_2_prob"] == 0.13807
    assert simulation["france"]["qualify_prob"] == 1.0
    assert simulation["norway"]["rank_1_prob"] == 0.13807
    assert simulation["norway"]["qualify_prob"] == 1.0
    assert simulation["senegal"]["qualify_prob"] == 0.0
    assert simulation["iraq"]["qualify_prob"] == 0.0
