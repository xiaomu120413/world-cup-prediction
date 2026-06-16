from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import date, datetime
from math import exp, log, log1p, sqrt
from random import Random
from typing import Any

LABELS = ("home_win", "draw", "away_win")

FEATURE_NAMES = (
    "elo_diff",
    "recent10_ppg_diff",
    "recent10_goal_diff_diff",
    "recent20_ppg_diff",
    "recent20_goal_diff_diff",
    "recent10_goals_for_diff",
    "recent10_goals_against_diff",
    "experience_log_diff",
    "rest_days_diff",
    "neutral_site",
    "is_world_cup",
    "is_qualifier",
    "is_friendly",
)


@dataclass(frozen=True)
class HistoricalMatch:
    match_id: str
    played_at: datetime
    home_team_id: str
    away_team_id: str
    home_team_code: str
    away_team_code: str
    home_score: int
    away_score: int
    tournament: str
    neutral: bool


@dataclass(frozen=True)
class TrainingExample:
    match_id: str
    played_at: datetime
    home_team_code: str
    away_team_code: str
    label: int
    features: dict[str, float]
    home_team_id: str | None = None
    away_team_id: str | None = None


@dataclass
class TeamState:
    elo: float = 1500.0
    matches: int = 0
    last_played_at: datetime | None = None
    recent: deque[tuple[int, int, int, datetime]] = field(default_factory=lambda: deque(maxlen=30))

    def rest_days(self, current: datetime) -> float:
        if self.last_played_at is None:
            return 30.0
        return max(0.0, min(60.0, float((current.date() - self.last_played_at.date()).days)))

    def summary(self, window: int) -> dict[str, float]:
        rows = list(self.recent)[-window:]
        if not rows:
            return {
                "ppg": 1.0,
                "goals_for": 1.25,
                "goals_against": 1.25,
                "goal_diff": 0.0,
            }
        count = len(rows)
        points = sum(row[0] for row in rows)
        goals_for = sum(row[1] for row in rows)
        goals_against = sum(row[2] for row in rows)
        return {
            "ppg": points / count,
            "goals_for": goals_for / count,
            "goals_against": goals_against / count,
            "goal_diff": (goals_for - goals_against) / count,
        }


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def label_for(home_score: int, away_score: int) -> int:
    if home_score > away_score:
        return 0
    if home_score == away_score:
        return 1
    return 2


def points_for(goals_for: int, goals_against: int) -> int:
    if goals_for > goals_against:
        return 3
    if goals_for == goals_against:
        return 1
    return 0


def tournament_flags(tournament: str) -> dict[str, float]:
    normalized = tournament.lower()
    return {
        "is_world_cup": 1.0 if "world cup" in normalized and "qualification" not in normalized else 0.0,
        "is_qualifier": 1.0 if "qualification" in normalized or "qualifier" in normalized else 0.0,
        "is_friendly": 1.0 if "friendly" in normalized else 0.0,
    }


def feature_dict(
    home: TeamState,
    away: TeamState,
    played_at: datetime,
    neutral: bool,
    tournament: str,
) -> dict[str, float]:
    home10 = home.summary(10)
    away10 = away.summary(10)
    home20 = home.summary(20)
    away20 = away.summary(20)
    values = {
        "elo_diff": (home.elo - away.elo) / 400.0,
        "recent10_ppg_diff": home10["ppg"] - away10["ppg"],
        "recent10_goal_diff_diff": home10["goal_diff"] - away10["goal_diff"],
        "recent20_ppg_diff": home20["ppg"] - away20["ppg"],
        "recent20_goal_diff_diff": home20["goal_diff"] - away20["goal_diff"],
        "recent10_goals_for_diff": home10["goals_for"] - away10["goals_for"],
        "recent10_goals_against_diff": home10["goals_against"] - away10["goals_against"],
        "experience_log_diff": log1p(home.matches) - log1p(away.matches),
        "rest_days_diff": (home.rest_days(played_at) - away.rest_days(played_at)) / 30.0,
        "neutral_site": 1.0 if neutral else 0.0,
    }
    values.update(tournament_flags(tournament))
    return values


def update_states(home: TeamState, away: TeamState, match: HistoricalMatch) -> None:
    home_advantage = 0.0 if match.neutral else 60.0
    elo_diff = home.elo - away.elo + home_advantage
    expected_home = 1.0 / (1.0 + 10 ** (-elo_diff / 400.0))
    actual_home = 1.0 if match.home_score > match.away_score else 0.5 if match.home_score == match.away_score else 0.0
    goal_margin = abs(match.home_score - match.away_score)
    margin_multiplier = 1.0 + log(goal_margin + 1.0) / 2.0
    k = 34.0 if tournament_flags(match.tournament)["is_world_cup"] else 28.0
    delta = k * margin_multiplier * (actual_home - expected_home)
    home.elo += delta
    away.elo -= delta

    home.recent.append((points_for(match.home_score, match.away_score), match.home_score, match.away_score, match.played_at))
    away.recent.append((points_for(match.away_score, match.home_score), match.away_score, match.home_score, match.played_at))
    home.matches += 1
    away.matches += 1
    home.last_played_at = match.played_at
    away.last_played_at = match.played_at


def build_examples(
    matches: list[HistoricalMatch],
    min_prior_matches: int = 5,
) -> tuple[list[TrainingExample], dict[str, TeamState]]:
    states: dict[str, TeamState] = {}
    examples: list[TrainingExample] = []
    ordered = sorted(matches, key=lambda item: (item.played_at, item.match_id))
    for match in ordered:
        home = states.setdefault(match.home_team_id, TeamState())
        away = states.setdefault(match.away_team_id, TeamState())
        if home.matches >= min_prior_matches and away.matches >= min_prior_matches:
            examples.append(
                TrainingExample(
                    match_id=match.match_id,
                    played_at=match.played_at,
                    home_team_code=match.home_team_code,
                    away_team_code=match.away_team_code,
                    label=label_for(match.home_score, match.away_score),
                    features=feature_dict(home, away, match.played_at, match.neutral, match.tournament),
                    home_team_id=match.home_team_id,
                    away_team_id=match.away_team_id,
                )
            )
        update_states(home, away, match)
    return examples, states


@dataclass
class Standardizer:
    means: dict[str, float]
    stds: dict[str, float]
    feature_names: tuple[str, ...] = FEATURE_NAMES

    @classmethod
    def fit(cls, examples: list[TrainingExample], feature_names: tuple[str, ...] = FEATURE_NAMES) -> "Standardizer":
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

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Standardizer":
        feature_names = tuple(payload.get("feature_names") or FEATURE_NAMES)
        return cls(
            means={name: float(value) for name, value in payload["means"].items()},
            stds={name: float(value) for name, value in payload["stds"].items()},
            feature_names=feature_names,
        )


@dataclass
class SmallOutcomeModel:
    standardizer: Standardizer
    weights: list[list[float]]
    labels: tuple[str, ...] = LABELS
    feature_names: tuple[str, ...] = FEATURE_NAMES

    def predict_proba(self, features: dict[str, float]) -> list[float]:
        x = [1.0, *self.standardizer.transform(features)]
        scores = [sum(weight * value for weight, value in zip(row, x)) for row in self.weights]
        return softmax(scores)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_type": "multinomial_logistic_regression_sgd",
            "labels": list(self.labels),
            "feature_names": list(self.feature_names),
            "standardizer": {
                "means": self.standardizer.means,
                "stds": self.standardizer.stds,
                "feature_names": list(self.standardizer.feature_names),
            },
            "weights": self.weights,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SmallOutcomeModel":
        feature_names = tuple(payload.get("feature_names") or FEATURE_NAMES)
        return cls(
            standardizer=Standardizer.from_dict(payload["standardizer"]),
            weights=[[float(value) for value in row] for row in payload["weights"]],
            labels=tuple(payload.get("labels") or LABELS),
            feature_names=feature_names,
        )


def softmax(scores: list[float]) -> list[float]:
    max_score = max(scores)
    exps = [exp(score - max_score) for score in scores]
    total = sum(exps) or 1.0
    return [value / total for value in exps]


def train_multinomial_logistic(
    train_examples: list[TrainingExample],
    epochs: int = 35,
    learning_rate: float = 0.025,
    l2: float = 0.0008,
    seed: int = 20260615,
    feature_names: tuple[str, ...] = FEATURE_NAMES,
) -> SmallOutcomeModel:
    standardizer = Standardizer.fit(train_examples, feature_names=feature_names)
    feature_count = len(feature_names) + 1
    label_counts = [1, 1, 1]
    for example in train_examples:
        label_counts[example.label] += 1
    total = sum(label_counts)
    weights = [[0.0 for _ in range(feature_count)] for _ in LABELS]
    for label_index, count in enumerate(label_counts):
        weights[label_index][0] = log(count / total)

    rng = Random(seed)
    indices = list(range(len(train_examples)))
    for epoch in range(epochs):
        rng.shuffle(indices)
        lr = learning_rate / (1.0 + epoch * 0.08)
        for index in indices:
            example = train_examples[index]
            x = [1.0, *standardizer.transform(example.features)]
            probabilities = softmax([sum(w * v for w, v in zip(row, x)) for row in weights])
            for label_index in range(len(LABELS)):
                target = 1.0 if example.label == label_index else 0.0
                gradient_scale = probabilities[label_index] - target
                for feature_index, value in enumerate(x):
                    regularization = 0.0 if feature_index == 0 else l2 * weights[label_index][feature_index]
                    weights[label_index][feature_index] -= lr * (gradient_scale * value + regularization)
    return SmallOutcomeModel(standardizer=standardizer, weights=weights, feature_names=feature_names)


def baseline_probabilities(example: TrainingExample) -> list[float]:
    elo_diff = example.features["elo_diff"] * 400.0
    if example.features["neutral_site"] < 0.5:
        elo_diff += 60.0
    home_share = 1.0 / (1.0 + exp(-elo_diff / 280.0))
    draw = clamp(0.27 - min(abs(elo_diff), 360.0) / 3600.0, 0.17, 0.29)
    home = (1.0 - draw) * home_share
    away = 1.0 - draw - home
    return [home, draw, away]


def class_prior_probabilities(train_examples: list[TrainingExample]) -> list[float]:
    counts = [1, 1, 1]
    for example in train_examples:
        counts[example.label] += 1
    total = sum(counts)
    return [count / total for count in counts]


def evaluate_probabilities(examples: list[TrainingExample], probabilities: list[list[float]]) -> dict[str, Any]:
    eps = 1e-12
    log_loss = 0.0
    brier = 0.0
    correct = 0
    confusion = [[0, 0, 0] for _ in LABELS]
    for example, probs in zip(examples, probabilities):
        clipped = [clamp(value, eps, 1.0 - eps) for value in probs]
        total = sum(clipped)
        clipped = [value / total for value in clipped]
        log_loss -= log(clipped[example.label])
        brier += sum((clipped[index] - (1.0 if index == example.label else 0.0)) ** 2 for index in range(3))
        predicted = max(range(3), key=lambda index: clipped[index])
        if predicted == example.label:
            correct += 1
        confusion[example.label][predicted] += 1
    total_examples = len(examples) or 1
    return {
        "examples": len(examples),
        "log_loss": round(log_loss / total_examples, 6),
        "brier": round(brier / total_examples, 6),
        "accuracy": round(correct / total_examples, 6),
        "confusion_matrix": confusion,
        "labels": list(LABELS),
    }


def evaluate_model(model: SmallOutcomeModel, examples: list[TrainingExample]) -> dict[str, Any]:
    return evaluate_probabilities(examples, [model.predict_proba(example.features) for example in examples])


def evaluate_baseline(examples: list[TrainingExample]) -> dict[str, Any]:
    return evaluate_probabilities(examples, [baseline_probabilities(example) for example in examples])


def evaluate_prior(train_examples: list[TrainingExample], examples: list[TrainingExample]) -> dict[str, Any]:
    prior = class_prior_probabilities(train_examples)
    return evaluate_probabilities(examples, [prior for _ in examples])
