from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import exp
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, desc, func, insert, or_, select, text, update
from sqlalchemy.orm import Session

from app.db.schema import (
    competition_stages,
    group_simulations,
    group_standings,
    match_predictions,
    matches,
    model_features,
    model_versions,
    prediction_snapshots,
    ranking_predictions,
    scoreline_predictions,
    teams,
)
from app.features.match_features import FEATURE_SET as MATCH_FEATURE_SET
from app.features.match_features import DONGQIUDI_MATCH_PUBLIC_ID_PREFIX, PREDICTION_MATCH_STATUSES, STALE_SCHEDULE_GRACE_HOURS
from app.features.match_features import MatchFeatureBuilder
from app.predictions.baseline import (
    MatchInputs,
    TeamInputs,
    build_match_prediction,
    calibrated_scoreline_distribution,
    expected_goals_from_scorelines,
    normalize_outcome_probabilities,
    outcome_key,
    ranked_scorelines,
    team_strength_score,
)
from app.predictions.scoreline_model import (
    PoissonGoalModel,
    SCORELINE_FEATURE_NAMES,
    build_scoreline_examples,
    context_adjusted_expected_goals,
    evaluate_scoreline_model,
    expected_goals_from_scorelines as scoreline_expected_goals,
    goal_feature_dict,
    outcome_probabilities_from_scorelines,
    ranked_scorelines as scoreline_ranked_scorelines,
    scoreline_distribution as model_scoreline_distribution,
    split_examples_by_date as split_scoreline_examples_by_date,
    train_poisson_goal_model,
)
from app.predictions.small_outcome_model import (
    FEATURE_NAMES,
    LABELS,
    SmallOutcomeModel,
    baseline_probabilities,
    build_examples,
    evaluate_baseline,
    evaluate_model,
    evaluate_prior,
    feature_dict,
    train_multinomial_logistic,
)
from scripts.train_small_outcome_model import (
    BASE_PROBABILITY_FEATURE_NAMES,
    DEFAULT_TRAINING_SEED,
    base_probability_features,
    blend_probabilities,
    build_calibration_examples,
    calibration_gate_result,
    examples_with_context_filter,
    load_current_context_feature_store,
    load_historical_matches,
    optimize_context_blend,
    rounded_probabilities,
    split_examples,
    top_coefficients,
)

API_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_SMALL_MODEL_VERSION = "small_outcome_2026_06_23_real_context_v3"
DEFAULT_SCORELINE_MODEL_VERSION = "scoreline_poisson_context_2026_06_17"
DEFAULT_PREDICTION_MODEL_VERSION = DEFAULT_SMALL_MODEL_VERSION
TRAIN_END = datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC"))
TEST_START = datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC"))
WORLD_CUP_GROUP_CODES = tuple(f"group-{letter}" for letter in "abcdefghijkl")
UNFILTERED_PREDICTION_SCOPES = {"all"}
GROUP_SIMULATION_MIN_PROBABILITY = 1e-9
WORLD_CUP_DIRECT_GROUP_QUALIFIERS = 2
WORLD_CUP_THIRD_PLACE_QUALIFIERS = 8
GOAL_ENVIRONMENT_BASELINE_TOTAL = 2.75
GOAL_ENVIRONMENT_MIN_MATCHES = 12


def clamp_value(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def calibrate_scorelines_to_outcome_probabilities(
    scorelines: list[dict],
    outcome_probabilities: dict[str, float],
) -> list[dict]:
    target = normalize_outcome_probabilities(outcome_probabilities)
    outcome_totals = {"home_win": 0.0, "draw": 0.0, "away_win": 0.0}
    for item in scorelines:
        outcome_totals[outcome_key(item["home_goals"], item["away_goals"])] += item["probability"]

    calibrated: list[dict] = []
    for item in scorelines:
        outcome = outcome_key(item["home_goals"], item["away_goals"])
        outcome_total = outcome_totals[outcome]
        if outcome_total <= 0:
            continue
        calibrated.append(
            {
                **item,
                "probability": item["probability"] / outcome_total * target[outcome],
            }
        )
    total = sum(item["probability"] for item in calibrated) or 1.0
    normalized = [{**item, "probability": item["probability"] / total} for item in calibrated]
    normalized.sort(key=lambda item: item["probability"], reverse=True)
    return normalized


def prediction_match_statuses(scope: str) -> tuple[str, ...] | None:
    if (scope or "matchday").lower() in UNFILTERED_PREDICTION_SCOPES:
        return None
    return PREDICTION_MATCH_STATUSES


def prediction_match_filters(scope: str, public_ids: list[str] | None = None) -> list[Any]:
    if public_ids:
        return [matches.c.public_id.in_(public_ids)]
    filters: list[Any] = [matches.c.public_id.like(f"{DONGQIUDI_MATCH_PUBLIC_ID_PREFIX}%")]
    statuses = prediction_match_statuses(scope)
    if statuses:
        filters.append(matches.c.status.in_(statuses))
        filters.append(
            or_(
                matches.c.status == "live",
                matches.c.kickoff_at >= text(f"now() - interval '{STALE_SCHEDULE_GRACE_HOURS} hours'"),
            )
        )
    return filters


@dataclass(frozen=True)
class SmallOutcomeRuntime:
    model_version_id: Any
    model_version: str
    model_family: str
    active_model: SmallOutcomeModel
    history_core: SmallOutcomeModel
    context_store: Any | None
    context_blend_weight: float | None
    final_states: dict[str, Any]


@dataclass(frozen=True)
class ScorelineRuntime:
    model_version_id: Any
    model_version: str
    model_family: str
    model: PoissonGoalModel
    final_states: dict[str, Any]


class BaselinePredictionService:
    def __init__(self, db: Session):
        self.db = db

    def recompute(
        self,
        scope: str = "matchday",
        match_ids: list[str] | None = None,
        model_version: str = DEFAULT_PREDICTION_MODEL_VERSION,
        seed: int | None = None,
        model_kind: str | None = None,
    ) -> dict:
        selected_kind = model_kind or (
            "baseline"
            if model_version.startswith("baseline")
            else "scoreline"
            if model_version.startswith("scoreline")
            else "small_outcome"
        )
        if selected_kind == "baseline":
            return self.recompute_baseline(scope=scope, match_ids=match_ids, model_version=model_version, seed=seed)
        if selected_kind == "scoreline":
            return self.recompute_scoreline(scope=scope, match_ids=match_ids, model_version=model_version, seed=seed)

        try:
            return self.recompute_small_outcome(scope=scope, match_ids=match_ids, model_version=model_version, seed=seed)
        except RuntimeError as exc:
            result = self.recompute_baseline(
                scope=scope,
                match_ids=match_ids,
                model_version="baseline_2026_06_13",
                seed=seed,
            )
            result["status"] = "completed_with_model_fallback"
            result["requested_model_version"] = model_version
            result["fallback_reason"] = str(exc)
            return result

    def recompute_scoreline(
        self,
        scope: str = "matchday",
        match_ids: list[str] | None = None,
        model_version: str = DEFAULT_SCORELINE_MODEL_VERSION,
        seed: int | None = None,
    ) -> dict:
        seed_value = seed or DEFAULT_TRAINING_SEED
        statuses = prediction_match_statuses(scope)
        feature_result = MatchFeatureBuilder(self.db).build(
            public_ids=match_ids,
            roster_only=False,
            public_id_prefix=DONGQIUDI_MATCH_PUBLIC_ID_PREFIX,
            statuses=statuses,
        )
        runtime = self.ensure_scoreline_runtime(model_version=model_version, seed=seed_value)
        snapshot_id = self.create_snapshot(
            runtime.model_version_id,
            scope,
            seed_value,
            notes=f"Generated by {runtime.model_family}; feature_snapshot_as_of={feature_result['snapshot_as_of_at']}",
        )
        match_rows = self.load_matches(match_ids, scope=scope)

        written_matches = 0
        for row in match_rows:
            prediction = self.build_scoreline_prediction(row, runtime)
            self.write_match_prediction(row.match_id, snapshot_id, runtime.model_version_id, prediction)
            written_matches += 1

        ranking_count = self.write_rankings(snapshot_id)
        simulation_count = self.write_group_simulations(snapshot_id)
        self.db.commit()
        return {
            "status": "completed",
            "scope": scope,
            "match_ids": match_ids or [],
            "model_kind": "scoreline",
            "model_version": runtime.model_version,
            "model_family": runtime.model_family,
            "prediction_snapshot_id": str(snapshot_id),
            "feature_snapshot": feature_result,
            "matches_written": written_matches,
            "rankings_written": ranking_count,
            "group_simulations_written": simulation_count,
        }

    def recompute_small_outcome(
        self,
        scope: str = "matchday",
        match_ids: list[str] | None = None,
        model_version: str = DEFAULT_SMALL_MODEL_VERSION,
        seed: int | None = None,
    ) -> dict:
        seed_value = seed or DEFAULT_TRAINING_SEED
        statuses = prediction_match_statuses(scope)
        feature_result = MatchFeatureBuilder(self.db).build(
            public_ids=match_ids,
            roster_only=False,
            public_id_prefix=DONGQIUDI_MATCH_PUBLIC_ID_PREFIX,
            statuses=statuses,
        )
        runtime = self.ensure_small_outcome_runtime(model_version=model_version, seed=seed_value)
        snapshot_id = self.create_snapshot(
            runtime.model_version_id,
            scope,
            seed_value,
            notes=f"Generated by {runtime.model_family}; feature_snapshot_as_of={feature_result['snapshot_as_of_at']}",
        )
        match_rows = self.load_matches(match_ids, scope=scope)

        written_matches = 0
        for row in match_rows:
            prediction = self.build_small_outcome_prediction(row, runtime)
            self.write_match_prediction(row.match_id, snapshot_id, runtime.model_version_id, prediction)
            written_matches += 1

        ranking_count = self.write_rankings(snapshot_id)
        simulation_count = self.write_group_simulations(snapshot_id)
        self.db.commit()
        return {
            "status": "completed",
            "scope": scope,
            "match_ids": match_ids or [],
            "model_kind": "small_outcome",
            "model_version": runtime.model_version,
            "model_family": runtime.model_family,
            "prediction_snapshot_id": str(snapshot_id),
            "feature_snapshot": feature_result,
            "matches_written": written_matches,
            "rankings_written": ranking_count,
            "group_simulations_written": simulation_count,
        }

    def recompute_baseline(
        self,
        scope: str = "matchday",
        match_ids: list[str] | None = None,
        model_version: str = "baseline_2026_06_13",
        seed: int | None = None,
    ) -> dict:
        seed_value = seed or int(datetime.now(API_TZ).strftime("%Y%m%d"))
        model_version_id = self.ensure_baseline_model_version(model_version)
        snapshot_id = self.create_snapshot(model_version_id, scope, seed_value, notes="Generated by deterministic MVP baseline")
        match_rows = self.load_matches(match_ids, scope=scope)

        written_matches = 0
        for row in match_rows:
            prediction = build_match_prediction(self.match_inputs(row))
            prediction.update(
                {
                    "inference_mode": "baseline",
                    "calibration_applied": False,
                    "fallback_reason": None,
                    "base_probabilities": None,
                    "feature_snapshot": {},
                    "feature_quality_status": row.match_feature_quality_status,
                    "feature_missing_count": len(row.match_feature_missing_features or []),
                    "feature_sources": self.feature_sources(row),
                }
            )
            self.write_match_prediction(row.match_id, snapshot_id, model_version_id, prediction)
            written_matches += 1

        ranking_count = self.write_rankings(snapshot_id)
        simulation_count = self.write_group_simulations(snapshot_id)
        self.db.commit()
        return {
            "status": "completed",
            "scope": scope,
            "match_ids": match_ids or [],
            "model_kind": "baseline",
            "model_version": model_version,
            "prediction_snapshot_id": str(snapshot_id),
            "matches_written": written_matches,
            "rankings_written": ranking_count,
            "group_simulations_written": simulation_count,
        }

    def ensure_scoreline_runtime(self, model_version: str, seed: int) -> ScorelineRuntime:
        historical_matches = load_historical_matches(self.db)
        if not historical_matches:
            raise RuntimeError("scoreline_model_unavailable:no_historical_matches")
        goal_examples, scoreline_examples, final_states = build_scoreline_examples(historical_matches, min_prior_matches=5)
        if not goal_examples or not scoreline_examples:
            raise RuntimeError("scoreline_model_unavailable:no_training_examples")

        existing = self.db.execute(
            select(model_versions).where(model_versions.c.name == "scoreline", model_versions.c.version == model_version)
        ).mappings().first()
        if existing and existing.feature_schema.get("model"):
            return ScorelineRuntime(
                model_version_id=existing.id,
                model_version=model_version,
                model_family=existing.model_type,
                model=PoissonGoalModel.from_dict(existing.feature_schema["model"]),
                final_states=final_states,
            )

        train_goals, test_goals = split_scoreline_examples_by_date(goal_examples, train_end=TRAIN_END, test_start=TEST_START)
        _train_scorelines, test_scorelines = split_scoreline_examples_by_date(
            scoreline_examples,
            train_end=TRAIN_END,
            test_start=TEST_START,
        )
        if not train_goals or not test_goals:
            raise RuntimeError("scoreline_model_unavailable:empty_train_or_test_split")

        model = train_poisson_goal_model(
            train_goals,
            epochs=45,
            learning_rate=0.008,
            l2=0.0005,
            seed=seed,
            feature_names=SCORELINE_FEATURE_NAMES,
        )
        metrics = {
            "goal_examples_total": len(goal_examples),
            "scoreline_examples_total": len(scoreline_examples),
            "train_goal_examples": len(train_goals),
            "test_goal_examples": len(test_goals),
            "test_scoreline_examples": len(test_scorelines),
            "test_metrics": evaluate_scoreline_model(model, test_scorelines),
        }
        feature_schema = {
            "feature_set": MATCH_FEATURE_SET,
            "model_family": "poisson_goal_scoreline_context",
            "feature_names": list(SCORELINE_FEATURE_NAMES),
            "context_adjustments": [
                "market_value_log_diff",
                "player_goals_per_player_diff",
                "player_assists_per_player_diff",
                "availability_impact",
                "player_unavailable_count",
                "weather_wind_speed_kph",
                "weather_precipitation_mm",
                "weather_temperature_c",
            ],
            "training_config": {
                "train_end": TRAIN_END.date().isoformat(),
                "test_start": TEST_START.date().isoformat(),
                "min_prior_matches": 5,
                "epochs": 45,
                "learning_rate": 0.008,
                "l2": 0.0005,
                "seed": seed,
            },
            "model": model.to_dict(),
        }
        self.db.execute(update(model_versions).where(model_versions.c.name == "scoreline").values(is_active=False))
        model_version_id = self.db.execute(
            insert(model_versions)
            .values(
                name="scoreline",
                version=model_version,
                model_type="poisson_goal_scoreline_context",
                training_data_start=min(item.played_at.date() for item in historical_matches),
                training_data_end=max(item.played_at.date() for item in historical_matches),
                feature_schema=feature_schema,
                metrics=metrics,
                is_active=True,
            )
            .returning(model_versions.c.id)
        ).scalar_one()
        return ScorelineRuntime(
            model_version_id=model_version_id,
            model_version=model_version,
            model_family="poisson_goal_scoreline_context",
            model=model,
            final_states=final_states,
        )

    def ensure_small_outcome_runtime(self, model_version: str, seed: int) -> SmallOutcomeRuntime:
        historical_matches = load_historical_matches(self.db)
        if not historical_matches:
            raise RuntimeError("small_outcome_unavailable:no_historical_matches")
        examples, final_states = build_examples(historical_matches, min_prior_matches=5)
        if not examples:
            raise RuntimeError("small_outcome_unavailable:no_training_examples")

        existing = self.db.execute(
            select(model_versions).where(model_versions.c.name == "small_outcome", model_versions.c.version == model_version)
        ).mappings().first()
        context_store = load_current_context_feature_store(self.db)
        if existing and existing.feature_schema.get("model"):
            payload = existing.feature_schema["model"]
            history_core = SmallOutcomeModel.from_dict(payload["history_core"])
            active_model = SmallOutcomeModel.from_dict(payload.get("context_calibrator") or payload["active_model"])
            model_family = existing.model_type
            gate = (existing.metrics or {}).get("calibration_gate")
            context_blend_weight = payload.get("context_blend_weight")
            if context_blend_weight is None:
                context_blend_weight = ((existing.metrics or {}).get("context_blend") or {}).get("context_weight")
            context_blend_weight = float(context_blend_weight) if context_blend_weight is not None else None
            if model_family in {"history_core_plus_context_calibrator", "history_core_plus_context_blend"}:
                gate = gate or calibration_gate_result(existing.metrics or {})
                if not gate.get("accepted", False):
                    active_model = history_core
                    model_family = "history_core"
                    context_store = None
                    context_blend_weight = None
            return SmallOutcomeRuntime(
                model_version_id=existing.id,
                model_version=model_version,
                model_family=model_family,
                active_model=active_model,
                history_core=history_core,
                context_store=context_store,
                context_blend_weight=context_blend_weight,
                final_states=final_states,
            )

        base_train_examples, base_test_examples = split_examples(examples, train_end=TRAIN_END, test_start=TEST_START)
        if not base_train_examples or not base_test_examples:
            raise RuntimeError("small_outcome_unavailable:empty_train_or_test_split")

        history_core = train_multinomial_logistic(
            base_train_examples,
            epochs=30,
            learning_rate=0.025,
            l2=0.0008,
            seed=seed,
            feature_names=FEATURE_NAMES,
        )
        raw_context_examples = examples_with_context_filter(examples, context_store, roster_context_only=True)
        strict_context_examples_count = sum(
            1
            for example in examples
            if context_store.has_team(example.home_team_id) and context_store.has_team(example.away_team_id)
        )
        raw_context_train_examples, raw_context_test_examples = split_examples(
            raw_context_examples, train_end=TRAIN_END, test_start=TEST_START
        )
        if raw_context_train_examples and raw_context_test_examples:
            active_train_examples = build_calibration_examples(
                history_core,
                raw_context_train_examples,
                context_store,
                roster_context_only=False,
            )
            active_test_examples = build_calibration_examples(
                history_core,
                raw_context_test_examples,
                context_store,
                roster_context_only=False,
            )
            active_model = train_multinomial_logistic(
                active_train_examples,
                epochs=30,
                learning_rate=0.025,
                l2=0.0008,
                seed=seed,
                feature_names=tuple(BASE_PROBABILITY_FEATURE_NAMES + context_store.feature_names),
            )
            calibrated_probability_rows = [
                active_model.predict_proba(example.features)
                for example in active_test_examples
            ]
            baseline_probability_rows = [
                baseline_probabilities(example)
                for example in raw_context_test_examples
            ]
            blend = optimize_context_blend(
                raw_context_test_examples,
                calibrated_probability_rows,
                baseline_probability_rows,
            )
            metrics = {
                "calibrated_model": evaluate_model(active_model, active_test_examples),
                "blended_model": blend["metrics"],
                "history_core_on_same_subset": evaluate_model(history_core, raw_context_test_examples),
                "elo_baseline_on_same_subset": evaluate_baseline(raw_context_test_examples),
                "history_core_full_test": evaluate_model(history_core, base_test_examples),
                "class_prior_on_same_subset": evaluate_prior(active_train_examples, active_test_examples),
                "context_blend": {
                    "context_weight": blend["context_weight"],
                    "baseline_weight": round(1.0 - float(blend["context_weight"]), 4),
                    "search_step": 0.02,
                    "baseline": "elo_baseline_on_same_subset",
                    "context_model": "calibrated_model",
                },
            }
            gate = calibration_gate_result(metrics)
            metrics["calibration_gate"] = gate
            if gate["accepted"]:
                model_family = "history_core_plus_context_blend"
                context_blend_weight = float(blend["context_weight"])
                model_payload = {
                    "history_core": history_core.to_dict(),
                    "context_calibrator": active_model.to_dict(),
                    "active_model": active_model.to_dict(),
                    "context_blend_weight": context_blend_weight,
                    "calibration_gate": gate,
                }
            else:
                context_calibrator = active_model
                active_model = history_core
                context_store = None
                context_blend_weight = None
                model_family = "history_core"
                model_payload = {
                    "history_core": history_core.to_dict(),
                    "rejected_context_calibrator": context_calibrator.to_dict(),
                    "active_model": history_core.to_dict(),
                    "calibration_gate": gate,
                }
            active_train_count = len(active_train_examples)
            active_test_count = len(active_test_examples)
        else:
            active_model = history_core
            model_family = "history_core"
            context_blend_weight = None
            metrics = {
                "history_core": evaluate_model(history_core, base_test_examples),
                "elo_baseline": evaluate_baseline(base_test_examples),
                "class_prior": evaluate_prior(base_train_examples, base_test_examples),
            }
            model_payload = {
                "history_core": history_core.to_dict(),
                "active_model": history_core.to_dict(),
            }
            active_train_count = len(base_train_examples)
            active_test_count = len(base_test_examples)

        feature_schema = {
            "feature_set": MATCH_FEATURE_SET,
            "model_family": model_family,
            "labels": list(LABELS),
            "history_feature_names": list(FEATURE_NAMES),
            "context_feature_names": [] if context_store is None else list(context_store.feature_names),
            "base_probability_feature_names": list(BASE_PROBABILITY_FEATURE_NAMES),
            "training_config": {
                "train_end": TRAIN_END.date().isoformat(),
                "test_start": TEST_START.date().isoformat(),
                "min_prior_matches": 5,
                "epochs": 30,
                "learning_rate": 0.025,
                "l2": 0.0008,
                "seed": seed,
            },
            "dataset": {
                "historical_matches": len(historical_matches),
                "training_examples_total": len(examples),
                "base_train_examples": len(base_train_examples),
                "base_test_examples": len(base_test_examples),
                "mapped_context_examples": len(raw_context_examples),
                "strict_context_examples": strict_context_examples_count,
                "active_train_examples": active_train_count,
                "active_test_examples": active_test_count,
                "roster_context_team_count": 0 if context_store is None else len(context_store.roster_team_ids),
                "context_training_policy": (
                    "mapped_roster_team_context; missing numeric context is zero-filled for training, "
                    "while current-match inference still requires critical context fields"
                ),
            },
            "interpretation": {
                "top_coefficients": top_coefficients(active_model),
                "history_core_top_coefficients": top_coefficients(history_core),
            },
            "model": model_payload,
        }
        self.db.execute(update(model_versions).where(model_versions.c.name == "small_outcome").values(is_active=False))
        model_version_id = self.db.execute(
            insert(model_versions)
            .values(
                name="small_outcome",
                version=model_version,
                model_type=model_family,
                training_data_start=min(item.played_at.date() for item in historical_matches),
                training_data_end=max(item.played_at.date() for item in historical_matches),
                feature_schema=feature_schema,
                metrics=metrics,
                is_active=True,
            )
            .returning(model_versions.c.id)
        ).scalar_one()
        return SmallOutcomeRuntime(
            model_version_id=model_version_id,
            model_version=model_version,
            model_family=model_family,
            active_model=active_model,
            history_core=history_core,
            context_store=context_store,
            context_blend_weight=context_blend_weight,
            final_states=final_states,
        )

    def ensure_baseline_model_version(self, version: str):
        row = self.db.execute(
            select(model_versions.c.id).where(model_versions.c.name == "baseline", model_versions.c.version == version)
        ).first()
        if row:
            return row.id

        return self.db.execute(
            insert(model_versions)
            .values(
                name="baseline",
                version=version,
                model_type="elo_poisson",
                feature_schema={
                    "features": ["elo_diff", "fifa_rank_diff", "venue_advantage"],
                    "note": "MVP deterministic baseline",
                },
                is_active=True,
            )
            .returning(model_versions.c.id)
        ).scalar_one()

    def create_snapshot(self, model_version_id, scope: str, seed: int, notes: str):
        return self.db.execute(
            insert(prediction_snapshots)
            .values(
                model_version_id=model_version_id,
                scope=scope,
                status="success",
                seed=seed,
                notes=notes,
            )
            .returning(prediction_snapshots.c.id)
        ).scalar_one()

    def load_matches(self, public_ids: list[str] | None = None, scope: str = "matchday"):
        home = teams.alias("home_team")
        away = teams.alias("away_team")
        latest_features = (
            select(
                model_features.c.entity_key.label("entity_key"),
                func.max(model_features.c.as_of_at).label("as_of_at"),
            )
            .where(
                and_(
                    model_features.c.entity_type == "match",
                    model_features.c.feature_set == MATCH_FEATURE_SET,
                )
            )
            .group_by(model_features.c.entity_key)
            .subquery()
        )
        query = (
            select(
                matches.c.id.label("match_id"),
                matches.c.public_id,
                matches.c.home_team_id,
                matches.c.away_team_id,
                matches.c.kickoff_at,
                matches.c.neutral_site,
                matches.c.source_confidence,
                home.c.code.label("home_code"),
                home.c.name_zh.label("home_name"),
                home.c.fifa_rank.label("home_fifa_rank"),
                home.c.elo_rating.label("home_elo_rating"),
                away.c.code.label("away_code"),
                away.c.name_zh.label("away_name"),
                away.c.fifa_rank.label("away_fifa_rank"),
                away.c.elo_rating.label("away_elo_rating"),
                model_features.c.quality_status.label("match_feature_quality_status"),
                model_features.c.missing_features.label("match_feature_missing_features"),
                model_features.c.source_summary.label("match_feature_source_summary"),
                model_features.c.features.label("match_feature_payload"),
            )
            .join(home, matches.c.home_team_id == home.c.id)
            .join(away, matches.c.away_team_id == away.c.id)
            .outerjoin(latest_features, latest_features.c.entity_key == matches.c.public_id)
            .outerjoin(
                model_features,
                and_(
                    model_features.c.entity_type == "match",
                    model_features.c.entity_key == matches.c.public_id,
                    model_features.c.feature_set == MATCH_FEATURE_SET,
                    model_features.c.as_of_at == latest_features.c.as_of_at,
                ),
            )
            .order_by(matches.c.kickoff_at.asc())
        )
        if public_ids:
            query = query.where(*prediction_match_filters(scope, public_ids))
        else:
            query = query.where(*prediction_match_filters(scope))
        return self.db.execute(query).mappings().all()

    def scoreline_model_projection(self, row, runtime: ScorelineRuntime) -> dict | None:
        home_state = runtime.final_states.get(str(row.home_team_id))
        away_state = runtime.final_states.get(str(row.away_team_id))
        if home_state is None or away_state is None:
            return None

        home_features = goal_feature_dict(home_state, away_state, row.kickoff_at, bool(row.neutral_site), "FIFA World Cup", True)
        away_features = goal_feature_dict(away_state, home_state, row.kickoff_at, bool(row.neutral_site), "FIFA World Cup", False)
        base_home_xg = runtime.model.predict_goals(home_features)
        base_away_xg = runtime.model.predict_goals(away_features)
        feature_payload = row.match_feature_payload or {}
        numeric_features = feature_payload.get("numeric") or {}
        home_xg, away_xg, context_adjustments = context_adjusted_expected_goals(
            base_home_xg,
            base_away_xg,
            numeric_features,
        )
        full_scorelines = model_scoreline_distribution(
            home_xg,
            away_xg,
            low_score_correlation=runtime.model.low_score_correlation,
        )
        expected_home, expected_away = scoreline_expected_goals(full_scorelines)
        feature_snapshot = {
            "scoreline_model_version": runtime.model_version,
            "base_home_expected_goals": round(base_home_xg, 6),
            "base_away_expected_goals": round(base_away_xg, 6),
            "context_home_expected_goals": round(home_xg, 6),
            "context_away_expected_goals": round(away_xg, 6),
            "context_adjustments": context_adjustments,
            "context_numeric_features": {
                key: numeric_features.get(key)
                for key in (
                    "market_value_log_diff",
                    "player_goals_per_player_diff",
                    "player_assists_per_player_diff",
                    "home_availability_impact",
                    "away_availability_impact",
                    "home_player_unavailable_count",
                    "away_player_unavailable_count",
                    "weather_wind_speed_kph",
                    "weather_precipitation_mm",
                    "weather_temperature_c",
                )
                if numeric_features.get(key) is not None
            },
            **{f"home_goal_{name}": round(float(home_features.get(name, 0.0) or 0.0), 6) for name in runtime.model.feature_names},
            **{f"away_goal_{name}": round(float(away_features.get(name, 0.0) or 0.0), 6) for name in runtime.model.feature_names},
        }
        return {
            "model_family": runtime.model_family,
            "full_scorelines": full_scorelines,
            "expected_goals": {"home": expected_home, "away": expected_away},
            "context_adjustments": context_adjustments,
            "feature_snapshot": feature_snapshot,
        }

    def tournament_goal_environment(self, kickoff_at: datetime) -> tuple[float, dict[str, Any] | None]:
        sample = self.db.execute(
            select(
                func.count().label("matches"),
                func.avg(matches.c.home_score + matches.c.away_score).label("avg_total_goals"),
            ).where(
                matches.c.public_id.like(f"{DONGQIUDI_MATCH_PUBLIC_ID_PREFIX}%"),
                matches.c.status == "finished",
                matches.c.home_score.is_not(None),
                matches.c.away_score.is_not(None),
                matches.c.kickoff_at < kickoff_at,
            )
        ).mappings().one()
        match_count = int(sample["matches"] or 0)
        if match_count < GOAL_ENVIRONMENT_MIN_MATCHES or sample["avg_total_goals"] is None:
            return 1.0, None

        observed_avg = float(sample["avg_total_goals"])
        multiplier = clamp_value(observed_avg / GOAL_ENVIRONMENT_BASELINE_TOTAL, 0.92, 1.18)
        return multiplier, {
            "matches": match_count,
            "observed_avg_total_goals": round(observed_avg, 4),
            "baseline_avg_total_goals": GOAL_ENVIRONMENT_BASELINE_TOTAL,
            "multiplier": round(multiplier, 4),
        }

    def build_scoreline_prediction(self, row, runtime: ScorelineRuntime) -> dict:
        baseline_prediction = build_match_prediction(self.match_inputs(row))
        projection = self.scoreline_model_projection(row, runtime)
        if projection is None:
            baseline_prediction.update(
                {
                    "inference_mode": "baseline",
                    "calibration_applied": False,
                    "fallback_reason": "missing_scoreline_state",
                    "base_probabilities": None,
                    "feature_snapshot": {},
                    "feature_quality_status": row.match_feature_quality_status,
                    "feature_missing_count": len(row.match_feature_missing_features or []),
                    "feature_sources": self.feature_sources(row),
                }
            )
            return baseline_prediction

        full_scorelines = projection["full_scorelines"]
        expected_goals = projection["expected_goals"]
        probabilities = outcome_probabilities_from_scorelines(full_scorelines)
        confidence = baseline_prediction["confidence"]
        if row.match_feature_quality_status == "insufficient":
            confidence = "low"

        return {
            "probabilities": probabilities,
            "expected_goals": expected_goals,
            "confidence": confidence,
            "key_factors": [
                *baseline_prediction["key_factors"],
                {
                    "label": "scoreline_model",
                    "value": 1,
                    "note": runtime.model_family,
                },
                {
                    "label": "model_xg_diff",
                    "value": round(expected_goals["home"] - expected_goals["away"], 3),
                    "note": "Scoreline model expected-goal edge",
                },
                *projection["context_adjustments"],
            ],
            "scorelines": scoreline_ranked_scorelines(full_scorelines),
            "inference_mode": "scoreline_model",
            "calibration_applied": False,
            "fallback_reason": None,
            "base_probabilities": None,
            "feature_snapshot": projection["feature_snapshot"],
            "feature_quality_status": row.match_feature_quality_status,
            "feature_missing_count": len(row.match_feature_missing_features or []),
            "feature_sources": self.feature_sources(row),
        }

    def build_small_outcome_prediction(
        self,
        row,
        runtime: SmallOutcomeRuntime,
        scoreline_runtime: ScorelineRuntime | None = None,
    ) -> dict:
        baseline_prediction = build_match_prediction(self.match_inputs(row))
        home_state = runtime.final_states.get(str(row.home_team_id))
        away_state = runtime.final_states.get(str(row.away_team_id))
        if home_state is None or away_state is None:
            baseline_prediction.update(
                {
                    "inference_mode": "baseline",
                    "calibration_applied": False,
                    "fallback_reason": "missing_historical_state",
                    "base_probabilities": None,
                    "feature_snapshot": {},
                    "feature_quality_status": row.match_feature_quality_status,
                    "feature_missing_count": len(row.match_feature_missing_features or []),
                    "feature_sources": self.feature_sources(row),
                }
            )
            return baseline_prediction

        history_features = feature_dict(home_state, away_state, row.kickoff_at, bool(row.neutral_site), "FIFA World Cup")
        base_probabilities = runtime.history_core.predict_proba(history_features)
        deterministic_baseline_probabilities = [
            baseline_prediction["probabilities"][label]
            for label in LABELS
        ]
        features = history_features
        calibration_applied = False
        fallback_reason = None
        probabilities = base_probabilities

        has_context_pair = (
            runtime.context_store is not None
            and runtime.context_store.has_team(str(row.home_team_id))
            and runtime.context_store.has_team(str(row.away_team_id))
            and runtime.model_family in {"history_core_plus_context_calibrator", "history_core_plus_context_blend"}
        )
        if has_context_pair:
            features = {
                **base_probability_features(base_probabilities),
                **runtime.context_store.diff_features(str(row.home_team_id), str(row.away_team_id)),
            }
            context_probabilities = runtime.active_model.predict_proba(features)
            if runtime.model_family == "history_core_plus_context_blend":
                probabilities = blend_probabilities(
                    context_probabilities,
                    deterministic_baseline_probabilities,
                    runtime.context_blend_weight if runtime.context_blend_weight is not None else 1.0,
                )
            else:
                probabilities = context_probabilities
            calibration_applied = True
        elif runtime.model_family in {"history_core_plus_context_calibrator", "history_core_plus_context_blend"}:
            fallback_reason = "missing_context_features"

        snapshot_model = runtime.active_model if calibration_applied else runtime.history_core
        model_probabilities = normalize_probabilities(probabilities)
        scoreline_projection = (
            self.scoreline_model_projection(row, scoreline_runtime)
            if scoreline_runtime is not None
            else None
        )
        scoreline_key_factors = []
        scoreline_feature_snapshot: dict[str, Any] = {"scoreline_source": "baseline_poisson"}
        if scoreline_projection is not None:
            calibrated_scorelines = calibrate_scorelines_to_outcome_probabilities(
                scoreline_projection["full_scorelines"],
                model_probabilities,
            )
            home_xg, away_xg = scoreline_expected_goals(calibrated_scorelines)
            scoreline_feature_snapshot = {
                "scoreline_source": "scoreline_model_calibrated_to_outcome",
                **scoreline_projection["feature_snapshot"],
            }
            scoreline_key_factors = [
                {
                    "label": "scoreline_model",
                    "value": 1,
                    "note": scoreline_projection["model_family"],
                },
                {
                    "label": "model_xg_diff",
                    "value": round(home_xg - away_xg, 3),
                    "note": "Scoreline model expected-goal edge calibrated to outcome probabilities",
                },
                *scoreline_projection["context_adjustments"],
            ]
        else:
            goal_multiplier, goal_environment = self.tournament_goal_environment(row.kickoff_at)
            base_home_xg = baseline_prediction["expected_goals"]["home"]
            base_away_xg = baseline_prediction["expected_goals"]["away"]
            calibrated_scorelines = calibrated_scoreline_distribution(
                base_home_xg * goal_multiplier,
                base_away_xg * goal_multiplier,
                model_probabilities,
            )
            home_xg, away_xg = expected_goals_from_scorelines(calibrated_scorelines)
            if goal_environment is not None:
                scoreline_feature_snapshot = {
                    "scoreline_source": "baseline_poisson_tournament_adjusted",
                    "base_home_expected_goals": round(base_home_xg, 6),
                    "base_away_expected_goals": round(base_away_xg, 6),
                    "goal_environment": goal_environment,
                }
                scoreline_key_factors = [
                    {
                        "label": "tournament_goal_environment",
                        "value": goal_environment["multiplier"],
                        "note": "Observed finished-match goal rate applied to scoreline distribution",
                    }
                ]
        baseline_prediction["probabilities"] = model_probabilities
        baseline_prediction["expected_goals"] = {"home": home_xg, "away": away_xg}
        baseline_prediction["scorelines"] = ranked_scorelines(calibrated_scorelines)
        baseline_prediction.update(
            {
                "inference_mode": "context_calibrated" if calibration_applied else "history_core_fallback" if fallback_reason else "history_core",
                "calibration_applied": calibration_applied,
                "fallback_reason": fallback_reason,
                "base_probabilities": rounded_probabilities(base_probabilities),
                "feature_snapshot": {
                    **{
                        name: round(float(features.get(name, 0.0) or 0.0), 6)
                        for name in snapshot_model.feature_names
                    },
                    **(
                        {
                            "context_blend_weight": round(float(runtime.context_blend_weight), 4),
                            "baseline_home_win_prob": round(float(deterministic_baseline_probabilities[0]), 6),
                            "baseline_draw_prob": round(float(deterministic_baseline_probabilities[1]), 6),
                            "baseline_away_win_prob": round(float(deterministic_baseline_probabilities[2]), 6),
                        }
                        if calibration_applied and runtime.model_family == "history_core_plus_context_blend"
                        else {}
                    ),
                    **scoreline_feature_snapshot,
                },
                "feature_quality_status": row.match_feature_quality_status,
                "feature_missing_count": len(row.match_feature_missing_features or []),
                "feature_sources": self.feature_sources(row),
            }
        )
        baseline_prediction["key_factors"] = [
            *baseline_prediction["key_factors"],
            {
                "label": "model_mode",
                "value": 1 if calibration_applied else 0,
                "note": baseline_prediction["inference_mode"],
            },
            *scoreline_key_factors,
        ]
        if row.match_feature_quality_status == "insufficient":
            baseline_prediction["confidence"] = "low"
        return baseline_prediction

    def match_inputs(self, row) -> MatchInputs:
        return MatchInputs(
            home=TeamInputs(row.home_code, row.home_fifa_rank, float(row.home_elo_rating or 1800)),
            away=TeamInputs(row.away_code, row.away_fifa_rank, float(row.away_elo_rating or 1800)),
            neutral_site=row.neutral_site,
            source_confidence=float(row.source_confidence),
        )

    def feature_sources(self, row) -> list[str]:
        return (row.match_feature_source_summary or {}).get("sources", [])

    def write_match_prediction(self, match_id, snapshot_id, model_version_id, prediction: dict):
        probabilities = prediction["probabilities"]
        expected_goals = prediction["expected_goals"]
        match_prediction_id = self.db.execute(
            insert(match_predictions)
            .values(
                match_id=match_id,
                prediction_snapshot_id=snapshot_id,
                model_version_id=model_version_id,
                inference_mode=prediction.get("inference_mode", "baseline"),
                calibration_applied=prediction.get("calibration_applied", False),
                fallback_reason=prediction.get("fallback_reason"),
                base_probabilities=prediction.get("base_probabilities"),
                home_win_prob=probabilities["home_win"],
                draw_prob=probabilities["draw"],
                away_win_prob=probabilities["away_win"],
                home_expected_goals=expected_goals["home"],
                away_expected_goals=expected_goals["away"],
                confidence=prediction["confidence"],
                key_factors=prediction["key_factors"],
                feature_snapshot=prediction.get("feature_snapshot"),
                feature_quality_status=prediction.get("feature_quality_status"),
                feature_missing_count=prediction.get("feature_missing_count"),
                feature_sources=prediction.get("feature_sources") or [],
            )
            .returning(match_predictions.c.id)
        ).scalar_one()

        self.db.execute(
            insert(scoreline_predictions),
            [
                {
                    "match_prediction_id": match_prediction_id,
                    "home_goals": item["home_goals"],
                    "away_goals": item["away_goals"],
                    "probability": item["probability"],
                    "rank": item["rank"],
                }
                for item in prediction["scorelines"]
            ],
        )

    def write_rankings(self, snapshot_id) -> int:
        team_rows = self.db.execute(
            select(
                teams.c.id.label("team_id"),
                teams.c.code,
                teams.c.fifa_rank,
                teams.c.elo_rating,
                teams.c.market_value_eur,
                group_standings.c.rank.label("group_rank"),
                group_standings.c.points.label("group_points"),
                group_standings.c.played.label("group_played"),
                group_standings.c.goal_diff.label("group_goal_diff"),
                group_standings.c.goals_for.label("group_goals_for"),
            )
            .join(group_standings, group_standings.c.team_id == teams.c.id)
            .join(competition_stages, group_standings.c.stage_id == competition_stages.c.id)
            .where(competition_stages.c.code.in_(WORLD_CUP_GROUP_CODES))
        ).mappings().all()
        group_paths = {
            row["team_id"]: row
            for row in self.build_group_simulation_values(snapshot_id)
        }
        scored = [self.tournament_team_score(row, group_paths.get(row.team_id)) for row in team_rows]
        if not scored:
            return 0

        mean_score = sum(item["score"] for item in scored) / len(scored)
        champion_weights = [exp((item["score"] - mean_score) * 4.5) for item in scored]
        champion_total = sum(champion_weights) or 1
        for item, weight in zip(scored, champion_weights):
            item["champion_prob"] = weight / champion_total

        semifinal_weights = [item["champion_prob"] ** 0.62 for item in scored]
        semifinal_scale = 4.0 / (sum(semifinal_weights) or 1)
        for item, weight in zip(scored, semifinal_weights):
            item["semifinal_prob"] = min(weight * semifinal_scale, 0.85)

        ranked = sorted(scored, key=lambda item: item["champion_prob"], reverse=True)
        semifinal_ranked = sorted(scored, key=lambda item: item["semifinal_prob"], reverse=True)
        previous_champion = self.previous_ranking_probabilities("champion")
        previous_semifinal = self.previous_ranking_probabilities("semifinal")
        previous_darkhorse = self.previous_ranking_probabilities("darkhorse")
        rows = []
        for index, item in enumerate(ranked, start=1):
            probability = round(item["champion_prob"], 5)
            rows.append(
                {
                    "prediction_snapshot_id": snapshot_id,
                    "ranking_type": "champion",
                    "team_id": item["team_id"],
                    "probability": probability,
                    "delta": self.ranking_probability_delta(probability, previous_champion.get(item["team_id"])),
                    "rank": index,
                    "reason": "tournament_path_strength",
                }
            )
        for index, item in enumerate(semifinal_ranked, start=1):
            probability = round(item["semifinal_prob"], 5)
            rows.append(
                {
                    "prediction_snapshot_id": snapshot_id,
                    "ranking_type": "semifinal",
                    "team_id": item["team_id"],
                    "probability": probability,
                    "delta": self.ranking_probability_delta(probability, previous_semifinal.get(item["team_id"])),
                    "rank": index,
                    "reason": "tournament_path_strength",
                }
            )

        darkhorses = [item for item in scored if item["fifa_rank"] >= 10] or scored
        darkhorse_weights = [
            item["semifinal_prob"] * (1 + min(max(item["fifa_rank"] - 9, 0) / 30, 1.0))
            for item in darkhorses
        ]
        darkhorse_total = sum(darkhorse_weights) or 1
        darkhorse_ranked = sorted(
            [
                {
                    **item,
                    "darkhorse_prob": weight / darkhorse_total,
                }
                for item, weight in zip(darkhorses, darkhorse_weights)
            ],
            key=lambda item: item["darkhorse_prob"],
            reverse=True,
        )
        for index, item in enumerate(darkhorse_ranked[:10], start=1):
            probability = round(item["darkhorse_prob"], 5)
            rows.append(
                {
                    "prediction_snapshot_id": snapshot_id,
                    "ranking_type": "darkhorse",
                    "team_id": item["team_id"],
                    "probability": probability,
                    "delta": self.ranking_probability_delta(probability, previous_darkhorse.get(item["team_id"])),
                    "rank": index,
                    "reason": "darkhorse_upside",
                }
            )

        if rows:
            self.db.execute(insert(ranking_predictions), rows)
        return len(rows)

    @staticmethod
    def ranking_probability_delta(probability: float, previous_probability: float | None) -> float:
        if previous_probability is None:
            return 0.0
        return round(probability - previous_probability, 5)

    def previous_ranking_probabilities(self, ranking_type: str) -> dict[Any, float]:
        latest_snapshot = (
            select(prediction_snapshots.c.id.label("snapshot_id"))
            .join(ranking_predictions, ranking_predictions.c.prediction_snapshot_id == prediction_snapshots.c.id)
            .where(ranking_predictions.c.ranking_type == ranking_type)
            .order_by(desc(prediction_snapshots.c.generated_at))
            .limit(1)
            .subquery()
        )
        rows = self.db.execute(
            select(ranking_predictions.c.team_id, ranking_predictions.c.probability)
            .join(latest_snapshot, ranking_predictions.c.prediction_snapshot_id == latest_snapshot.c.snapshot_id)
            .where(ranking_predictions.c.ranking_type == ranking_type)
        ).mappings().all()
        return {row.team_id: float(row.probability) for row in rows}

    @staticmethod
    def tournament_team_score(row, group_path: dict[str, Any] | None = None) -> dict:
        fifa_rank = row.fifa_rank or 99
        group_rank = row.group_rank or 4
        group_points = row.group_points or 0
        group_played = row.group_played or 0
        group_goal_diff = row.group_goal_diff or 0
        group_goals_for = row.group_goals_for or 0
        market_value_eur = float(row.market_value_eur or 0)
        base_score = team_strength_score(TeamInputs(row.code, row.fifa_rank, float(row.elo_rating or 1800)))
        market_component = min(market_value_eur / 1_000_000_000, 1.2) * 0.2
        group_component = max(0, 5 - group_rank) * 0.03 + group_points * 0.015
        live_form_component = 0.0
        if group_played > 0:
            live_form_component = min(max(group_goal_diff / group_played, -2.0), 3.0) * 0.012
            live_form_component += min(group_goals_for / group_played, 4.0) * 0.004
        path_component = 0.0
        if group_path:
            qualify_prob = float(group_path.get("qualify_prob") or 0.0)
            rank_1_prob = float(group_path.get("rank_1_prob") or 0.0)
            expected_points = float(group_path.get("expected_points") or group_points)
            path_component = (qualify_prob - 0.5) * 0.32
            path_component += rank_1_prob * 0.16
            path_component += min(max(expected_points - group_points, 0.0), 3.0) * 0.01
        return {
            "team_id": row.team_id,
            "score": base_score + market_component + group_component + live_form_component + path_component,
            "fifa_rank": fifa_rank,
        }

    def write_group_simulations(self, snapshot_id) -> int:
        values = self.build_group_simulation_values(snapshot_id)
        if not values:
            return 0
        self.db.execute(insert(group_simulations), values)
        return len(values)

    def build_group_simulation_values(self, snapshot_id) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(
                competition_stages.c.id.label("stage_id"),
                group_standings.c.team_id,
                group_standings.c.rank,
                group_standings.c.played,
                group_standings.c.points,
                group_standings.c.goal_diff,
                group_standings.c.goals_for,
            )
            .join(group_standings, group_standings.c.stage_id == competition_stages.c.id)
            .where(competition_stages.c.stage_type == "group")
            .order_by(competition_stages.c.code.asc(), group_standings.c.rank.asc())
        ).mappings().all()
        if not rows:
            return []

        grouped: dict[object, list] = {}
        for row in rows:
            grouped.setdefault(row.stage_id, []).append(row)

        group_states_by_stage: dict[Any, list[tuple[float, list[dict[str, Any]]]]] = {}
        for stage_id, stage_rows in grouped.items():
            team_ids = [row.team_id for row in stage_rows]
            remaining_matches = self.load_group_remaining_matches(stage_id, team_ids, snapshot_id)
            group_states_by_stage[stage_id] = enumerate_group_table_states(stage_rows, remaining_matches)

        third_place_qualifiers = third_place_state_qualifying_probabilities(group_states_by_stage)
        values: list[dict[str, Any]] = []
        for stage_id, stage_rows in grouped.items():
            simulation = aggregate_group_simulation(
                stage_rows,
                group_states_by_stage[stage_id],
                {
                    state_index: probability
                    for (qualifier_stage_id, state_index), probability in third_place_qualifiers.items()
                    if qualifier_stage_id == stage_id
                },
            )
            for row in stage_rows:
                team_simulation = simulation[row.team_id]
                values.append(
                    {
                        "stage_id": stage_id,
                        "prediction_snapshot_id": snapshot_id,
                        "team_id": row.team_id,
                        "rank_1_prob": team_simulation["rank_1_prob"],
                        "rank_2_prob": team_simulation["rank_2_prob"],
                        "qualify_prob": team_simulation["qualify_prob"],
                        "expected_points": team_simulation["expected_points"],
                    }
                )
        return values

    def load_group_remaining_matches(self, stage_id, team_ids: list[Any], snapshot_id) -> list[dict[str, Any]]:
        if not team_ids:
            return []
        rows = self.db.execute(
            select(
                matches.c.home_team_id,
                matches.c.away_team_id,
                matches.c.status,
                match_predictions.c.home_win_prob,
                match_predictions.c.draw_prob,
                match_predictions.c.away_win_prob,
                match_predictions.c.home_expected_goals,
                match_predictions.c.away_expected_goals,
            )
            .join(
                match_predictions,
                and_(
                    match_predictions.c.match_id == matches.c.id,
                    match_predictions.c.prediction_snapshot_id == snapshot_id,
                ),
            )
            .where(
                matches.c.home_team_id.in_(team_ids),
                matches.c.away_team_id.in_(team_ids),
                matches.c.status.in_(("scheduled", "live")),
            )
            .order_by(matches.c.kickoff_at.asc(), matches.c.public_id.asc())
        ).mappings().all()
        return [dict(row) for row in rows]


def normalize_probabilities(probabilities: list[float]) -> dict[str, float]:
    total = sum(probabilities) or 1.0
    normalized = [max(0.0, value / total) for value in probabilities]
    home = round(normalized[0], 5)
    draw = round(normalized[1], 5)
    away = round(1.0 - home - draw, 5)
    return {"home_win": home, "draw": draw, "away_win": away}


def group_sort_key(row: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        -float(row["points"]),
        -float(row["goal_diff"]),
        -float(row["goals_for"]),
        float(row.get("seed_rank") or 99),
    )


def probability_at_most_successes(probabilities: list[float], max_successes: int) -> float:
    if max_successes < 0:
        return 0.0
    if max_successes >= len(probabilities):
        return 1.0

    distribution = [1.0]
    for probability in probabilities:
        bounded_probability = min(max(float(probability), 0.0), 1.0)
        next_distribution = [0.0] * (len(distribution) + 1)
        for index, value in enumerate(distribution):
            next_distribution[index] += value * (1.0 - bounded_probability)
            next_distribution[index + 1] += value * bounded_probability
        distribution = next_distribution
    return sum(distribution[: max_successes + 1])


def group_match_outcomes(match_row: dict[str, Any]) -> list[dict[str, Any]]:
    home_xg = float(match_row.get("home_expected_goals") or 1.2)
    away_xg = float(match_row.get("away_expected_goals") or 1.2)
    draw_goals = max(0.0, (home_xg + away_xg) / 2.0)
    home_win_gd = max(1.0, home_xg - away_xg)
    away_win_gd = max(1.0, away_xg - home_xg)
    outcomes = [
        {
            "probability": float(match_row.get("home_win_prob") or 0.0),
            "home_points": 3,
            "away_points": 0,
            "home_goals_for": max(home_xg, away_xg + 1.0),
            "away_goals_for": max(0.0, max(home_xg, away_xg + 1.0) - home_win_gd),
            "home_goal_diff": home_win_gd,
            "away_goal_diff": -home_win_gd,
        },
        {
            "probability": float(match_row.get("draw_prob") or 0.0),
            "home_points": 1,
            "away_points": 1,
            "home_goals_for": draw_goals,
            "away_goals_for": draw_goals,
            "home_goal_diff": 0.0,
            "away_goal_diff": 0.0,
        },
        {
            "probability": float(match_row.get("away_win_prob") or 0.0),
            "home_points": 0,
            "away_points": 3,
            "home_goals_for": max(0.0, max(away_xg, home_xg + 1.0) - away_win_gd),
            "away_goals_for": max(away_xg, home_xg + 1.0),
            "home_goal_diff": -away_win_gd,
            "away_goal_diff": away_win_gd,
        },
    ]
    total = sum(max(0.0, item["probability"]) for item in outcomes)
    if total <= GROUP_SIMULATION_MIN_PROBABILITY:
        for item in outcomes:
            item["probability"] = 1.0 / len(outcomes)
    else:
        for item in outcomes:
            item["probability"] = max(0.0, item["probability"]) / total
    return outcomes


def enumerate_group_table_states(
    stage_rows: list[Any],
    remaining_matches: list[dict[str, Any]],
) -> list[tuple[float, list[dict[str, Any]]]]:
    base_table = {
        row.team_id: {
            "team_id": row.team_id,
            "seed_rank": int(row.rank or 99),
            "points": float(row.points or 0),
            "goal_diff": float(row.goal_diff or 0),
            "goals_for": float(row.goals_for or 0),
        }
        for row in stage_rows
    }
    states: list[tuple[float, dict[Any, dict[str, Any]]]] = [(1.0, base_table)]
    for match_row in remaining_matches:
        next_states: list[tuple[float, dict[Any, dict[str, Any]]]] = []
        home_team_id = match_row["home_team_id"]
        away_team_id = match_row["away_team_id"]
        if home_team_id not in base_table or away_team_id not in base_table:
            continue
        for probability, table in states:
            for outcome in group_match_outcomes(match_row):
                outcome_probability = probability * outcome["probability"]
                if outcome_probability <= GROUP_SIMULATION_MIN_PROBABILITY:
                    continue
                next_table = {team_id: dict(values) for team_id, values in table.items()}
                home = next_table[home_team_id]
                away = next_table[away_team_id]
                home["points"] += outcome["home_points"]
                away["points"] += outcome["away_points"]
                home["goal_diff"] += outcome["home_goal_diff"]
                away["goal_diff"] += outcome["away_goal_diff"]
                home["goals_for"] += outcome["home_goals_for"]
                away["goals_for"] += outcome["away_goals_for"]
                next_states.append((outcome_probability, next_table))
        states = next_states or states

    total_probability = sum(probability for probability, _table in states) or 1.0
    return [
        (probability / total_probability, sorted(table.values(), key=group_sort_key))
        for probability, table in states
    ]


def third_place_qualifying_probabilities(
    group_states_by_stage: dict[Any, list[tuple[float, list[dict[str, Any]]]]],
) -> dict[Any, float]:
    third_entries_by_stage: dict[Any, list[dict[str, Any]]] = {}
    for stage_id, states in group_states_by_stage.items():
        entries = []
        for probability, ranked in states:
            if len(ranked) <= WORLD_CUP_DIRECT_GROUP_QUALIFIERS:
                continue
            third_team = ranked[WORLD_CUP_DIRECT_GROUP_QUALIFIERS]
            entries.append(
                {
                    "team_id": third_team["team_id"],
                    "probability": probability,
                    "sort_key": group_sort_key(third_team),
                }
            )
        third_entries_by_stage[stage_id] = entries

    max_better_third_teams = WORLD_CUP_THIRD_PLACE_QUALIFIERS - 1
    probabilities_by_team: dict[Any, float] = {}
    for stage_id, entries in third_entries_by_stage.items():
        other_stage_entries = [
            other_entries
            for other_stage_id, other_entries in third_entries_by_stage.items()
            if other_stage_id != stage_id
        ]
        for candidate in entries:
            better_probabilities = [
                sum(
                    other_entry["probability"]
                    for other_entry in other_entries
                    if other_entry["sort_key"] < candidate["sort_key"]
                )
                for other_entries in other_stage_entries
            ]
            qualify_given_candidate = probability_at_most_successes(
                better_probabilities,
                max_better_third_teams,
            )
            probabilities_by_team[candidate["team_id"]] = probabilities_by_team.get(candidate["team_id"], 0.0) + (
                candidate["probability"] * qualify_given_candidate
            )
    return probabilities_by_team


def third_place_state_qualify_probability(
    group_states_by_stage: dict[Any, list[tuple[float, list[dict[str, Any]]]]],
    stage_id: Any,
    candidate_key: tuple[float, float, float, float],
) -> float:
    better_probabilities = []
    for other_stage_id, other_states in group_states_by_stage.items():
        if other_stage_id == stage_id:
            continue
        better_probability = 0.0
        for probability, ranked in other_states:
            if len(ranked) <= WORLD_CUP_DIRECT_GROUP_QUALIFIERS:
                continue
            other_third = ranked[WORLD_CUP_DIRECT_GROUP_QUALIFIERS]
            if group_sort_key(other_third) < candidate_key:
                better_probability += probability
        better_probabilities.append(better_probability)
    return probability_at_most_successes(better_probabilities, WORLD_CUP_THIRD_PLACE_QUALIFIERS - 1)


def third_place_state_qualifying_probabilities(
    group_states_by_stage: dict[Any, list[tuple[float, list[dict[str, Any]]]]],
) -> dict[tuple[Any, int], float]:
    probabilities: dict[tuple[Any, int], float] = {}
    for stage_id, states in group_states_by_stage.items():
        for state_index, (_probability, ranked) in enumerate(states):
            if len(ranked) <= WORLD_CUP_DIRECT_GROUP_QUALIFIERS:
                probabilities[(stage_id, state_index)] = 0.0
                continue
            third_team = ranked[WORLD_CUP_DIRECT_GROUP_QUALIFIERS]
            probabilities[(stage_id, state_index)] = third_place_state_qualify_probability(
                group_states_by_stage,
                stage_id,
                group_sort_key(third_team),
            )
    return probabilities


def aggregate_group_simulation(
    stage_rows: list[Any],
    group_states: list[tuple[float, list[dict[str, Any]]]],
    third_place_qualifiers: dict[int, float] | None = None,
) -> dict[Any, dict[str, float]]:
    accumulator = {
        row.team_id: {
            "rank_1_prob": 0.0,
            "rank_2_prob": 0.0,
            "qualify_prob": 0.0,
            "expected_points": 0.0,
        }
        for row in stage_rows
    }

    for state_index, (normalized_probability, ranked) in enumerate(group_states):
        rank_3_team_id = None
        if len(ranked) > WORLD_CUP_DIRECT_GROUP_QUALIFIERS:
            rank_3_team_id = ranked[WORLD_CUP_DIRECT_GROUP_QUALIFIERS]["team_id"]
            rank_3_qualify_probability = (third_place_qualifiers or {}).get(state_index, 0.0)
        else:
            rank_3_qualify_probability = 0.0
        for index, team_row in enumerate(ranked, start=1):
            team_id = team_row["team_id"]
            accumulator[team_id]["expected_points"] += normalized_probability * float(team_row["points"])
            if index == 1:
                accumulator[team_id]["rank_1_prob"] += normalized_probability
                accumulator[team_id]["qualify_prob"] += normalized_probability
            elif index == 2:
                accumulator[team_id]["rank_2_prob"] += normalized_probability
                accumulator[team_id]["qualify_prob"] += normalized_probability
            elif index == 3 and team_id == rank_3_team_id:
                accumulator[team_id]["qualify_prob"] += normalized_probability * rank_3_qualify_probability

    return {
        team_id: {
            "rank_1_prob": round(values["rank_1_prob"], 5),
            "rank_2_prob": round(values["rank_2_prob"], 5),
            "qualify_prob": round(values["qualify_prob"], 5),
            "expected_points": round(values["expected_points"], 2),
        }
        for team_id, values in accumulator.items()
    }


def simulate_group_table(
    stage_rows: list[Any],
    remaining_matches: list[dict[str, Any]],
    third_place_qualifiers: dict[Any, float] | None = None,
) -> dict[Any, dict[str, float]]:
    return aggregate_group_simulation(
        stage_rows,
        enumerate_group_table_states(stage_rows, remaining_matches),
        third_place_qualifiers,
    )
