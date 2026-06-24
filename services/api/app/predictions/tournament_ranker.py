from __future__ import annotations

from dataclasses import dataclass
from math import exp, log, log1p
from random import Random
from typing import Any

from app.predictions.baseline import MatchInputs, TeamInputs, build_match_prediction


@dataclass(frozen=True)
class TournamentRankingParams:
    version: str
    group_points_weight: float
    live_goal_diff_per_match_weight: float
    live_goals_for_per_match_weight: float
    qualify_probability_weight: float
    rank1_probability_weight: float
    expected_points_delta_weight: float
    champion_softmax_scale: float
    semifinal_exponent: float
    semifinal_probability_cap: float
    darkhorse_favorite_cutoff: int
    darkhorse_depth_scale: float
    darkhorse_rank_bonus: float
    knockout_market_log_weight: float
    knockout_points_per_match_weight: float
    knockout_goal_diff_per_match_weight: float
    knockout_goals_for_per_match_weight: float
    knockout_adjustment_logit_cap: float
    training_source: str


DEFAULT_TOURNAMENT_RANKING_PARAMS = TournamentRankingParams(
    version="tournament_ranker_2026_06_24_world_cup_backtest_context_v2",
    group_points_weight=0.02,
    live_goal_diff_per_match_weight=0.0,
    live_goals_for_per_match_weight=0.0,
    qualify_probability_weight=0.18,
    rank1_probability_weight=0.08,
    expected_points_delta_weight=0.02,
    champion_softmax_scale=14.0,
    semifinal_exponent=0.9,
    semifinal_probability_cap=0.92,
    darkhorse_favorite_cutoff=10,
    darkhorse_depth_scale=20.0,
    darkhorse_rank_bonus=0.25,
    knockout_market_log_weight=0.08,
    knockout_points_per_match_weight=0.16,
    knockout_goal_diff_per_match_weight=0.08,
    knockout_goals_for_per_match_weight=0.03,
    knockout_adjustment_logit_cap=0.75,
    training_source=(
        "FIFA World Cup 1954-2022 backtest plus current tournament context controls; "
        "run scripts/train_tournament_ranker.py to regenerate."
    ),
)

ROUND_OF_32_MATCHES = (
    ("M73", "2A", "2B"),
    ("M74", "1E", "3"),
    ("M75", "1F", "2C"),
    ("M76", "1C", "2F"),
    ("M77", "1I", "3"),
    ("M78", "2E", "2I"),
    ("M79", "1A", "3"),
    ("M80", "1L", "3"),
    ("M81", "1D", "3"),
    ("M82", "1G", "3"),
    ("M83", "2K", "2L"),
    ("M84", "1H", "2J"),
    ("M85", "1B", "3"),
    ("M86", "1J", "2H"),
    ("M87", "1K", "3"),
    ("M88", "2D", "2G"),
)

THIRD_PLACE_ALLOWED_GROUPS = {
    "M74": set("ABCDF"),
    "M77": set("CDFGH"),
    "M79": set("CEFHI"),
    "M80": set("EHIJK"),
    "M81": set("BEFIJ"),
    "M82": set("AEHIJ"),
    "M85": set("EFGIJ"),
    "M87": set("DEIJL"),
}

ROUND_OF_16_MATCHES = (
    ("M89", "M74", "M77"),
    ("M90", "M73", "M75"),
    ("M91", "M76", "M78"),
    ("M92", "M79", "M80"),
    ("M93", "M83", "M84"),
    ("M94", "M81", "M82"),
    ("M95", "M86", "M88"),
    ("M96", "M85", "M87"),
)

QUARTER_FINAL_MATCHES = (
    ("M97", "M89", "M90"),
    ("M98", "M93", "M94"),
    ("M99", "M91", "M92"),
    ("M100", "M95", "M96"),
)

SEMI_FINAL_MATCHES = (
    ("M101", "M97", "M98"),
    ("M102", "M99", "M100"),
)

FINAL_MATCH = ("M103", "M101", "M102")

DEFAULT_MONTE_CARLO_ITERATIONS = 12000


def normalized_team_strength(row: Any) -> float:
    return float(getattr(row, "elo_rating", None) or 1800) / 2200.0


def tournament_team_score(
    row: Any,
    group_path: dict[str, Any] | None = None,
    params: TournamentRankingParams = DEFAULT_TOURNAMENT_RANKING_PARAMS,
) -> dict[str, Any]:
    fifa_rank = getattr(row, "fifa_rank", None) or 99
    group_points = float(getattr(row, "group_points", None) or 0.0)
    group_played = float(getattr(row, "group_played", None) or 0.0)
    group_goal_diff = float(getattr(row, "group_goal_diff", None) or 0.0)
    group_goals_for = float(getattr(row, "group_goals_for", None) or 0.0)

    score = normalized_team_strength(row)
    score += group_points * params.group_points_weight

    if group_played > 0:
        score += (group_goal_diff / group_played) * params.live_goal_diff_per_match_weight
        score += (group_goals_for / group_played) * params.live_goals_for_per_match_weight

    if group_path:
        qualify_prob = float(group_path.get("qualify_prob") or 0.0)
        rank_1_prob = float(group_path.get("rank_1_prob") or 0.0)
        expected_points = float(group_path.get("expected_points") or group_points)
        score += (qualify_prob - 0.5) * params.qualify_probability_weight
        score += rank_1_prob * params.rank1_probability_weight
        score += max(expected_points - group_points, 0.0) * params.expected_points_delta_weight

    return {
        "team_id": getattr(row, "team_id"),
        "score": score,
        "fifa_rank": fifa_rank,
        "ranking_param_version": params.version,
    }


def assign_tournament_probabilities(
    scored: list[dict[str, Any]],
    params: TournamentRankingParams = DEFAULT_TOURNAMENT_RANKING_PARAMS,
) -> list[dict[str, Any]]:
    if not scored:
        return []
    mean_score = sum(float(item["score"]) for item in scored) / len(scored)
    champion_weights = [
        exp((float(item["score"]) - mean_score) * params.champion_softmax_scale)
        for item in scored
    ]
    champion_total = sum(champion_weights) or 1.0
    for item, weight in zip(scored, champion_weights):
        item["champion_prob"] = weight / champion_total

    semifinal_weights = [float(item["champion_prob"]) ** params.semifinal_exponent for item in scored]
    semifinal_scale = 4.0 / (sum(semifinal_weights) or 1.0)
    for item, weight in zip(scored, semifinal_weights):
        item["semifinal_prob"] = min(weight * semifinal_scale, params.semifinal_probability_cap)
    return scored


def assign_darkhorse_probabilities(
    scored: list[dict[str, Any]],
    params: TournamentRankingParams = DEFAULT_TOURNAMENT_RANKING_PARAMS,
) -> list[dict[str, Any]]:
    ranked = sorted(scored, key=lambda item: float(item.get("champion_prob") or 0.0), reverse=True)
    rank_by_team = {item["team_id"]: index + 1 for index, item in enumerate(ranked)}
    candidates = [
        item
        for item in scored
        if rank_by_team.get(item["team_id"], 999) > params.darkhorse_favorite_cutoff
    ] or scored
    weights: list[float] = []
    for item in candidates:
        rank = rank_by_team.get(item["team_id"], params.darkhorse_favorite_cutoff + 1)
        depth = min(max(rank - params.darkhorse_favorite_cutoff, 0) / params.darkhorse_depth_scale, 1.0)
        weights.append(float(item.get("semifinal_prob") or 0.0) * (1.0 + params.darkhorse_rank_bonus * depth))
    total = sum(weights) or 1.0
    ranked_candidates = sorted(
        [
            {
                **item,
                "favorite_rank": rank_by_team.get(item["team_id"]),
                "darkhorse_prob": weight / total,
            }
            for item, weight in zip(candidates, weights)
        ],
        key=lambda item: item["darkhorse_prob"],
        reverse=True,
    )
    return ranked_candidates


def group_sort_key(row: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        -float(row["points"]),
        -float(row["goal_diff"]),
        -float(row["goals_for"]),
        float(row.get("seed_rank") or 99),
    )


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def logit(probability: float) -> float:
    bounded = clamp(float(probability), 0.01, 0.99)
    return log(bounded / (1.0 - bounded))


def logistic(value: float) -> float:
    return 1.0 / (1.0 + exp(-value))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def tournament_form_features(team: Any) -> dict[str, float]:
    played = max(safe_float(getattr(team, "group_played", 0)), 1.0)
    return {
        "points_per_match": safe_float(getattr(team, "group_points", 0)) / played,
        "goal_diff_per_match": safe_float(getattr(team, "group_goal_diff", 0)) / played,
        "goals_for_per_match": safe_float(getattr(team, "group_goals_for", 0)) / played,
    }


def knockout_context_logit_adjustment(
    team_a: Any,
    team_b: Any,
    params: TournamentRankingParams = DEFAULT_TOURNAMENT_RANKING_PARAMS,
) -> float:
    market_a = max(safe_float(getattr(team_a, "market_value_eur", 0)), 0.0)
    market_b = max(safe_float(getattr(team_b, "market_value_eur", 0)), 0.0)
    market_edge = log1p(market_a) - log1p(market_b)
    form_a = tournament_form_features(team_a)
    form_b = tournament_form_features(team_b)
    adjustment = market_edge * params.knockout_market_log_weight
    adjustment += (form_a["points_per_match"] - form_b["points_per_match"]) * params.knockout_points_per_match_weight
    adjustment += (form_a["goal_diff_per_match"] - form_b["goal_diff_per_match"]) * params.knockout_goal_diff_per_match_weight
    adjustment += (form_a["goals_for_per_match"] - form_b["goals_for_per_match"]) * params.knockout_goals_for_per_match_weight
    return clamp(adjustment, -params.knockout_adjustment_logit_cap, params.knockout_adjustment_logit_cap)


def weighted_choice(items: list[tuple[float, Any]], rng: Random) -> Any:
    threshold = rng.random()
    cumulative = 0.0
    for probability, value in items:
        cumulative += max(0.0, float(probability))
        if threshold <= cumulative:
            return value
    return items[-1][1]


def third_place_assignment(qualified_groups: set[str]) -> dict[str, str] | None:
    remaining_slots = list(THIRD_PLACE_ALLOWED_GROUPS)

    def search(slots: list[str], groups: set[str], assignment: dict[str, str]) -> dict[str, str] | None:
        if not slots:
            return assignment if not groups else None
        slot = min(slots, key=lambda value: len(THIRD_PLACE_ALLOWED_GROUPS[value] & groups))
        candidates = sorted(THIRD_PLACE_ALLOWED_GROUPS[slot] & groups)
        if not candidates:
            return None
        next_slots = [value for value in slots if value != slot]
        for group_code in candidates:
            result = search(next_slots, groups - {group_code}, {**assignment, slot: group_code})
            if result is not None:
                return result
        return None

    return search(remaining_slots, set(qualified_groups), {})


def knockout_advancement_probability(
    team_a: Any,
    team_b: Any,
    params: TournamentRankingParams = DEFAULT_TOURNAMENT_RANKING_PARAMS,
) -> float:
    prediction = build_match_prediction(
        MatchInputs(
            home=TeamInputs(team_a.code, team_a.fifa_rank, float(team_a.elo_rating or 1800)),
            away=TeamInputs(team_b.code, team_b.fifa_rank, float(team_b.elo_rating or 1800)),
            neutral_site=True,
            source_confidence=1.0,
        )
    )
    probabilities = prediction["probabilities"]
    base_probability = float(probabilities["home_win"]) + float(probabilities["draw"]) / 2.0
    adjusted_probability = logistic(logit(base_probability) + knockout_context_logit_adjustment(team_a, team_b, params))
    return clamp(adjusted_probability, 0.03, 0.97)


def simulate_match(
    team_a_id: Any,
    team_b_id: Any,
    teams_by_id: dict[Any, Any],
    rng: Random,
    params: TournamentRankingParams,
) -> Any:
    if team_a_id == team_b_id:
        return team_a_id
    probability = knockout_advancement_probability(teams_by_id[team_a_id], teams_by_id[team_b_id], params)
    return team_a_id if rng.random() < probability else team_b_id


def build_round_of_32_pairings(positions: dict[str, Any], third_assignment: dict[str, str]) -> dict[str, tuple[Any, Any]] | None:
    pairings: dict[str, tuple[Any, Any]] = {}
    for match_code, token_a, token_b in ROUND_OF_32_MATCHES:
        if token_a == "3":
            group_a = third_assignment.get(match_code)
            team_a = positions.get(f"3{group_a}") if group_a else None
        else:
            team_a = positions.get(token_a)
        if token_b == "3":
            group_b = third_assignment.get(match_code)
            team_b = positions.get(f"3{group_b}") if group_b else None
        else:
            team_b = positions.get(token_b)
        if team_a is None or team_b is None:
            return None
        pairings[match_code] = (team_a, team_b)
    return pairings


def simulate_tournament_paths(
    group_state_distributions: dict[str, list[tuple[float, list[dict[str, Any]]]]],
    teams_by_id: dict[Any, Any],
    iterations: int = DEFAULT_MONTE_CARLO_ITERATIONS,
    seed: int = 20260624,
    params: TournamentRankingParams = DEFAULT_TOURNAMENT_RANKING_PARAMS,
) -> dict[str, Any]:
    rng = Random(seed)
    champion_counts = {team_id: 0 for team_id in teams_by_id}
    semifinal_counts = {team_id: 0 for team_id in teams_by_id}
    round32_counts = {team_id: 0 for team_id in teams_by_id}
    completed_iterations = 0

    for _index in range(iterations):
        positions: dict[str, Any] = {}
        third_candidates: list[dict[str, Any]] = []
        for group_code, states in sorted(group_state_distributions.items()):
            if not states:
                continue
            ranked = weighted_choice(states, rng)
            if len(ranked) < 3:
                continue
            positions[f"1{group_code}"] = ranked[0]["team_id"]
            positions[f"2{group_code}"] = ranked[1]["team_id"]
            third_candidates.append(
                {
                    **ranked[2],
                    "group_code": group_code,
                    "sort_key": group_sort_key(ranked[2]),
                }
            )

        if len(positions) < 24 or len(third_candidates) < 12:
            continue

        qualified_thirds = sorted(third_candidates, key=lambda item: item["sort_key"])[:8]
        qualified_third_groups = {item["group_code"] for item in qualified_thirds}
        for item in qualified_thirds:
            positions[f"3{item['group_code']}"] = item["team_id"]
        assignment = third_place_assignment(qualified_third_groups)
        if assignment is None:
            continue
        round32_pairings = build_round_of_32_pairings(positions, assignment)
        if round32_pairings is None:
            continue

        for team_id in positions.values():
            round32_counts[team_id] = round32_counts.get(team_id, 0) + 1

        winners: dict[str, Any] = {}
        for match_code, (team_a_id, team_b_id) in round32_pairings.items():
            winners[match_code] = simulate_match(team_a_id, team_b_id, teams_by_id, rng, params)
        for match_code, previous_a, previous_b in ROUND_OF_16_MATCHES:
            winners[match_code] = simulate_match(winners[previous_a], winners[previous_b], teams_by_id, rng, params)
        for match_code, previous_a, previous_b in QUARTER_FINAL_MATCHES:
            winners[match_code] = simulate_match(winners[previous_a], winners[previous_b], teams_by_id, rng, params)

        semifinalists = [winners[match_code] for match_code, _a, _b in QUARTER_FINAL_MATCHES]
        for team_id in semifinalists:
            semifinal_counts[team_id] = semifinal_counts.get(team_id, 0) + 1

        for match_code, previous_a, previous_b in SEMI_FINAL_MATCHES:
            winners[match_code] = simulate_match(winners[previous_a], winners[previous_b], teams_by_id, rng, params)
        final_code, previous_a, previous_b = FINAL_MATCH
        winners[final_code] = simulate_match(winners[previous_a], winners[previous_b], teams_by_id, rng, params)
        champion_counts[winners[final_code]] = champion_counts.get(winners[final_code], 0) + 1
        completed_iterations += 1

    denominator = max(completed_iterations, 1)
    return {
        "iterations": completed_iterations,
        "champion_probabilities": {
            team_id: count / denominator
            for team_id, count in champion_counts.items()
        },
        "semifinal_probabilities": {
            team_id: count / denominator
            for team_id, count in semifinal_counts.items()
        },
        "round32_probabilities": {
            team_id: count / denominator
            for team_id, count in round32_counts.items()
        },
    }
