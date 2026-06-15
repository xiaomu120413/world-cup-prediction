from datetime import UTC, datetime, timedelta

import pytest

from app.predictions.small_outcome_model import (
    HistoricalMatch,
    build_examples,
    evaluate_baseline,
    evaluate_model,
    train_multinomial_logistic,
)


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


def test_small_outcome_model_trains_and_scores_probabilities():
    matches = [
        make_match(1, "a", "b", 2, 0),
        make_match(2, "c", "d", 1, 1),
        make_match(3, "a", "c", 2, 1),
        make_match(4, "b", "d", 0, 1),
        make_match(5, "a", "d", 3, 1),
        make_match(6, "b", "c", 1, 2),
        make_match(7, "a", "b", 1, 0),
        make_match(8, "c", "d", 2, 2),
        make_match(9, "d", "a", 0, 2),
        make_match(10, "c", "b", 2, 0),
    ]

    examples, states = build_examples(matches, min_prior_matches=2)

    assert len(examples) == 6
    assert states["a"].matches == 5

    model = train_multinomial_logistic(examples, epochs=3, learning_rate=0.02, seed=7)
    probabilities = model.predict_proba(examples[0].features)

    assert sum(probabilities) == pytest.approx(1.0)
    assert all(0.0 < probability < 1.0 for probability in probabilities)

    model_metrics = evaluate_model(model, examples)
    baseline_metrics = evaluate_baseline(examples)

    assert model_metrics["examples"] == len(examples)
    assert baseline_metrics["examples"] == len(examples)
    assert "log_loss" in model_metrics
