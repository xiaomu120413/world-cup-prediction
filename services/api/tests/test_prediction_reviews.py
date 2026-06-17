import pytest

from scripts.review_predictions import actual_outcome, calibration_summary, prediction_metrics


def test_prediction_review_metrics_use_actual_outcome_probability():
    metrics = prediction_metrics(0.62, 0.23, 0.15, "home_win")

    assert metrics["actual_outcome_prob"] == 0.62
    assert metrics["predicted_outcome"] == "home_win"
    assert metrics["predicted_outcome_correct"] is True
    assert metrics["log_loss"] == pytest.approx(0.478036)
    assert metrics["brier_score"] == pytest.approx((0.62 - 1) ** 2 + 0.23**2 + 0.15**2)
    assert metrics["calibration_bucket"] == 6


def test_prediction_review_metrics_marks_wrong_favorite():
    metrics = prediction_metrics(0.52, 0.25, 0.23, "away_win")

    assert metrics["actual_outcome_prob"] == 0.23
    assert metrics["predicted_outcome"] == "home_win"
    assert metrics["predicted_outcome_correct"] is False
    assert metrics["calibration_bucket"] == 5


def test_actual_outcome_from_score():
    assert actual_outcome(2, 1) == "home_win"
    assert actual_outcome(1, 1) == "draw"
    assert actual_outcome(0, 2) == "away_win"


def test_calibration_summary_computes_ece_by_bucket():
    summary = calibration_summary(
        [
            {"calibration_bucket": 6, "predicted_outcome_prob": 0.62, "predicted_outcome_correct": True},
            {"calibration_bucket": 6, "predicted_outcome_prob": 0.68, "predicted_outcome_correct": False},
            {"calibration_bucket": 8, "predicted_outcome_prob": 0.82, "predicted_outcome_correct": True},
        ]
    )

    assert summary["ece"] == pytest.approx((2 / 3) * abs(0.65 - 0.5) + (1 / 3) * abs(0.82 - 1.0))
    assert [bucket["bucket"] for bucket in summary["buckets"]] == [6, 8]
