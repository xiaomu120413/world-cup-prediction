from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime, time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.predictions.scoreline_model import (
    SCORELINE_FEATURE_NAMES,
    build_scoreline_examples,
    evaluate_scoreline_model,
    split_examples_by_date,
    train_poisson_goal_model,
)
from scripts.train_small_outcome_model import load_historical_matches

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "exports" / "scoreline_model_latest.json"


def parse_date(value: str) -> datetime:
    parsed = date.fromisoformat(value)
    return datetime.combine(parsed, time.min, tzinfo=UTC)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the scoreline Poisson goal model.")
    parser.add_argument("--train-end", default="2024-01-01")
    parser.add_argument("--test-start", default="2024-01-01")
    parser.add_argument("--min-prior-matches", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=45)
    parser.add_argument("--learning-rate", type=float, default=0.008)
    parser.add_argument("--l2", type=float, default=0.0005)
    parser.add_argument("--seed", type=int, default=20260617)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    with SessionLocal() as db:
        historical_matches = load_historical_matches(db)

    goal_examples, scoreline_examples, _states = build_scoreline_examples(
        historical_matches,
        min_prior_matches=args.min_prior_matches,
    )
    train_goals, test_goals = split_examples_by_date(
        goal_examples,
        train_end=parse_date(args.train_end),
        test_start=parse_date(args.test_start),
    )
    _train_scorelines, test_scorelines = split_examples_by_date(
        scoreline_examples,
        train_end=parse_date(args.train_end),
        test_start=parse_date(args.test_start),
    )
    if not train_goals:
        raise RuntimeError("No scoreline training examples after applying train split.")
    if not test_goals:
        raise RuntimeError("No scoreline test examples after applying test split.")

    model = train_poisson_goal_model(
        train_goals,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        l2=args.l2,
        seed=args.seed,
        feature_names=SCORELINE_FEATURE_NAMES,
    )
    report = {
        "model": model.to_dict(),
        "dataset": {
            "historical_matches": len(historical_matches),
            "goal_examples_total": len(goal_examples),
            "scoreline_examples_total": len(scoreline_examples),
            "train_goal_examples": len(train_goals),
            "test_goal_examples": len(test_goals),
            "test_scoreline_examples": len(test_scorelines),
        },
        "metrics": evaluate_scoreline_model(model, test_scorelines),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), **report["dataset"], "metrics": report["metrics"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
