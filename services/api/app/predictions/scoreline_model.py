from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import exp, log, log1p, sqrt
from random import Random
from typing import Any

from app.predictions.baseline import outcome_key, poisson_probability
from app.predictions.small_outcome_model import HistoricalMatch, TeamState, tournament_flags, update_states

SCORELINE_FEATURE_NAMES = (
    "elo_diff",
    "recent10_goals_for",
    "recent10_opp_goals_against",
    "recent10_goal_diff",
    "recent20_goals_for",
    "recent20_opp_goals_against",
    "recent20_goal_diff",
    "experience_log_diff",
    "rest_days_diff",
    "neutral_site",
    "home_side",
    "is_world_cup",
    "is_qualifier",
    "is_friendly",
)

DEFAULT_LOW_SCORE_CORRELATION = -0.08


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def numeric_value(values: dict[str, Any], key: str) -> float | None:
    value = values.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class GoalExample:
    match_id: str
    played_at: datetime
    team_code: str
    opponent_code: str
    target_goals: int
    features: dict[str, float]


@dataclass(frozen=True)
class ScorelineExample:
    match_id: str
    played_at: datetime
    home_features: dict[str, float]
    away_features: dict[str, float]
    home_score: int
    away_score: int


@dataclass(frozen=True)
class GoalStandardizer:
    means: dict[str, float]
    stds: dict[str, float]
    feature_names: tuple[str, ...] = SCORELINE_FEATURE_NAMES

    @classmethod
    def fit(
        cls,
        examples: list[GoalExample],
        feature_names: tuple[str, ...] = SCORELINE_FEATURE_NAMES,
    ) -> "GoalStandardizer":
        means: dict[str, float] = {}
        stds: dict[str, float] = {}
        for name in feature_names:
            values = [float(example.features.get(name, 0.0) or 0.0) for example in examples]
            mean = sum(values) / len(values)
            variance = sum((value - mean) ** 2 for value in values) / max(1, len(values) - 1)
            means[name] = mean
            stds[name] = sqrt(variance) or 1.0
        return cls(means=means, stds=stds, feature_names=feature_names)

    def transform(self, features: dict[str, float]) -> list[float]:
        return [
            (float(features.get(name, 0.0) or 0.0) - self.means[name]) / self.stds[name]
            for name in self.feature_names
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "means": self.means,
            "stds": self.stds,
            "feature_names": list(self.feature_names),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GoalStandardizer":
        feature_names = tuple(payload.get("feature_names") or SCORELINE_FEATURE_NAMES)
        return cls(
            means={name: float(value) for name, value in payload["means"].items()},
            stds={name: float(value) for name, value in payload["stds"].items()},
            feature_names=feature_names,
        )


@dataclass(frozen=True)
class PoissonGoalModel:
    standardizer: GoalStandardizer
    weights: list[float]
    feature_names: tuple[str, ...] = SCORELINE_FEATURE_NAMES
    low_score_correlation: float = DEFAULT_LOW_SCORE_CORRELATION

    def predict_goals(self, features: dict[str, float]) -> float:
        x = [1.0, *self.standardizer.transform(features)]
        linear = sum(weight * value for weight, value in zip(self.weights, x))
        return max(0.05, min(5.5, exp(max(-4.0, min(1.8, linear)))))

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_type": "poisson_goal_regression_sgd",
            "feature_names": list(self.feature_names),
            "standardizer": self.standardizer.to_dict(),
            "weights": self.weights,
            "low_score_correlation": self.low_score_correlation,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PoissonGoalModel":
        feature_names = tuple(payload.get("feature_names") or SCORELINE_FEATURE_NAMES)
        return cls(
            standardizer=GoalStandardizer.from_dict(payload["standardizer"]),
            weights=[float(value) for value in payload["weights"]],
            feature_names=feature_names,
            low_score_correlation=float(payload.get("low_score_correlation", DEFAULT_LOW_SCORE_CORRELATION)),
        )


def goal_feature_dict(
    scoring: TeamState,
    conceding: TeamState,
    played_at: datetime,
    neutral: bool,
    tournament: str,
    is_home: bool,
) -> dict[str, float]:
    scoring10 = scoring.summary(10)
    conceding10 = conceding.summary(10)
    scoring20 = scoring.summary(20)
    conceding20 = conceding.summary(20)
    values = {
        "elo_diff": (scoring.elo - conceding.elo) / 400.0,
        "recent10_goals_for": scoring10["goals_for"],
        "recent10_opp_goals_against": conceding10["goals_against"],
        "recent10_goal_diff": scoring10["goal_diff"] - conceding10["goal_diff"],
        "recent20_goals_for": scoring20["goals_for"],
        "recent20_opp_goals_against": conceding20["goals_against"],
        "recent20_goal_diff": scoring20["goal_diff"] - conceding20["goal_diff"],
        "experience_log_diff": log1p(scoring.matches) - log1p(conceding.matches),
        "rest_days_diff": (scoring.rest_days(played_at) - conceding.rest_days(played_at)) / 30.0,
        "neutral_site": 1.0 if neutral else 0.0,
        "home_side": 1.0 if is_home else 0.0,
    }
    values.update(tournament_flags(tournament))
    return values


def build_scoreline_examples(
    matches: list[HistoricalMatch],
    min_prior_matches: int = 5,
) -> tuple[list[GoalExample], list[ScorelineExample], dict[str, TeamState]]:
    states: dict[str, TeamState] = {}
    goal_examples: list[GoalExample] = []
    scoreline_examples: list[ScorelineExample] = []
    ordered = sorted(matches, key=lambda item: (item.played_at, item.match_id))
    for match in ordered:
        home = states.setdefault(match.home_team_id, TeamState())
        away = states.setdefault(match.away_team_id, TeamState())
        if home.matches >= min_prior_matches and away.matches >= min_prior_matches:
            home_features = goal_feature_dict(home, away, match.played_at, match.neutral, match.tournament, True)
            away_features = goal_feature_dict(away, home, match.played_at, match.neutral, match.tournament, False)
            goal_examples.append(
                GoalExample(
                    match_id=f"{match.match_id}:home",
                    played_at=match.played_at,
                    team_code=match.home_team_code,
                    opponent_code=match.away_team_code,
                    target_goals=match.home_score,
                    features=home_features,
                )
            )
            goal_examples.append(
                GoalExample(
                    match_id=f"{match.match_id}:away",
                    played_at=match.played_at,
                    team_code=match.away_team_code,
                    opponent_code=match.home_team_code,
                    target_goals=match.away_score,
                    features=away_features,
                )
            )
            scoreline_examples.append(
                ScorelineExample(
                    match_id=match.match_id,
                    played_at=match.played_at,
                    home_features=home_features,
                    away_features=away_features,
                    home_score=match.home_score,
                    away_score=match.away_score,
                )
            )
        update_states(home, away, match)
    return goal_examples, scoreline_examples, states


def split_examples_by_date(examples: list[Any], train_end: datetime, test_start: datetime) -> tuple[list[Any], list[Any]]:
    train = [example for example in examples if example.played_at < train_end]
    test = [example for example in examples if example.played_at >= test_start]
    return train, test


def train_poisson_goal_model(
    examples: list[GoalExample],
    epochs: int = 40,
    learning_rate: float = 0.01,
    l2: float = 0.0005,
    seed: int = 20260617,
    feature_names: tuple[str, ...] = SCORELINE_FEATURE_NAMES,
    low_score_correlation: float = DEFAULT_LOW_SCORE_CORRELATION,
) -> PoissonGoalModel:
    if not examples:
        raise ValueError("scoreline_model_unavailable:no_goal_examples")
    standardizer = GoalStandardizer.fit(examples, feature_names=feature_names)
    avg_goals = sum(example.target_goals for example in examples) / len(examples)
    weights = [log(max(0.2, avg_goals)), *[0.0 for _ in feature_names]]
    rng = Random(seed)
    rows = list(examples)
    for epoch in range(epochs):
        rng.shuffle(rows)
        step = learning_rate / (1.0 + epoch * 0.04)
        for example in rows:
            x = [1.0, *standardizer.transform(example.features)]
            linear = sum(weight * value for weight, value in zip(weights, x))
            expected = max(0.05, min(5.5, exp(max(-4.0, min(1.8, linear)))))
            error = expected - example.target_goals
            for index, value in enumerate(x):
                penalty = l2 * weights[index] if index else 0.0
                weights[index] -= step * (error * value + penalty)
    return PoissonGoalModel(
        standardizer=standardizer,
        weights=[round(float(value), 8) for value in weights],
        feature_names=feature_names,
        low_score_correlation=low_score_correlation,
    )


def dixon_coles_factor(home_goals: int, away_goals: int, home_xg: float, away_xg: float, rho: float) -> float:
    if home_goals == 0 and away_goals == 0:
        return 1.0 - home_xg * away_xg * rho
    if home_goals == 0 and away_goals == 1:
        return 1.0 + home_xg * rho
    if home_goals == 1 and away_goals == 0:
        return 1.0 + away_xg * rho
    if home_goals == 1 and away_goals == 1:
        return 1.0 - rho
    return 1.0


def scoreline_distribution(
    home_xg: float,
    away_xg: float,
    max_goals: int = 7,
    low_score_correlation: float = DEFAULT_LOW_SCORE_CORRELATION,
) -> list[dict]:
    scorelines = []
    for home_goals in range(max_goals + 1):
        home_probability = poisson_probability(home_xg, home_goals)
        for away_goals in range(max_goals + 1):
            probability = home_probability * poisson_probability(away_xg, away_goals)
            probability *= dixon_coles_factor(home_goals, away_goals, home_xg, away_xg, low_score_correlation)
            scorelines.append(
                {
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "probability": max(0.0, probability),
                }
            )
    total = sum(item["probability"] for item in scorelines) or 1.0
    normalized = [
        {
            **item,
            "probability": item["probability"] / total,
        }
        for item in scorelines
    ]
    normalized.sort(key=lambda item: item["probability"], reverse=True)
    return normalized


def outcome_probabilities_from_scorelines(scorelines: list[dict]) -> dict[str, float]:
    totals = {"home_win": 0.0, "draw": 0.0, "away_win": 0.0}
    for item in scorelines:
        totals[outcome_key(item["home_goals"], item["away_goals"])] += item["probability"]
    total = sum(totals.values()) or 1.0
    home = round(totals["home_win"] / total, 5)
    draw = round(totals["draw"] / total, 5)
    away = round(1.0 - home - draw, 5)
    return {"home_win": home, "draw": draw, "away_win": away}


def expected_goals_from_scorelines(scorelines: list[dict]) -> tuple[float, float]:
    total = sum(item["probability"] for item in scorelines) or 1.0
    home_xg = sum(item["home_goals"] * item["probability"] for item in scorelines) / total
    away_xg = sum(item["away_goals"] * item["probability"] for item in scorelines) / total
    return round(home_xg, 2), round(away_xg, 2)


def ranked_scorelines(scorelines: list[dict], limit: int = 4) -> list[dict]:
    return [
        {
            "home_goals": item["home_goals"],
            "away_goals": item["away_goals"],
            "probability": round(item["probability"], 5),
            "rank": index + 1,
        }
        for index, item in enumerate(scorelines[:limit])
    ]


def context_adjusted_expected_goals(
    home_xg: float,
    away_xg: float,
    numeric_features: dict[str, Any] | None,
) -> tuple[float, float, list[dict[str, float | str]]]:
    values = numeric_features or {}
    home_multiplier = 1.0
    away_multiplier = 1.0
    total_multiplier = 1.0
    adjustments: list[dict[str, float | str]] = []

    market_diff = numeric_value(values, "market_value_log_diff")
    if market_diff is not None:
        edge = clamp(market_diff * 0.035, -0.16, 0.16)
        home_multiplier *= 1.0 + edge
        away_multiplier *= 1.0 - edge
        adjustments.append(
            {
                "label": "context_market_value",
                "value": round(edge, 4),
                "note": "Market-value log edge applied to team scoring rates",
            }
        )

    goals_diff = numeric_value(values, "player_goals_per_player_diff")
    assists_diff = numeric_value(values, "player_assists_per_player_diff")
    if goals_diff is not None or assists_diff is not None:
        edge = clamp((goals_diff or 0.0) * 0.055 + (assists_diff or 0.0) * 0.035, -0.12, 0.12)
        home_multiplier *= 1.0 + edge
        away_multiplier *= 1.0 - edge
        adjustments.append(
            {
                "label": "context_roster_output",
                "value": round(edge, 4),
                "note": "Roster scoring and assist edge applied to scoring rates",
            }
        )

    home_availability = numeric_value(values, "home_availability_impact")
    away_availability = numeric_value(values, "away_availability_impact")
    if home_availability is not None:
        effect = clamp(home_availability * 0.08, -0.14, 0.08)
        home_multiplier *= 1.0 + effect
        adjustments.append(
            {
                "label": "context_home_availability",
                "value": round(effect, 4),
                "note": "Home injury/news availability impact applied to scoring rate",
            }
        )
    if away_availability is not None:
        effect = clamp(away_availability * 0.08, -0.14, 0.08)
        away_multiplier *= 1.0 + effect
        adjustments.append(
            {
                "label": "context_away_availability",
                "value": round(effect, 4),
                "note": "Away injury/news availability impact applied to scoring rate",
            }
        )

    home_unavailable = numeric_value(values, "home_player_unavailable_count")
    away_unavailable = numeric_value(values, "away_player_unavailable_count")
    if home_unavailable is not None and home_unavailable > 0:
        effect = -clamp(home_unavailable * 0.025, 0.0, 0.12)
        home_multiplier *= 1.0 + effect
        adjustments.append(
            {
                "label": "context_home_unavailable",
                "value": round(effect, 4),
                "note": "Home unavailable-player count applied to scoring rate",
            }
        )
    if away_unavailable is not None and away_unavailable > 0:
        effect = -clamp(away_unavailable * 0.025, 0.0, 0.12)
        away_multiplier *= 1.0 + effect
        adjustments.append(
            {
                "label": "context_away_unavailable",
                "value": round(effect, 4),
                "note": "Away unavailable-player count applied to scoring rate",
            }
        )

    wind_speed = numeric_value(values, "weather_wind_speed_kph")
    precipitation = numeric_value(values, "weather_precipitation_mm")
    temperature = numeric_value(values, "weather_temperature_c")
    weather_effect = 0.0
    if wind_speed is not None and wind_speed > 18:
        weather_effect -= clamp((wind_speed - 18) / 100, 0.0, 0.08)
    if precipitation is not None and precipitation > 0.5:
        weather_effect -= clamp(precipitation / 80, 0.0, 0.06)
    if temperature is not None:
        if temperature > 30:
            weather_effect -= clamp((temperature - 30) / 120, 0.0, 0.05)
        elif temperature < 5:
            weather_effect -= clamp((5 - temperature) / 120, 0.0, 0.05)
    if weather_effect:
        total_multiplier *= 1.0 + weather_effect
        adjustments.append(
            {
                "label": "context_weather_total",
                "value": round(weather_effect, 4),
                "note": "Weather drag applied to both teams' scoring rates",
            }
        )

    adjusted_home = clamp(home_xg * home_multiplier * total_multiplier, 0.05, 5.5)
    adjusted_away = clamp(away_xg * away_multiplier * total_multiplier, 0.05, 5.5)
    return adjusted_home, adjusted_away, adjustments


def evaluate_scoreline_model(model: PoissonGoalModel, examples: list[ScorelineExample]) -> dict[str, float | int]:
    if not examples:
        return {"examples": 0}
    log_loss = 0.0
    home_abs_error = 0.0
    away_abs_error = 0.0
    top1_hits = 0
    top4_hits = 0
    for example in examples:
        home_xg = model.predict_goals(example.home_features)
        away_xg = model.predict_goals(example.away_features)
        home_abs_error += abs(home_xg - example.home_score)
        away_abs_error += abs(away_xg - example.away_score)
        scorelines = scoreline_distribution(home_xg, away_xg, low_score_correlation=model.low_score_correlation)
        actual_probability = next(
            (
                item["probability"]
                for item in scorelines
                if item["home_goals"] == example.home_score and item["away_goals"] == example.away_score
            ),
            1e-9,
        )
        log_loss += -log(max(actual_probability, 1e-9))
        actual = (example.home_score, example.away_score)
        ranked = [(item["home_goals"], item["away_goals"]) for item in scorelines]
        if ranked and ranked[0] == actual:
            top1_hits += 1
        if actual in ranked[:4]:
            top4_hits += 1
    count = len(examples)
    return {
        "examples": count,
        "scoreline_log_loss": round(log_loss / count, 6),
        "home_goal_mae": round(home_abs_error / count, 6),
        "away_goal_mae": round(away_abs_error / count, 6),
        "top1_accuracy": round(top1_hits / count, 6),
        "top4_accuracy": round(top4_hits / count, 6),
    }
