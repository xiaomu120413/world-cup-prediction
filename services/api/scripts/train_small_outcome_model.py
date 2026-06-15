from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

from sqlalchemy import and_, asc, or_, select

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.schema import historical_international_matches, matches, teams
from app.db.session import SessionLocal
from app.predictions.small_outcome_model import (
    FEATURE_NAMES,
    LABELS,
    HistoricalMatch,
    TeamState,
    build_examples,
    evaluate_baseline,
    evaluate_model,
    evaluate_prior,
    feature_dict,
    train_multinomial_logistic,
)

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "exports" / "small_outcome_model_latest.json"


def parse_date(value: str) -> datetime:
    parsed = date.fromisoformat(value)
    return datetime.combine(parsed, time.min, tzinfo=UTC)


def load_historical_matches(db) -> list[HistoricalMatch]:
    home_team = teams.alias("home_team")
    away_team = teams.alias("away_team")
    statement = (
        select(
            historical_international_matches.c.source_match_id,
            historical_international_matches.c.played_at,
            historical_international_matches.c.home_team_id,
            historical_international_matches.c.away_team_id,
            home_team.c.code.label("home_team_code"),
            away_team.c.code.label("away_team_code"),
            historical_international_matches.c.home_score,
            historical_international_matches.c.away_score,
            historical_international_matches.c.tournament,
            historical_international_matches.c.neutral,
        )
        .select_from(
            historical_international_matches.join(
                home_team, historical_international_matches.c.home_team_id == home_team.c.id
            ).join(away_team, historical_international_matches.c.away_team_id == away_team.c.id)
        )
        .order_by(asc(historical_international_matches.c.played_at), asc(historical_international_matches.c.source_match_id))
    )
    rows = db.execute(statement).mappings().all()
    return [
        HistoricalMatch(
            match_id=row.source_match_id,
            played_at=row.played_at,
            home_team_id=str(row.home_team_id),
            away_team_id=str(row.away_team_id),
            home_team_code=row.home_team_code,
            away_team_code=row.away_team_code,
            home_score=int(row.home_score),
            away_score=int(row.away_score),
            tournament=row.tournament or "",
            neutral=bool(row.neutral),
        )
        for row in rows
    ]


def split_examples(examples, train_end: datetime, test_start: datetime):
    train = [example for example in examples if example.played_at < train_end]
    test = [example for example in examples if example.played_at >= test_start]
    return train, test


def label_distribution(examples) -> dict[str, int]:
    counts = Counter(example.label for example in examples)
    return {label: counts[index] for index, label in enumerate(LABELS)}


def top_coefficients(model, limit: int = 8) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {}
    for label_index, label in enumerate(LABELS):
        coefficients = []
        for feature_name, weight in zip(FEATURE_NAMES, model.weights[label_index][1:]):
            coefficients.append({"feature": feature_name, "weight": round(weight, 6)})
        rows[label] = sorted(coefficients, key=lambda item: abs(item["weight"]), reverse=True)[:limit]
    return rows


def load_scheduled_matches(db, limit: int):
    home_team = teams.alias("home_team")
    away_team = teams.alias("away_team")
    statement = (
        select(
            matches.c.public_id,
            matches.c.home_team_id,
            matches.c.away_team_id,
            matches.c.kickoff_at,
            matches.c.neutral_site,
            home_team.c.code.label("home_team_code"),
            home_team.c.name_zh.label("home_team_name"),
            away_team.c.code.label("away_team_code"),
            away_team.c.name_zh.label("away_team_name"),
        )
        .select_from(matches.join(home_team, matches.c.home_team_id == home_team.c.id).join(away_team, matches.c.away_team_id == away_team.c.id))
        .where(
            and_(
                matches.c.status == "scheduled",
                or_(home_team.c.quality_status != "estimated", away_team.c.quality_status != "estimated"),
            )
        )
        .order_by(asc(matches.c.kickoff_at), asc(matches.c.public_id))
        .limit(limit)
    )
    return db.execute(statement).mappings().all()


def predict_scheduled_matches(model, states: dict[str, TeamState], scheduled_rows) -> list[dict[str, Any]]:
    predictions: list[dict[str, Any]] = []
    for row in scheduled_rows:
        home_state = states.get(str(row.home_team_id))
        away_state = states.get(str(row.away_team_id))
        if home_state is None or away_state is None:
            predictions.append(
                {
                    "match_id": row.public_id,
                    "home_team": row.home_team_name,
                    "away_team": row.away_team_name,
                    "skipped": "missing_historical_state",
                }
            )
            continue
        features = feature_dict(
            home_state,
            away_state,
            row.kickoff_at,
            bool(row.neutral_site),
            "FIFA World Cup",
        )
        probabilities = model.predict_proba(features)
        predictions.append(
            {
                "match_id": row.public_id,
                "kickoff_at": row.kickoff_at.isoformat(),
                "home_team": row.home_team_name,
                "away_team": row.away_team_name,
                "home_team_code": row.home_team_code,
                "away_team_code": row.away_team_code,
                "probabilities": {
                    label: round(probabilities[index], 6)
                    for index, label in enumerate(LABELS)
                },
                "feature_snapshot": {name: round(features[name], 6) for name in FEATURE_NAMES},
            }
        )
    return predictions


def build_report(args) -> dict[str, Any]:
    with SessionLocal() as db:
        historical_matches = load_historical_matches(db)
        examples, final_states = build_examples(historical_matches, min_prior_matches=args.min_prior_matches)
        train_end = parse_date(args.train_end)
        test_start = parse_date(args.test_start)
        train_examples, test_examples = split_examples(examples, train_end=train_end, test_start=test_start)
        if not train_examples:
            raise RuntimeError("No training examples after applying train split.")
        if not test_examples:
            raise RuntimeError("No test examples after applying test split.")

        model = train_multinomial_logistic(
            train_examples,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            l2=args.l2,
            seed=args.seed,
        )
        scheduled_rows = load_scheduled_matches(db, args.current_limit)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "data_source": {
            "historical_matches_table": "historical_international_matches",
            "scheduled_matches_table": "matches",
            "team_table": "teams",
        },
        "config": {
            "min_prior_matches": args.min_prior_matches,
            "train_end": args.train_end,
            "test_start": args.test_start,
            "epochs": args.epochs,
            "learning_rate": args.learning_rate,
            "l2": args.l2,
            "seed": args.seed,
        },
        "dataset": {
            "historical_matches": len(historical_matches),
            "training_examples_total": len(examples),
            "train_examples": len(train_examples),
            "test_examples": len(test_examples),
            "train_label_distribution": label_distribution(train_examples),
            "test_label_distribution": label_distribution(test_examples),
        },
        "metrics": {
            "small_model": evaluate_model(model, test_examples),
            "elo_baseline": evaluate_baseline(test_examples),
            "class_prior": evaluate_prior(train_examples, test_examples),
        },
        "interpretation": {
            "top_coefficients": top_coefficients(model),
            "labels": list(LABELS),
            "positive_weight_note": "Positive weights increase the class logit after feature standardization; compare within the same label only.",
        },
        "current_match_sample": predict_scheduled_matches(model, final_states, scheduled_rows),
        "model": model.to_dict(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate a small 1X2 outcome model from cleaned match history.")
    parser.add_argument("--train-end", default="2024-01-01", help="Train on examples before this date, YYYY-MM-DD.")
    parser.add_argument("--test-start", default="2024-01-01", help="Evaluate on examples at or after this date, YYYY-MM-DD.")
    parser.add_argument("--min-prior-matches", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--learning-rate", type=float, default=0.025)
    parser.add_argument("--l2", type=float, default=0.0008)
    parser.add_argument("--seed", type=int, default=20260615)
    parser.add_argument("--current-limit", type=int, default=12)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = build_report(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "output": str(args.output),
        "dataset": report["dataset"],
        "metrics": report["metrics"],
        "current_match_sample_count": len(report["current_match_sample"]),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
