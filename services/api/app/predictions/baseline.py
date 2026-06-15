from __future__ import annotations

from dataclasses import dataclass
from math import exp, factorial


@dataclass(frozen=True)
class TeamInputs:
    code: str
    fifa_rank: int | None
    elo_rating: float | None


@dataclass(frozen=True)
class MatchInputs:
    home: TeamInputs
    away: TeamInputs
    neutral_site: bool = True
    source_confidence: float = 1.0


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def poisson_probability(expected_goals: float, goals: int) -> float:
    return (exp(-expected_goals) * expected_goals**goals) / factorial(goals)


def expected_goals(match: MatchInputs) -> tuple[float, float]:
    home_elo = match.home.elo_rating or 1800
    away_elo = match.away.elo_rating or 1800
    elo_diff = home_elo - away_elo

    home_rank = match.home.fifa_rank or 48
    away_rank = match.away.fifa_rank or 48
    rank_edge = clamp((away_rank - home_rank) / 80, -0.45, 0.45)
    home_field = 0.08 if not match.neutral_site else 0.0

    home_xg = 1.25 + elo_diff / 700 + rank_edge + home_field
    away_xg = 1.25 - elo_diff / 760 - rank_edge
    return round(clamp(home_xg, 0.25, 3.8), 2), round(clamp(away_xg, 0.25, 3.8), 2)


def scoreline_distribution(home_xg: float, away_xg: float, max_goals: int = 7) -> list[dict]:
    scorelines = []
    for home_goals in range(max_goals + 1):
        home_prob = poisson_probability(home_xg, home_goals)
        for away_goals in range(max_goals + 1):
            probability = home_prob * poisson_probability(away_xg, away_goals)
            scorelines.append(
                {
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "probability": probability,
                }
            )
    scorelines.sort(key=lambda item: item["probability"], reverse=True)
    return scorelines


def win_draw_loss_probabilities(home_xg: float, away_xg: float) -> dict[str, float]:
    scorelines = scoreline_distribution(home_xg, away_xg)
    home_win = sum(item["probability"] for item in scorelines if item["home_goals"] > item["away_goals"])
    draw = sum(item["probability"] for item in scorelines if item["home_goals"] == item["away_goals"])
    away_win = sum(item["probability"] for item in scorelines if item["home_goals"] < item["away_goals"])
    total = home_win + draw + away_win

    home = round(home_win / total, 5)
    draw_value = round(draw / total, 5)
    away = round(1 - home - draw_value, 5)
    return {"home_win": home, "draw": draw_value, "away_win": away}


def confidence_label(match: MatchInputs) -> str:
    rating_gap = abs((match.home.elo_rating or 1800) - (match.away.elo_rating or 1800))
    if match.source_confidence < 0.75:
        return "low"
    if rating_gap >= 180:
        return "high"
    return "medium"


def key_factors(match: MatchInputs) -> list[dict]:
    home_elo = match.home.elo_rating or 1800
    away_elo = match.away.elo_rating or 1800
    home_rank = match.home.fifa_rank or 48
    away_rank = match.away.fifa_rank or 48
    return [
        {
            "label": "elo_diff",
            "value": round(home_elo - away_elo, 2),
            "note": f"{match.home.code} Elo minus {match.away.code} Elo",
        },
        {
            "label": "fifa_rank_diff",
            "value": away_rank - home_rank,
            "note": "Positive value favors the home team because lower FIFA rank is stronger",
        },
        {
            "label": "venue",
            "value": 0 if match.neutral_site else 1,
            "note": "Neutral-site matches remove home-field edge",
        },
    ]


def build_match_prediction(match: MatchInputs) -> dict:
    home_xg, away_xg = expected_goals(match)
    probabilities = win_draw_loss_probabilities(home_xg, away_xg)
    top_scorelines = scoreline_distribution(home_xg, away_xg)[:4]
    return {
        "probabilities": probabilities,
        "expected_goals": {"home": home_xg, "away": away_xg},
        "confidence": confidence_label(match),
        "key_factors": key_factors(match),
        "scorelines": [
            {
                "home_goals": item["home_goals"],
                "away_goals": item["away_goals"],
                "probability": round(item["probability"], 5),
                "rank": index + 1,
            }
            for index, item in enumerate(top_scorelines)
        ],
    }


def team_strength_score(team: TeamInputs) -> float:
    elo = team.elo_rating or 1800
    rank = team.fifa_rank or 48
    return elo / 2200 + (80 - min(rank, 80)) / 160
