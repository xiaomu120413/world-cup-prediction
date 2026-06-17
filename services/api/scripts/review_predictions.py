from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.schema import matches, match_predictions, prediction_reviews, scoreline_predictions
from app.db.session import SessionLocal

OUTCOMES = ("home_win", "draw", "away_win")


def actual_outcome(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "home_win"
    if home_goals < away_goals:
        return "away_win"
    return "draw"


def prediction_metrics(
    home_win_prob: float,
    draw_prob: float,
    away_win_prob: float,
    outcome: str,
) -> dict[str, Any]:
    probabilities = {
        "home_win": float(home_win_prob),
        "draw": float(draw_prob),
        "away_win": float(away_win_prob),
    }
    actual_prob = max(probabilities[outcome], 1e-15)
    predicted_outcome = max(OUTCOMES, key=lambda key: probabilities[key])
    predicted_prob = probabilities[predicted_outcome]
    brier = sum((probabilities[key] - (1.0 if key == outcome else 0.0)) ** 2 for key in OUTCOMES)
    return {
        "actual_outcome_prob": round(actual_prob, 6),
        "predicted_outcome": predicted_outcome,
        "predicted_outcome_prob": round(predicted_prob, 6),
        "predicted_outcome_correct": predicted_outcome == outcome,
        "log_loss": round(-math.log(actual_prob), 6),
        "brier_score": round(brier, 6),
        "calibration_bucket": min(9, max(0, int(predicted_prob * 10))),
    }


def calibration_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"ece": None, "buckets": []}
    total = len(rows)
    buckets = []
    ece = 0.0
    for bucket in range(10):
        bucket_rows = [row for row in rows if int(row["calibration_bucket"]) == bucket]
        if not bucket_rows:
            continue
        avg_confidence = sum(float(row["predicted_outcome_prob"]) for row in bucket_rows) / len(bucket_rows)
        accuracy = sum(1 for row in bucket_rows if row["predicted_outcome_correct"]) / len(bucket_rows)
        gap = abs(avg_confidence - accuracy)
        ece += (len(bucket_rows) / total) * gap
        buckets.append(
            {
                "bucket": bucket,
                "range": [round(bucket / 10, 1), round((bucket + 1) / 10, 1)],
                "count": len(bucket_rows),
                "avg_confidence": round(avg_confidence, 6),
                "accuracy": round(accuracy, 6),
                "gap": round(gap, 6),
            }
        )
    return {"ece": round(ece, 6), "buckets": buckets}


def scoreline_lookup(db, prediction_ids: list[Any]) -> dict[Any, dict[str, Any]]:
    if not prediction_ids:
        return {}
    rows = db.execute(
        select(
            scoreline_predictions.c.match_prediction_id,
            scoreline_predictions.c.home_goals,
            scoreline_predictions.c.away_goals,
            scoreline_predictions.c.probability,
            scoreline_predictions.c.rank,
        ).where(scoreline_predictions.c.match_prediction_id.in_(prediction_ids))
    ).mappings().all()
    grouped: dict[Any, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row.match_prediction_id, []).append(dict(row))
    return {key: sorted(values, key=lambda item: item["rank"]) for key, values in grouped.items()}


def metadata_scoreline(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if not item:
        return None
    return {
        "home_goals": item["home_goals"],
        "away_goals": item["away_goals"],
        "probability": round(float(item["probability"]), 6),
        "rank": item["rank"],
    }


def review_predictions(db, force: bool = False, include_post_kickoff: bool = False) -> dict[str, Any]:
    query = (
        select(
            match_predictions.c.id.label("match_prediction_id"),
            match_predictions.c.match_id,
            match_predictions.c.prediction_snapshot_id,
            match_predictions.c.model_version_id,
            match_predictions.c.home_win_prob,
            match_predictions.c.draw_prob,
            match_predictions.c.away_win_prob,
            match_predictions.c.generated_at,
            match_predictions.c.inference_mode,
            match_predictions.c.calibration_applied,
            matches.c.public_id,
            matches.c.kickoff_at,
            matches.c.home_score,
            matches.c.away_score,
        )
        .join(matches, matches.c.id == match_predictions.c.match_id)
        .outerjoin(prediction_reviews, prediction_reviews.c.match_prediction_id == match_predictions.c.id)
        .where(
            matches.c.status == "finished",
            matches.c.home_score.is_not(None),
            matches.c.away_score.is_not(None),
        )
        .order_by(match_predictions.c.generated_at.asc())
    )
    if not include_post_kickoff:
        query = query.where(match_predictions.c.generated_at < matches.c.kickoff_at)
    if not force:
        query = query.where(prediction_reviews.c.id.is_(None))

    candidates = [dict(row) for row in db.execute(query).mappings().all()]
    scorelines_by_prediction = scoreline_lookup(db, [row["match_prediction_id"] for row in candidates])
    rows = []
    for row in candidates:
        outcome = actual_outcome(row["home_score"], row["away_score"])
        metrics = prediction_metrics(
            float(row["home_win_prob"]),
            float(row["draw_prob"]),
            float(row["away_win_prob"]),
            outcome,
        )
        scorelines = scorelines_by_prediction.get(row["match_prediction_id"], [])
        actual_scoreline = next(
            (
                item
                for item in scorelines
                if item["home_goals"] == row["home_score"] and item["away_goals"] == row["away_score"]
            ),
            None,
        )
        top_scoreline = scorelines[0] if scorelines else None
        rows.append(
            {
                "match_prediction_id": row["match_prediction_id"],
                "match_id": row["match_id"],
                "prediction_snapshot_id": row["prediction_snapshot_id"],
                "model_version_id": row["model_version_id"],
                "actual_outcome": outcome,
                "actual_home_goals": row["home_score"],
                "actual_away_goals": row["away_score"],
                "home_win_prob": row["home_win_prob"],
                "draw_prob": row["draw_prob"],
                "away_win_prob": row["away_win_prob"],
                **metrics,
                "actual_scoreline_prob": float(actual_scoreline["probability"]) if actual_scoreline else None,
                "top_scoreline_hit": (
                    bool(
                        top_scoreline
                        and top_scoreline["home_goals"] == row["home_score"]
                        and top_scoreline["away_goals"] == row["away_score"]
                    )
                    if top_scoreline
                    else None
                ),
                "review_metadata": {
                    "match_public_id": row["public_id"],
                    "prediction_generated_at": row["generated_at"].isoformat(),
                    "kickoff_at": row["kickoff_at"].isoformat(),
                    "inference_mode": row["inference_mode"],
                    "calibration_applied": row["calibration_applied"],
                    "top_scoreline": metadata_scoreline(top_scoreline),
                },
            }
        )

    if rows:
        statement = pg_insert(prediction_reviews).values(rows)
        db.execute(
            statement.on_conflict_do_update(
                constraint="uq_prediction_reviews_match_prediction",
                set_={
                    "actual_outcome": statement.excluded.actual_outcome,
                    "actual_home_goals": statement.excluded.actual_home_goals,
                    "actual_away_goals": statement.excluded.actual_away_goals,
                    "home_win_prob": statement.excluded.home_win_prob,
                    "draw_prob": statement.excluded.draw_prob,
                    "away_win_prob": statement.excluded.away_win_prob,
                    "actual_outcome_prob": statement.excluded.actual_outcome_prob,
                    "predicted_outcome": statement.excluded.predicted_outcome,
                    "predicted_outcome_prob": statement.excluded.predicted_outcome_prob,
                    "predicted_outcome_correct": statement.excluded.predicted_outcome_correct,
                    "log_loss": statement.excluded.log_loss,
                    "brier_score": statement.excluded.brier_score,
                    "calibration_bucket": statement.excluded.calibration_bucket,
                    "actual_scoreline_prob": statement.excluded.actual_scoreline_prob,
                    "top_scoreline_hit": statement.excluded.top_scoreline_hit,
                    "review_metadata": statement.excluded.review_metadata,
                    "reviewed_at": func.now(),
                },
            )
        )
        db.commit()

    summary_rows = [
        dict(row)
        for row in db.execute(
            select(
                prediction_reviews.c.log_loss,
                prediction_reviews.c.brier_score,
                prediction_reviews.c.predicted_outcome_prob,
                prediction_reviews.c.predicted_outcome_correct,
                prediction_reviews.c.calibration_bucket,
            )
        ).mappings().all()
    ]
    count = len(summary_rows)
    return {
        "status": "completed",
        "reviews_written": len(rows),
        "reviews_total": count,
        "log_loss": round(sum(float(row["log_loss"]) for row in summary_rows) / count, 6) if count else None,
        "brier_score": round(sum(float(row["brier_score"]) for row in summary_rows) / count, 6) if count else None,
        "calibration": calibration_summary(summary_rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Review finished-match predictions against actual results.")
    parser.add_argument("--force", action="store_true", help="Recompute existing reviews.")
    parser.add_argument(
        "--include-post-kickoff",
        action="store_true",
        help="Also review predictions generated after kickoff. Default excludes them to avoid leakage.",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        result = review_predictions(db, force=args.force, include_post_kickoff=args.include_post_kickoff)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
