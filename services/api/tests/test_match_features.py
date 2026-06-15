from datetime import datetime, timezone

from app.features.match_features import ResultRow, aggregate_results, assemble_numeric_features, quality_status


def result_row(result: str, goals_for: int, goals_against: int, opponent_rank: int | None = None) -> ResultRow:
    return ResultRow(
        result=result,
        goals_for=goals_for,
        goals_against=goals_against,
        opponent_rank=opponent_rank,
        opponent_rank_bucket="top30" if opponent_rank and opponent_rank <= 30 else "other",
        competition_name="FIFA World Cup qualification",
        played_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def team_context(code: str, rank: int, market_value: int, form_score: float):
    history = {
        name: {
            "matches": 3,
            "win_rate": 0.6667,
            "draw_rate": 0.0,
            "loss_rate": 0.3333,
            "points_per_match": 2.0,
            "goals_for_per_match": 2.0,
            "goals_against_per_match": 1.0,
            "goal_diff_per_match": 1.0,
        }
        for name in ("last20", "since_2024", "since_2022", "world_cup_qualifying", "vs_top10", "vs_top30", "vs_top50")
    }
    return {
        "context": {
            "code": code,
            "name_zh": code,
            "name_en": code,
            "fifa_rank": rank,
            "elo_rating": 1800 + (50 - rank),
            "market_value_eur": market_value,
            "history": history,
            "team_stats": {
                "goals": {"value": 7, "rank": 2},
                "goal_against": {"value": 3, "rank": 4},
            },
            "player_form": {
                "avg_form_score": form_score,
                "goals_per_player": 0.5,
                "assists_per_player": 0.2,
                "shots_per_player": 1.4,
                "key_passes_per_player": 0.7,
                "minutes_per_player": 65,
                "unavailable_count": 1,
                "roster_market_value_eur": market_value,
            },
            "availability": {"availability_impact": -0.4},
        }
    }


def test_aggregate_results_outputs_training_ready_rates():
    summary = aggregate_results(
        [
            result_row("win", 2, 0, 8),
            result_row("draw", 1, 1, 18),
            result_row("loss", 0, 1, 45),
        ]
    )

    assert summary["matches"] == 3
    assert summary["points_per_match"] == 1.3333
    assert summary["goal_diff_per_match"] == 0.3333


def test_assemble_numeric_features_creates_raw_and_diff_features_without_probabilities():
    numeric, missing = assemble_numeric_features(
        {
            "public_id": "match-1",
            "neutral_site": True,
            "source_confidence": 0.95,
        },
        team_context("FRA", 3, 1_000_000_000, 7.5),
        team_context("USA", 11, 500_000_000, 7.0),
        {
            "temperature_c": 21.5,
            "humidity_pct": 60,
            "precipitation_mm": 0,
            "wind_speed_kph": 12,
            "wind_direction_deg": 180,
            "weather_code": 1,
        },
    )

    assert numeric["fifa_rank_diff"] == 8
    assert numeric["market_value_log_diff"] > 0
    assert numeric["player_avg_form_score_diff"] == 0.5
    assert "home_win_prob" not in numeric
    assert quality_status(missing) == "complete"
