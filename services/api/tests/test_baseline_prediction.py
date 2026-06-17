import pytest

from app.predictions.baseline import (
    MatchInputs,
    TeamInputs,
    build_match_prediction,
    calibrated_scoreline_distribution,
    expected_goals,
    outcome_key,
)


def test_expected_goals_favor_stronger_team():
    home_xg, away_xg = expected_goals(
        MatchInputs(
            home=TeamInputs("FRA", fifa_rank=2, elo_rating=2104),
            away=TeamInputs("PAR", fifa_rank=48, elo_rating=1741),
        )
    )

    assert home_xg > away_xg
    assert 0.25 <= away_xg <= 3.8


def test_match_prediction_probability_sum():
    prediction = build_match_prediction(
        MatchInputs(
            home=TeamInputs("USA", fifa_rank=11, elo_rating=1838),
            away=TeamInputs("PAR", fifa_rank=48, elo_rating=1741),
        )
    )
    probabilities = prediction["probabilities"]

    assert abs(sum(probabilities.values()) - 1) < 0.001
    assert len(prediction["scorelines"]) == 4
    assert prediction["scorelines"][0]["rank"] == 1


def test_calibrated_scorelines_match_model_outcome_probabilities():
    model_probabilities = {"home_win": 0.72, "draw": 0.18, "away_win": 0.10}

    scorelines = calibrated_scoreline_distribution(1.8, 0.7, model_probabilities)

    totals = {"home_win": 0.0, "draw": 0.0, "away_win": 0.0}
    for item in scorelines:
        totals[outcome_key(item["home_goals"], item["away_goals"])] += item["probability"]

    assert totals["home_win"] == pytest.approx(0.72)
    assert totals["draw"] == pytest.approx(0.18)
    assert totals["away_win"] == pytest.approx(0.10)
    assert scorelines == sorted(scorelines, key=lambda item: item["probability"], reverse=True)
