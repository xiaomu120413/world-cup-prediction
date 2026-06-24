from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from math import exp, log
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.predictions.small_outcome_model import TeamState, update_states
from app.predictions.tournament_ranker import DEFAULT_TOURNAMENT_RANKING_PARAMS
from scripts.train_small_outcome_model import load_historical_matches

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "exports" / "tournament_ranker_latest.json"


def softmax_probabilities(rows: list[dict[str, Any]], scale: float) -> list[float]:
    mean_score = sum(float(row["score"]) for row in rows) / len(rows)
    weights = [exp((float(row["score"]) - mean_score) * scale) for row in rows]
    total = sum(weights) or 1.0
    return [weight / total for weight in weights]


def build_world_cup_backtest_examples(matches: list[Any], start_year: int, end_year: int) -> dict[int, list[dict[str, Any]]]:
    ordered = sorted(matches, key=lambda item: (item.played_at, item.match_id))
    states: dict[str, TeamState] = {}
    tournament_matches: dict[int, list[Any]] = defaultdict(list)
    pre_tournament: dict[tuple[int, str], dict[str, float]] = {}
    group_summary: dict[tuple[int, str], dict[str, float]] = defaultdict(
        lambda: {"played": 0, "points": 0, "goal_diff": 0, "goals_for": 0}
    )

    for match in ordered:
        is_training_world_cup = (
            match.tournament == "FIFA World Cup"
            and start_year <= match.played_at.year <= end_year
        )
        if is_training_world_cup:
            year = match.played_at.year
            tournament_matches[year].append(match)
            for team_id in (match.home_team_id, match.away_team_id):
                state = states.setdefault(team_id, TeamState())
                pre_tournament.setdefault((year, team_id), {"elo": state.elo})
            for team_id, goals_for, goals_against in (
                (match.home_team_id, match.home_score, match.away_score),
                (match.away_team_id, match.away_score, match.home_score),
            ):
                summary = group_summary[(year, team_id)]
                if summary["played"] < 3:
                    summary["played"] += 1
                    summary["goals_for"] += goals_for
                    summary["goal_diff"] += goals_for - goals_against
                    summary["points"] += 3 if goals_for > goals_against else 1 if goals_for == goals_against else 0

        home = states.setdefault(match.home_team_id, TeamState())
        away = states.setdefault(match.away_team_id, TeamState())
        update_states(home, away, match)

    examples_by_year: dict[int, list[dict[str, Any]]] = {}
    for year, rows in sorted(tournament_matches.items()):
        if len(rows) < 10:
            continue
        tournament_rows = sorted(rows, key=lambda item: (item.played_at, item.match_id))
        final = tournament_rows[-1]
        champion_team_id = final.home_team_id if final.home_score > final.away_score else final.away_team_id
        top4_team_ids = set()
        for match in tournament_rows[-2:]:
            top4_team_ids.update((match.home_team_id, match.away_team_id))

        year_examples: list[dict[str, Any]] = []
        team_ids = sorted({match.home_team_id for match in rows} | {match.away_team_id for match in rows})
        for team_id in team_ids:
            summary = group_summary[(year, team_id)]
            if summary["played"] < 2:
                continue
            pre = pre_tournament[(year, team_id)]
            played = float(summary["played"] or 1)
            year_examples.append(
                {
                    "year": year,
                    "team_id": team_id,
                    "champion": team_id == champion_team_id,
                    "top4": team_id in top4_team_ids,
                    "base_strength": pre["elo"] / 2200.0,
                    "group_points": float(summary["points"]),
                    "goal_diff_per_match": float(summary["goal_diff"]) / played,
                    "goals_for_per_match": float(summary["goals_for"]) / played,
                }
            )
        if year_examples:
            examples_by_year[year] = year_examples
    return examples_by_year


def score_rows(rows: list[dict[str, Any]], params: dict[str, float]) -> list[dict[str, Any]]:
    return [
        {
            **row,
            "score": row["base_strength"]
            + params["group_points_weight"] * row["group_points"]
            + params["goal_diff_per_match_weight"] * row["goal_diff_per_match"]
            + params["goals_for_per_match_weight"] * row["goals_for_per_match"],
        }
        for row in rows
    ]


def evaluate_champion_params(examples_by_year: dict[int, list[dict[str, Any]]], params: dict[str, float]) -> dict[str, float]:
    log_loss = 0.0
    brier = 0.0
    top1_hits = 0
    years = 0
    for rows in examples_by_year.values():
        scored = score_rows(rows, params)
        probabilities = softmax_probabilities(scored, params["champion_softmax_scale"])
        champion_index = next(index for index, row in enumerate(scored) if row["champion"])
        log_loss -= log(max(probabilities[champion_index], 1e-9))
        brier += sum((probabilities[index] - (1.0 if row["champion"] else 0.0)) ** 2 for index, row in enumerate(scored))
        top1_hits += 1 if max(range(len(probabilities)), key=lambda index: probabilities[index]) == champion_index else 0
        years += 1
    return {
        "years": years,
        "champion_log_loss": round(log_loss / max(years, 1), 6),
        "champion_brier": round(brier / max(years, 1), 6),
        "champion_top1_accuracy": round(top1_hits / max(years, 1), 6),
    }


def evaluate_semifinal_params(
    examples_by_year: dict[int, list[dict[str, Any]]],
    params: dict[str, float],
) -> dict[str, float]:
    log_loss = 0.0
    brier = 0.0
    top4_precision = 0.0
    rows_seen = 0
    years = 0
    for rows in examples_by_year.values():
        scored = score_rows(rows, params)
        champion_probs = softmax_probabilities(scored, params["champion_softmax_scale"])
        semifinal_weights = [probability ** params["semifinal_exponent"] for probability in champion_probs]
        semifinal_scale = 4.0 / (sum(semifinal_weights) or 1.0)
        semifinal_probs = [
            min(weight * semifinal_scale, DEFAULT_TOURNAMENT_RANKING_PARAMS.semifinal_probability_cap)
            for weight in semifinal_weights
        ]
        for index, row in enumerate(scored):
            target = 1.0 if row["top4"] else 0.0
            probability = min(max(semifinal_probs[index], 1e-9), 1.0 - 1e-9)
            log_loss -= target * log(probability) + (1.0 - target) * log(1.0 - probability)
            brier += (probability - target) ** 2
            rows_seen += 1
        top4_indexes = sorted(range(len(scored)), key=lambda index: semifinal_probs[index], reverse=True)[:4]
        top4_precision += len([index for index in top4_indexes if scored[index]["top4"]]) / 4.0
        years += 1
    return {
        "semifinal_log_loss": round(log_loss / max(rows_seen, 1), 6),
        "semifinal_brier": round(brier / max(rows_seen, 1), 6),
        "semifinal_top4_precision": round(top4_precision / max(years, 1), 6),
    }


def evaluate_darkhorse_bonus(
    examples_by_year: dict[int, list[dict[str, Any]]],
    params: dict[str, float],
    bonus: float,
) -> float:
    precision = 0.0
    years = 0
    for rows in examples_by_year.values():
        scored = score_rows(rows, params)
        champion_probs = softmax_probabilities(scored, params["champion_softmax_scale"])
        semifinal_weights = [probability ** params["semifinal_exponent"] for probability in champion_probs]
        semifinal_scale = 4.0 / (sum(semifinal_weights) or 1.0)
        semifinal_probs = [
            min(weight * semifinal_scale, DEFAULT_TOURNAMENT_RANKING_PARAMS.semifinal_probability_cap)
            for weight in semifinal_weights
        ]
        rank_order = sorted(range(len(scored)), key=lambda index: champion_probs[index], reverse=True)
        rank_by_index = {index: rank + 1 for rank, index in enumerate(rank_order)}
        pool = [
            index
            for index in range(len(scored))
            if rank_by_index[index] > DEFAULT_TOURNAMENT_RANKING_PARAMS.darkhorse_favorite_cutoff
        ]
        if not pool:
            continue
        darkhorse_scores = []
        for index in pool:
            depth = min(
                max(rank_by_index[index] - DEFAULT_TOURNAMENT_RANKING_PARAMS.darkhorse_favorite_cutoff, 0)
                / DEFAULT_TOURNAMENT_RANKING_PARAMS.darkhorse_depth_scale,
                1.0,
            )
            darkhorse_scores.append((index, semifinal_probs[index] * (1.0 + bonus * depth)))
        top_indexes = [index for index, _score in sorted(darkhorse_scores, key=lambda item: item[1], reverse=True)[:4]]
        precision += len([index for index in top_indexes if scored[index]["top4"]]) / 4.0
        years += 1
    return round(precision / max(years, 1), 6)


def search_params(examples_by_year: dict[int, list[dict[str, Any]]]) -> tuple[dict[str, float], dict[str, Any]]:
    candidates: list[tuple[dict[str, float], dict[str, float]]] = []
    for group_points_weight in (0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12):
        for goal_diff_per_match_weight in (0.0, 0.005, 0.01, 0.02, 0.03, 0.04, 0.06):
            for goals_for_per_match_weight in (0.0, 0.002, 0.004, 0.008, 0.012, 0.018):
                for champion_softmax_scale in (4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 24.0):
                    params = {
                        "group_points_weight": group_points_weight,
                        "goal_diff_per_match_weight": goal_diff_per_match_weight,
                        "goals_for_per_match_weight": goals_for_per_match_weight,
                        "champion_softmax_scale": champion_softmax_scale,
                    }
                    metrics = evaluate_champion_params(examples_by_year, params)
                    candidates.append((params, metrics))

    best_brier = min(metrics["champion_brier"] for _params, metrics in candidates)
    calibrated_candidates = [
        (params, metrics)
        for params, metrics in candidates
        if metrics["champion_brier"] <= best_brier + 0.005
    ]
    best_params, best_metrics = min(
        calibrated_candidates,
        key=lambda item: (
            item[0]["champion_softmax_scale"],
            item[1]["champion_log_loss"],
        ),
    )
    best_semifinal_exponent = 0.7
    best_semifinal_metrics: dict[str, float] | None = None
    for semifinal_exponent in (0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.80, 0.90, 1.0):
        params = {**best_params, "semifinal_exponent": semifinal_exponent}
        metrics = evaluate_semifinal_params(examples_by_year, params)
        if best_semifinal_metrics is None or metrics["semifinal_log_loss"] < best_semifinal_metrics["semifinal_log_loss"]:
            best_semifinal_exponent = semifinal_exponent
            best_semifinal_metrics = metrics

    params = {**best_params, "semifinal_exponent": best_semifinal_exponent}
    best_bonus = 0.0
    best_precision = -1.0
    for bonus in (0.0, 0.25, 0.50, 0.75, 1.0, 1.25, 1.5):
        precision = evaluate_darkhorse_bonus(examples_by_year, params, bonus)
        if precision > best_precision:
            best_bonus = bonus
            best_precision = precision

    fitted = {
        **params,
        "qualify_probability_weight": round(best_params["group_points_weight"] * 9.0, 6),
        "rank1_probability_weight": round(best_params["group_points_weight"] * 4.0, 6),
        "expected_points_delta_weight": best_params["group_points_weight"],
        "darkhorse_rank_bonus": best_bonus,
    }
    metrics = {
        "champion": best_metrics,
        "semifinal": best_semifinal_metrics,
        "darkhorse": {
            "darkhorse_top4_precision": best_precision,
        },
    }
    return fitted, metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Fit tournament ranking parameters from World Cup backtests.")
    parser.add_argument("--start-year", type=int, default=1954)
    parser.add_argument("--end-year", type=int, default=2022)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    with SessionLocal() as db:
        historical_matches = load_historical_matches(db)
    examples_by_year = build_world_cup_backtest_examples(historical_matches, args.start_year, args.end_year)
    params, metrics = search_params(examples_by_year)
    report = {
        "version": DEFAULT_TOURNAMENT_RANKING_PARAMS.version,
        "training_source": DEFAULT_TOURNAMENT_RANKING_PARAMS.training_source,
        "dataset": {
            "start_year": args.start_year,
            "end_year": args.end_year,
            "tournaments": len(examples_by_year),
            "team_examples": sum(len(rows) for rows in examples_by_year.values()),
            "years": sorted(examples_by_year),
        },
        "params": {
            **params,
            "semifinal_probability_cap": DEFAULT_TOURNAMENT_RANKING_PARAMS.semifinal_probability_cap,
            "darkhorse_favorite_cutoff": DEFAULT_TOURNAMENT_RANKING_PARAMS.darkhorse_favorite_cutoff,
            "darkhorse_depth_scale": DEFAULT_TOURNAMENT_RANKING_PARAMS.darkhorse_depth_scale,
            "knockout_market_log_weight": DEFAULT_TOURNAMENT_RANKING_PARAMS.knockout_market_log_weight,
            "knockout_points_per_match_weight": DEFAULT_TOURNAMENT_RANKING_PARAMS.knockout_points_per_match_weight,
            "knockout_goal_diff_per_match_weight": DEFAULT_TOURNAMENT_RANKING_PARAMS.knockout_goal_diff_per_match_weight,
            "knockout_goals_for_per_match_weight": DEFAULT_TOURNAMENT_RANKING_PARAMS.knockout_goals_for_per_match_weight,
            "knockout_adjustment_logit_cap": DEFAULT_TOURNAMENT_RANKING_PARAMS.knockout_adjustment_logit_cap,
        },
        "metrics": metrics,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), **report["dataset"], "params": report["params"], "metrics": metrics}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
