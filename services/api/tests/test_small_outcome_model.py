from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.predictions.service import DEFAULT_PREDICTION_MODEL_VERSION, DEFAULT_SCORELINE_MODEL_VERSION, DEFAULT_SMALL_MODEL_VERSION
from app.predictions.small_outcome_model import (
    HistoricalMatch,
    FEATURE_NAMES,
    build_examples,
    evaluate_baseline,
    evaluate_model,
    train_multinomial_logistic,
)
from scripts.train_small_outcome_model import (
    CurrentContextFeatureStore,
    calibration_gate_result,
    examples_with_context_filter,
    predict_scheduled_matches,
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


def test_small_outcome_model_accepts_context_feature_names():
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
    examples, _states = build_examples(matches, min_prior_matches=2)
    enriched = [
        type(example)(
            **{
                **example.__dict__,
                "features": {
                    **example.features,
                    "ctx_roster_market_value_log": 1.0 if example.home_team_code in {"A", "C"} else -1.0,
                },
            }
        )
        for example in examples
    ]

    feature_names = (*FEATURE_NAMES, "ctx_roster_market_value_log")
    model = train_multinomial_logistic(enriched, epochs=2, feature_names=feature_names)

    assert model.feature_names == feature_names
    assert "ctx_roster_market_value_log" in model.to_dict()["feature_names"]


def test_small_outcome_model_round_trips_from_model_version_payload():
    matches = [
        make_match(1, "a", "b", 2, 0),
        make_match(2, "a", "b", 1, 1),
        make_match(3, "a", "b", 0, 1),
        make_match(4, "a", "b", 3, 1),
    ]
    examples, _states = build_examples(matches, min_prior_matches=1)
    model = train_multinomial_logistic(examples, epochs=2, learning_rate=0.01)
    restored = type(model).from_dict(model.to_dict())

    assert restored.feature_names == model.feature_names
    assert restored.predict_proba(examples[0].features) == pytest.approx(model.predict_proba(examples[0].features))


def test_prediction_uses_history_fallback_when_context_team_is_missing():
    class FixedModel:
        feature_names = ("elo_diff",)

        def __init__(self, probabilities):
            self.probabilities = probabilities

        def predict_proba(self, _features):
            return self.probabilities

    row = SimpleNamespace(
        public_id="match-1",
        home_team_id="team-a",
        away_team_id="team-b",
        kickoff_at=datetime(2026, 6, 16, tzinfo=UTC),
        neutral_site=True,
        home_team_name="A",
        away_team_name="B",
        home_team_code="A",
        away_team_code="B",
        match_feature_quality_status=None,
        match_feature_missing_features=[],
        match_feature_source_summary={},
    )
    states = {"team-a": make_state(), "team-b": make_state()}
    context_store = CurrentContextFeatureStore(
        feature_names=("ctx_roster_market_value_log",),
        team_vectors={"team-a": {"ctx_roster_market_value_log": 1.0}},
        roster_team_ids={"team-a"},
    )

    predictions = predict_scheduled_matches(
        FixedModel([0.1, 0.1, 0.8]),
        states,
        [row],
        context_store=context_store,
        core_model=FixedModel([0.5, 0.3, 0.2]),
    )

    assert predictions[0]["inference_mode"] == "history_core_fallback"
    assert predictions[0]["calibration_applied"] is False
    assert predictions[0]["fallback_reason"] == "missing_context_features"
    assert predictions[0]["probabilities"] == {"home_win": 0.5, "draw": 0.3, "away_win": 0.2}


def test_prediction_uses_history_fallback_when_context_features_are_incomplete():
    class FixedModel:
        feature_names = ("ctx_team_market_value_log",)

        def __init__(self, probabilities):
            self.probabilities = probabilities

        def predict_proba(self, _features):
            return self.probabilities

    class FixedCoreModel(FixedModel):
        feature_names = ("elo_diff",)

    row = SimpleNamespace(
        public_id="match-1",
        home_team_id="team-a",
        away_team_id="team-b",
        kickoff_at=datetime(2026, 6, 16, tzinfo=UTC),
        neutral_site=True,
        home_team_name="A",
        away_team_name="B",
        home_team_code="A",
        away_team_code="B",
        match_feature_quality_status="partial",
        match_feature_missing_features=["away_team_market_value"],
        match_feature_source_summary={},
    )
    states = {"team-a": make_state(), "team-b": make_state()}
    context_store = CurrentContextFeatureStore(
        feature_names=("ctx_team_market_value_log",),
        team_vectors={
            "team-a": {"ctx_team_market_value_log": 20.0},
            "team-b": {"ctx_team_market_value_log": 0.0},
        },
        roster_team_ids={"team-a", "team-b"},
        team_missing_features={"team-b": {"ctx_team_market_value_log"}},
    )

    predictions = predict_scheduled_matches(
        FixedModel([0.1, 0.1, 0.8]),
        states,
        [row],
        context_store=context_store,
        core_model=FixedCoreModel([0.5, 0.3, 0.2]),
    )

    assert predictions[0]["inference_mode"] == "history_core_fallback"
    assert predictions[0]["calibration_applied"] is False
    assert predictions[0]["fallback_reason"] == "missing_context_features"
    assert predictions[0]["probabilities"] == {"home_win": 0.5, "draw": 0.3, "away_win": 0.2}


def test_context_training_filter_keeps_mapped_teams_with_incomplete_features():
    example = SimpleNamespace(home_team_id="team-a", away_team_id="team-b")
    context_store = CurrentContextFeatureStore(
        feature_names=("ctx_team_market_value_log",),
        team_vectors={
            "team-a": {"ctx_team_market_value_log": 20.0},
            "team-b": {"ctx_team_market_value_log": 0.0},
        },
        roster_team_ids={"team-a", "team-b"},
        team_missing_features={"team-b": {"ctx_team_market_value_log"}},
    )

    filtered = examples_with_context_filter([example], context_store, roster_context_only=True)

    assert filtered == [example]
    assert context_store.has_mapped_team("team-b") is True
    assert context_store.has_team("team-b") is False


def test_calibration_gate_rejects_model_worse_than_elo_baseline():
    gate = calibration_gate_result(
        {
            "calibrated_model": {"log_loss": 1.09, "brier": 0.66},
            "elo_baseline_on_same_subset": {"log_loss": 1.06, "brier": 0.64},
        }
    )

    assert gate["accepted"] is False
    assert gate["reason"] == "calibrated_model_worse_than_elo_baseline"
    assert gate["log_loss_delta"] == pytest.approx(0.03)


def test_calibration_gate_accepts_model_no_worse_than_elo_baseline():
    gate = calibration_gate_result(
        {
            "calibrated_model": {"log_loss": 1.05, "brier": 0.63},
            "elo_baseline_on_same_subset": {"log_loss": 1.06, "brier": 0.64},
        }
    )

    assert gate["accepted"] is True
    assert gate["reason"] is None


def test_small_outcome_pipeline_is_default_and_scoreline_remains_available():
    assert DEFAULT_PREDICTION_MODEL_VERSION == DEFAULT_SMALL_MODEL_VERSION
    assert DEFAULT_SMALL_MODEL_VERSION.startswith("small_outcome")
    assert DEFAULT_SCORELINE_MODEL_VERSION.startswith("scoreline")


def make_state():
    matches = [
        make_match(1, "a", "b", 2, 0),
        make_match(2, "a", "b", 1, 1),
        make_match(3, "a", "b", 0, 1),
    ]
    examples, states = build_examples(matches, min_prior_matches=1)
    return next(iter(states.values()))
