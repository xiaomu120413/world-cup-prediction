from app.predictions.baseline import MatchInputs, TeamInputs, build_match_prediction, expected_goals


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
