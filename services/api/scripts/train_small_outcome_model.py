from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import replace
from datetime import UTC, date, datetime, time
from math import log, log1p
from pathlib import Path
from typing import Any

from sqlalchemy import and_, asc, or_, select, text

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.schema import historical_international_matches, matches, model_features, teams
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
FEATURE_CONTEXT_SET = "match_pre_match_v1"
BASE_PROBABILITY_FEATURE_NAMES = (
    "base_prob_home_win",
    "base_prob_draw",
    "base_prob_away_win",
    "base_log_prob_home_win",
    "base_log_prob_draw",
    "base_log_prob_away_win",
)
STABLE_TEAM_STAT_METRICS = {
    "goals",
    "goal_against",
    "shots",
    "shots_on_target",
    "key_passes",
    "pass_accuracy",
    "rating",
    "market_value",
    "yellow_cards",
    "red_cards",
    "fouls",
    "big_chance_created",
    "big_chance_missed",
}


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    return float(value)


def rounded_probabilities(probabilities: list[float]) -> dict[str, float]:
    return {label: round(probabilities[index], 6) for index, label in enumerate(LABELS)}


def base_probability_features(probabilities: list[float]) -> dict[str, float]:
    eps = 1e-9
    clipped = [max(eps, min(1.0 - eps, value)) for value in probabilities]
    total = sum(clipped) or 1.0
    normalized = [value / total for value in clipped]
    return {
        "base_prob_home_win": normalized[0],
        "base_prob_draw": normalized[1],
        "base_prob_away_win": normalized[2],
        "base_log_prob_home_win": log(normalized[0]),
        "base_log_prob_draw": log(normalized[1]),
        "base_log_prob_away_win": log(normalized[2]),
    }


def sanitize_metric_name(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value.lower()).strip("_")


class CurrentContextFeatureStore:
    def __init__(self, feature_names: tuple[str, ...], team_vectors: dict[str, dict[str, float]], roster_team_ids: set[str]):
        self.feature_names = feature_names
        self.team_vectors = team_vectors
        self.roster_team_ids = roster_team_ids

    def has_team(self, team_id: str | None) -> bool:
        return bool(team_id and team_id in self.roster_team_ids and team_id in self.team_vectors)

    def diff_features(self, home_team_id: str | None, away_team_id: str | None) -> dict[str, float]:
        home = self.team_vectors.get(str(home_team_id), {})
        away = self.team_vectors.get(str(away_team_id), {})
        return {name: safe_float(home.get(name)) - safe_float(away.get(name)) for name in self.feature_names}


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


def load_current_context_feature_store(db, include_all_team_stats: bool = False) -> CurrentContextFeatureStore:
    roster_rows = db.execute(
        text(
            """
            with latest_player_form as (
                select distinct on (pf.player_id)
                    pf.player_id,
                    pf.form_score,
                    pf.goals,
                    pf.assists,
                    pf.shots,
                    pf.key_passes,
                    pf.minutes,
                    pf.availability_status
                from player_form_snapshots pf
                order by pf.player_id, pf.as_of_at desc
            )
            select
                t.id as team_id,
                t.fifa_rank,
                t.market_value_eur as team_market_value_eur,
                count(p.id) as roster_count,
                count(p.market_value_eur) as players_with_market_value,
                sum(coalesce(p.market_value_eur, 0)) as roster_market_value_eur,
                avg(p.market_value_eur) filter (where p.market_value_eur is not null) as avg_player_market_value_eur,
                count(lf.form_score) as player_form_count,
                avg(lf.form_score) as avg_form_score,
                sum(coalesce(lf.goals, 0)) as goals,
                sum(coalesce(lf.assists, 0)) as assists,
                sum(coalesce(lf.shots, 0)) as shots,
                sum(coalesce(lf.key_passes, 0)) as key_passes,
                sum(coalesce(lf.minutes, 0)) as minutes,
                count(*) filter (where lf.availability_status not in ('available', 'unknown')) as unavailable_count
            from teams t
            join players p on p.team_id = t.id and p.code like 'DQD-P%%'
            left join latest_player_form lf on lf.player_id = p.id
            group by t.id
            """
        )
    ).mappings().all()

    team_vectors: dict[str, dict[str, float]] = {}
    roster_team_ids: set[str] = set()
    base_feature_names = [
        "ctx_fifa_rank_strength",
        "ctx_team_market_value_log",
        "ctx_roster_count",
        "ctx_players_with_market_value_rate",
        "ctx_roster_market_value_log",
        "ctx_avg_player_market_value_log",
        "ctx_player_form_coverage_rate",
        "ctx_avg_form_score",
        "ctx_player_goals_per_player",
        "ctx_player_assists_per_player",
        "ctx_player_shots_per_player",
        "ctx_player_key_passes_per_player",
        "ctx_player_minutes_per_player",
        "ctx_unavailable_count",
    ]
    for row in roster_rows:
        team_id = str(row.team_id)
        roster_count = int(row.roster_count or 0)
        roster_team_ids.add(team_id)
        team_vectors[team_id] = {
            "ctx_fifa_rank_strength": -safe_float(row.fifa_rank, 99.0),
            "ctx_team_market_value_log": log1p(safe_float(row.team_market_value_eur)),
            "ctx_roster_count": float(roster_count),
            "ctx_players_with_market_value_rate": safe_float(row.players_with_market_value) / roster_count if roster_count else 0.0,
            "ctx_roster_market_value_log": log1p(safe_float(row.roster_market_value_eur)),
            "ctx_avg_player_market_value_log": log1p(safe_float(row.avg_player_market_value_eur)),
            "ctx_player_form_coverage_rate": safe_float(row.player_form_count) / roster_count if roster_count else 0.0,
            "ctx_avg_form_score": safe_float(row.avg_form_score),
            "ctx_player_goals_per_player": safe_float(row.goals) / roster_count if roster_count else 0.0,
            "ctx_player_assists_per_player": safe_float(row.assists) / roster_count if roster_count else 0.0,
            "ctx_player_shots_per_player": safe_float(row.shots) / roster_count if roster_count else 0.0,
            "ctx_player_key_passes_per_player": safe_float(row.key_passes) / roster_count if roster_count else 0.0,
            "ctx_player_minutes_per_player": safe_float(row.minutes) / roster_count if roster_count else 0.0,
            "ctx_unavailable_count": safe_float(row.unavailable_count),
        }

    coach_rows = db.execute(
        text(
            """
            select
                team_id,
                count(*) as coach_records,
                max(matches_count) as max_matches_count,
                max(win_rate) as best_win_rate,
                avg(win_rate) filter (where win_rate is not null) as avg_win_rate
            from coaches
            where team_id = any(:team_ids)
            group by team_id
            """
        ),
        {"team_ids": list(roster_team_ids)},
    ).mappings().all()
    coach_feature_names = [
        "ctx_coach_records_log",
        "ctx_coach_max_matches_log",
        "ctx_coach_best_win_rate",
        "ctx_coach_avg_win_rate",
    ]
    for row in coach_rows:
        vector = team_vectors.setdefault(str(row.team_id), {})
        vector.update(
            {
                "ctx_coach_records_log": log1p(safe_float(row.coach_records)),
                "ctx_coach_max_matches_log": log1p(safe_float(row.max_matches_count)),
                "ctx_coach_best_win_rate": safe_float(row.best_win_rate) / 100.0,
                "ctx_coach_avg_win_rate": safe_float(row.avg_win_rate) / 100.0,
            }
        )

    availability_rows = db.execute(
        text(
            """
            select team_id, sum(impact) as availability_impact, sum(signals) as availability_signals
            from (
                select team_id,
                       coalesce(sum(impact_score * confidence) filter (where is_model_eligible), 0) as impact,
                       count(*) filter (where is_model_eligible) as signals
                from injury_reports
                where team_id = any(:team_ids)
                group by team_id
                union all
                select team_id,
                       coalesce(sum(impact_score * confidence) filter (where is_model_eligible), 0) as impact,
                       count(*) filter (where is_model_eligible) as signals
                from ai_insights
                where team_id = any(:team_ids)
                group by team_id
            ) availability
            group by team_id
            """
        ),
        {"team_ids": list(roster_team_ids)},
    ).mappings().all()
    availability_feature_names = ["ctx_availability_impact", "ctx_availability_signals"]
    for row in availability_rows:
        vector = team_vectors.setdefault(str(row.team_id), {})
        vector.update(
            {
                "ctx_availability_impact": safe_float(row.availability_impact),
                "ctx_availability_signals": safe_float(row.availability_signals),
            }
        )

    metric_rows = db.execute(
        text(
            """
            select distinct on (team_id, metric_type)
                   team_id, metric_type, rank, numeric_value
            from team_stat_snapshots
            where team_id = any(:team_ids)
            order by team_id, metric_type, as_of_at desc
            """
        ),
        {"team_ids": list(roster_team_ids)},
    ).mappings().all()
    metric_types = sorted(
        {
            sanitize_metric_name(row.metric_type)
            for row in metric_rows
            if include_all_team_stats or sanitize_metric_name(row.metric_type) in STABLE_TEAM_STAT_METRICS
        }
    )
    metric_feature_names = []
    for metric_type in metric_types:
        metric_feature_names.append(f"ctx_team_stat_{metric_type}_value")
    for row in metric_rows:
        metric_type = sanitize_metric_name(row.metric_type)
        if metric_type not in metric_types:
            continue
        vector = team_vectors.setdefault(str(row.team_id), {})
        metric_value = safe_float(row.numeric_value)
        vector[f"ctx_team_stat_{metric_type}_value"] = log1p(metric_value) if metric_type == "market_value" else metric_value

    feature_names = tuple(base_feature_names + coach_feature_names + availability_feature_names + metric_feature_names)
    for vector in team_vectors.values():
        for name in feature_names:
            vector.setdefault(name, 0.0)
    return CurrentContextFeatureStore(feature_names=feature_names, team_vectors=team_vectors, roster_team_ids=roster_team_ids)


def augment_examples_with_current_context(
    examples,
    context_store: CurrentContextFeatureStore,
    roster_context_only: bool,
):
    output = []
    for example in examples:
        if roster_context_only and (
            not context_store.has_team(example.home_team_id)
            or not context_store.has_team(example.away_team_id)
        ):
            continue
        context_features = context_store.diff_features(example.home_team_id, example.away_team_id)
        output.append(replace(example, features={**example.features, **context_features}))
    return output


def examples_with_context_filter(
    examples,
    context_store: CurrentContextFeatureStore,
    roster_context_only: bool,
):
    if not roster_context_only:
        return list(examples)
    return [
        example
        for example in examples
        if context_store.has_team(example.home_team_id) and context_store.has_team(example.away_team_id)
    ]


def build_calibration_examples(
    core_model,
    examples,
    context_store: CurrentContextFeatureStore,
    roster_context_only: bool,
):
    output = []
    for example in examples_with_context_filter(examples, context_store, roster_context_only):
        base_probs = core_model.predict_proba(example.features)
        calibration_features = {
            **base_probability_features(base_probs),
            **context_store.diff_features(example.home_team_id, example.away_team_id),
        }
        output.append(replace(example, features=calibration_features))
    return output


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
        for feature_name, weight in zip(model.feature_names, model.weights[label_index][1:]):
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
            model_features.c.quality_status.label("match_feature_quality_status"),
            model_features.c.missing_features.label("match_feature_missing_features"),
            model_features.c.source_summary.label("match_feature_source_summary"),
        )
        .select_from(
            matches.join(home_team, matches.c.home_team_id == home_team.c.id)
            .join(away_team, matches.c.away_team_id == away_team.c.id)
            .outerjoin(
                model_features,
                and_(
                    model_features.c.entity_type == "match",
                    model_features.c.entity_key == matches.c.public_id,
                    model_features.c.feature_set == FEATURE_CONTEXT_SET,
                ),
            )
        )
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


def predict_scheduled_matches(
    model,
    states: dict[str, TeamState],
    scheduled_rows,
    context_store: CurrentContextFeatureStore | None = None,
    core_model=None,
) -> list[dict[str, Any]]:
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
        base_probabilities = None
        calibration_applied = False
        fallback_reason = None
        has_context_pair = (
            context_store is not None
            and context_store.has_team(str(row.home_team_id))
            and context_store.has_team(str(row.away_team_id))
        )
        if core_model is not None and context_store is not None:
            base_probabilities = core_model.predict_proba(features)
            if has_context_pair:
                features = {
                    **base_probability_features(base_probabilities),
                    **context_store.diff_features(str(row.home_team_id), str(row.away_team_id)),
                }
                probabilities = model.predict_proba(features)
                calibration_applied = True
            else:
                probabilities = base_probabilities
                fallback_reason = "missing_context_features"
        elif context_store is not None and has_context_pair:
            features.update(context_store.diff_features(str(row.home_team_id), str(row.away_team_id)))
            probabilities = model.predict_proba(features)
            calibration_applied = True
        else:
            probabilities = model.predict_proba(features)
        snapshot_model = model if calibration_applied or core_model is None else core_model
        prediction = {
            "match_id": row.public_id,
            "kickoff_at": row.kickoff_at.isoformat(),
            "home_team": row.home_team_name,
            "away_team": row.away_team_name,
            "home_team_code": row.home_team_code,
            "away_team_code": row.away_team_code,
            "inference_mode": "context_calibrated" if calibration_applied else "history_core_fallback" if fallback_reason else "history_core",
            "calibration_applied": calibration_applied,
            "fallback_reason": fallback_reason,
            "probabilities": rounded_probabilities(probabilities),
            "match_feature_quality_status": row.match_feature_quality_status,
            "match_feature_missing_count": len(row.match_feature_missing_features or []),
            "match_feature_sources": (row.match_feature_source_summary or {}).get("sources", []),
            "feature_snapshot": {
                name: round(safe_float(features.get(name)), 6)
                for name in snapshot_model.feature_names
            },
        }
        if base_probabilities is not None:
            prediction["base_probabilities"] = rounded_probabilities(base_probabilities)
        predictions.append(prediction)
    return predictions


def build_report(args) -> dict[str, Any]:
    with SessionLocal() as db:
        historical_matches = load_historical_matches(db)
        examples, final_states = build_examples(historical_matches, min_prior_matches=args.min_prior_matches)
        train_end = parse_date(args.train_end)
        test_start = parse_date(args.test_start)
        base_train_examples, base_test_examples = split_examples(examples, train_end=train_end, test_start=test_start)
        if not base_train_examples:
            raise RuntimeError("No training examples after applying train split.")
        if not base_test_examples:
            raise RuntimeError("No test examples after applying test split.")

        core_model = train_multinomial_logistic(
            base_train_examples,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            l2=args.l2,
            seed=args.seed,
            feature_names=FEATURE_NAMES,
        )
        mode = "history" if args.history_only else args.model_mode
        context_store = None
        core_model_for_current = None
        model = core_model
        model_family = "history_core"
        active_train_examples = base_train_examples
        active_test_examples = base_test_examples
        metrics = {
            "history_core": evaluate_model(core_model, base_test_examples),
            "elo_baseline": evaluate_baseline(base_test_examples),
            "class_prior": evaluate_prior(base_train_examples, base_test_examples),
        }
        model_payload: dict[str, Any] = {
            "mode": model_family,
            "history_core": core_model.to_dict(),
            "active_model": core_model.to_dict(),
        }

        if mode in {"calibrated", "joint"}:
            context_store = load_current_context_feature_store(db, include_all_team_stats=args.include_all_team_stats)

        if mode == "joint":
            active_examples = augment_examples_with_current_context(
                examples,
                context_store,
                roster_context_only=not args.allow_missing_context_training,
            )
            active_train_examples, active_test_examples = split_examples(
                active_examples, train_end=train_end, test_start=test_start
            )
            if not active_train_examples or not active_test_examples:
                raise RuntimeError("No context examples after applying train/test split.")
            feature_names = tuple(FEATURE_NAMES + context_store.feature_names)
            model = train_multinomial_logistic(
                active_train_examples,
                epochs=args.epochs,
                learning_rate=args.learning_rate,
                l2=args.l2,
                seed=args.seed,
                feature_names=feature_names,
            )
            model_family = "history_plus_current_context_joint"
            metrics = {
                "joint_model": evaluate_model(model, active_test_examples),
                "history_core_on_full_test": evaluate_model(core_model, base_test_examples),
                "elo_baseline_on_same_subset": evaluate_baseline(active_test_examples),
                "class_prior_on_same_subset": evaluate_prior(active_train_examples, active_test_examples),
            }
            model_payload = {
                "mode": model_family,
                "history_core": core_model.to_dict(),
                "joint_model": model.to_dict(),
                "active_model": model.to_dict(),
            }

        if mode == "calibrated":
            raw_context_examples = examples_with_context_filter(
                examples,
                context_store,
                roster_context_only=not args.allow_missing_context_training,
            )
            raw_context_train_examples, raw_context_test_examples = split_examples(
                raw_context_examples, train_end=train_end, test_start=test_start
            )
            active_train_examples = build_calibration_examples(
                core_model,
                raw_context_train_examples,
                context_store,
                roster_context_only=False,
            )
            active_test_examples = build_calibration_examples(
                core_model,
                raw_context_test_examples,
                context_store,
                roster_context_only=False,
            )
            if not active_train_examples or not active_test_examples:
                raise RuntimeError("No calibration examples after applying train/test split.")
            feature_names = tuple(BASE_PROBABILITY_FEATURE_NAMES + context_store.feature_names)
            model = train_multinomial_logistic(
                active_train_examples,
                epochs=args.epochs,
                learning_rate=args.learning_rate,
                l2=args.l2,
                seed=args.seed,
                feature_names=feature_names,
            )
            core_model_for_current = core_model
            model_family = "history_core_plus_context_calibrator"
            metrics = {
                "calibrated_model": evaluate_model(model, active_test_examples),
                "history_core_on_same_subset": evaluate_model(core_model, raw_context_test_examples),
                "elo_baseline_on_same_subset": evaluate_baseline(raw_context_test_examples),
                "history_core_full_test": evaluate_model(core_model, base_test_examples),
                "class_prior_on_same_subset": evaluate_prior(active_train_examples, active_test_examples),
            }
            model_payload = {
                "mode": model_family,
                "history_core": core_model.to_dict(),
                "context_calibrator": model.to_dict(),
                "active_model": model.to_dict(),
            }

        scheduled_rows = load_scheduled_matches(db, args.current_limit)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "data_source": {
            "historical_matches_table": "historical_international_matches",
            "scheduled_matches_table": "matches",
            "team_table": "teams",
            "feature_context_tables": [
                "players",
                "player_form_snapshots",
                "team_stat_snapshots",
                "coaches",
                "injury_reports",
                "ai_insights",
                "model_features",
            ]
            if context_store is not None
            else [],
        },
        "config": {
            "model_family": model_family,
            "model_mode": mode,
            "min_prior_matches": args.min_prior_matches,
            "train_end": args.train_end,
            "test_start": args.test_start,
            "epochs": args.epochs,
            "learning_rate": args.learning_rate,
            "l2": args.l2,
            "seed": args.seed,
            "history_only": args.history_only,
            "allow_missing_context_training": args.allow_missing_context_training,
            "include_all_team_stats": args.include_all_team_stats,
        },
        "dataset": {
            "historical_matches": len(historical_matches),
            "training_examples_total": len(examples),
            "base_train_examples": len(base_train_examples),
            "base_test_examples": len(base_test_examples),
            "active_train_examples": len(active_train_examples),
            "active_test_examples": len(active_test_examples),
            "active_train_label_distribution": label_distribution(active_train_examples),
            "active_test_label_distribution": label_distribution(active_test_examples),
            "feature_count": len(model.feature_names),
            "context_feature_count": 0 if context_store is None else len(context_store.feature_names),
            "roster_context_team_count": 0 if context_store is None else len(context_store.roster_team_ids),
        },
        "metrics": metrics,
        "interpretation": {
            "top_coefficients": top_coefficients(model),
            "history_core_top_coefficients": top_coefficients(core_model),
            "labels": list(LABELS),
            "positive_weight_note": "Positive weights increase the class logit after feature standardization; compare within the same label only.",
            "current_context_note": (
                "Two-layer mode: history_core learns from leakage-safe historical features; context_calibrator adjusts those base probabilities "
                "with current roster/player/team-board/coach/news features. Backtest metrics for current-only context remain directional until "
                "daily pre-match snapshots accumulate."
                if context_store is not None
                else "History-only model; no current roster/player/team-board context included."
            ),
        },
        "current_match_sample": predict_scheduled_matches(
            model,
            final_states,
            scheduled_rows,
            context_store=context_store,
            core_model=core_model_for_current,
        ),
        "model": model_payload,
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
    parser.add_argument(
        "--model-mode",
        choices=("calibrated", "joint", "history"),
        default="calibrated",
        help="calibrated trains a history core plus context calibrator; joint mixes all features in one model; history disables context.",
    )
    parser.add_argument("--history-only", action="store_true", help="Disable current roster/player/team-board context features.")
    parser.add_argument(
        "--include-all-team-stats",
        action="store_true",
        help="Use all 45 Dongqiudi team-board metrics instead of the default stable metric subset.",
    )
    parser.add_argument(
        "--allow-missing-context-training",
        action="store_true",
        help="Keep historical examples whose teams do not both have current Dongqiudi roster context, filling missing context with zero.",
    )
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
