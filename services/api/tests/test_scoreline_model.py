from datetime import UTC, datetime, timedelta

import pytest

from app.predictions.service import calibrate_scorelines_to_outcome_probabilities
from app.predictions.scoreline_model import (
    build_scoreline_examples,
    context_adjusted_expected_goals,
    evaluate_scoreline_model,
    outcome_probabilities_from_scorelines,
    scoreline_distribution,
    train_poisson_goal_model,
)
from app.predictions.small_outcome_model import HistoricalMatch


def make_match(index: int, home: str, away: str, home_score: int, away_score: int) -> HistoricalMatch:
    played_at = datetime(2020, 1, 1, tzinfo=UTC) + timedelta(days=index * 7)
    return HistoricalMatch(
        match_id=f"m-{index}",
        played_at=played_at,
        home_team_id=home,
        away_team_id=away,
        home_team_code=home.upper(),
        away_team_code=away.upper(),
        home_score=home_score,
        away_score=away_score,
        tournament="Friendly",
        neutral=True,
    )


def test_scoreline_model_trains_and_outputs_probability_matrix():
    matches = [
        make_match(1, "a", "b", 3, 0),
        make_match(2, "a", "c", 2, 0),
        make_match(3, "a", "d", 2, 1),
        make_match(4, "b", "c", 1, 1),
        make_match(5, "c", "d", 1, 0),
        make_match(6, "b", "d", 0, 1),
        make_match(7, "a", "b", 2, 0),
        make_match(8, "a", "c", 3, 1),
        make_match(9, "d", "a", 0, 2),
        make_match(10, "c", "b", 2, 2),
        make_match(11, "a", "d", 1, 0),
        make_match(12, "b", "a", 0, 3),
    ]

    goal_examples, scoreline_examples, _states = build_scoreline_examples(matches, min_prior_matches=2)
    model = train_poisson_goal_model(goal_examples, epochs=3, learning_rate=0.005, seed=17)
    metrics = evaluate_scoreline_model(model, scoreline_examples)
    scorelines = scoreline_distribution(1.6, 0.8, low_score_correlation=model.low_score_correlation)
    probabilities = outcome_probabilities_from_scorelines(scorelines)

    assert len(goal_examples) > 0
    assert metrics["examples"] == len(scoreline_examples)
    assert sum(item["probability"] for item in scorelines) == pytest.approx(1.0)
    assert sum(probabilities.values()) == pytest.approx(1.0)
    assert scorelines == sorted(scorelines, key=lambda item: item["probability"], reverse=True)
    assert model.predict_goals(goal_examples[0].features) > 0


def test_scoreline_matrix_calibrates_to_outcome_model_probabilities():
    scorelines = scoreline_distribution(1.4, 0.9)
    calibrated = calibrate_scorelines_to_outcome_probabilities(
        scorelines,
        {"home_win": 0.62, "draw": 0.24, "away_win": 0.14},
    )
    probabilities = outcome_probabilities_from_scorelines(calibrated)

    assert probabilities["home_win"] == pytest.approx(0.62, abs=1e-5)
    assert probabilities["draw"] == pytest.approx(0.24, abs=1e-5)
    assert probabilities["away_win"] == pytest.approx(0.14, abs=1e-5)
    assert sum(item["probability"] for item in calibrated) == pytest.approx(1.0)
    assert calibrated == sorted(calibrated, key=lambda item: item["probability"], reverse=True)


def test_context_adjustments_apply_real_feature_direction_with_bounds():
    home_xg, away_xg, adjustments = context_adjusted_expected_goals(
        1.2,
        1.2,
        {
            "market_value_log_diff": 2.0,
            "player_goals_per_player_diff": 0.8,
            "player_assists_per_player_diff": 0.4,
            "home_availability_impact": -0.5,
            "away_availability_impact": -1.0,
            "home_player_unavailable_count": 1,
            "away_player_unavailable_count": 3,
            "weather_wind_speed_kph": 24,
            "weather_precipitation_mm": 2.0,
            "weather_temperature_c": 33,
        },
    )

    assert 0.05 <= home_xg <= 5.5
    assert 0.05 <= away_xg <= 5.5
    assert home_xg > away_xg
    assert {item["label"] for item in adjustments} >= {
        "context_market_value",
        "context_roster_output",
        "context_weather_total",
    }
