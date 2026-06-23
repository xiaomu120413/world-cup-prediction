from types import SimpleNamespace

from app.predictions.service import (
    DEFAULT_PREDICTION_MODEL_VERSION,
    DEFAULT_SCORELINE_MODEL_VERSION,
    DEFAULT_SMALL_MODEL_VERSION,
    BaselinePredictionService,
    simulate_group_table,
    third_place_state_qualifying_probabilities,
)


def test_default_prediction_model_uses_calibrated_outcome_model():
    assert DEFAULT_PREDICTION_MODEL_VERSION == DEFAULT_SMALL_MODEL_VERSION
    assert DEFAULT_SCORELINE_MODEL_VERSION.startswith("scoreline")


def test_tournament_ranking_score_rewards_live_group_form():
    base = SimpleNamespace(
        team_id="france",
        code="FRA",
        fifa_rank=3,
        elo_rating=2104,
        market_value_eur=1_523_000_000,
        group_rank=2,
        group_points=3,
        group_played=1,
        group_goal_diff=2,
        group_goals_for=3,
    )
    stale = SimpleNamespace(
        **{
            **base.__dict__,
            "group_points": 0,
            "group_played": 0,
            "group_goal_diff": 0,
            "group_goals_for": 0,
        }
    )

    updated_score = BaselinePredictionService.tournament_team_score(base)["score"]
    stale_score = BaselinePredictionService.tournament_team_score(stale)["score"]

    assert updated_score > stale_score


def test_tournament_ranking_score_rewards_group_path_probability():
    row = SimpleNamespace(
        team_id="norway",
        code="NORWAY",
        fifa_rank=33,
        elo_rating=1850,
        market_value_eur=450_000_000,
        group_rank=2,
        group_points=6,
        group_played=2,
        group_goal_diff=4,
        group_goals_for=7,
    )

    qualified_path = {"qualify_prob": 1.0, "rank_1_prob": 0.45, "expected_points": 7.4}
    at_risk_path = {"qualify_prob": 0.25, "rank_1_prob": 0.02, "expected_points": 3.4}

    qualified_score = BaselinePredictionService.tournament_team_score(row, qualified_path)["score"]
    at_risk_score = BaselinePredictionService.tournament_team_score(row, at_risk_path)["score"]

    assert qualified_score - at_risk_score > 0.2


def test_ranking_probability_delta_uses_previous_snapshot_value():
    assert BaselinePredictionService.ranking_probability_delta(0.12345, 0.1) == 0.02345
    assert BaselinePredictionService.ranking_probability_delta(0.08, None) == 0.0


def test_group_simulation_uses_remaining_match_probabilities():
    standings = [
        SimpleNamespace(team_id="france", rank=1, points=6, goal_diff=5, goals_for=6),
        SimpleNamespace(team_id="norway", rank=2, points=6, goal_diff=4, goals_for=7),
        SimpleNamespace(team_id="senegal", rank=3, points=0, goal_diff=-3, goals_for=3),
        SimpleNamespace(team_id="iraq", rank=4, points=0, goal_diff=-6, goals_for=1),
    ]
    remaining_matches = [
        {
            "home_team_id": "norway",
            "away_team_id": "france",
            "home_win_prob": 0.13807,
            "draw_prob": 0.24368,
            "away_win_prob": 0.61825,
            "home_expected_goals": 0.74,
            "away_expected_goals": 1.75,
        },
        {
            "home_team_id": "senegal",
            "away_team_id": "iraq",
            "home_win_prob": 0.67494,
            "draw_prob": 0.21062,
            "away_win_prob": 0.11444,
            "home_expected_goals": 1.89,
            "away_expected_goals": 0.61,
        },
    ]

    simulation = simulate_group_table(standings, remaining_matches)

    assert simulation["france"]["rank_1_prob"] == 0.86193
    assert simulation["france"]["rank_2_prob"] == 0.13807
    assert simulation["france"]["qualify_prob"] == 1.0
    assert simulation["norway"]["rank_1_prob"] == 0.13807
    assert simulation["norway"]["qualify_prob"] == 1.0
    assert simulation["senegal"]["qualify_prob"] == 0.0
    assert simulation["iraq"]["qualify_prob"] == 0.0


def test_group_simulation_can_include_best_third_place_probability():
    standings = [
        SimpleNamespace(team_id="team-a", rank=1, points=6, goal_diff=5, goals_for=6),
        SimpleNamespace(team_id="team-b", rank=2, points=4, goal_diff=2, goals_for=4),
        SimpleNamespace(team_id="team-c", rank=3, points=3, goal_diff=0, goals_for=3),
        SimpleNamespace(team_id="team-d", rank=4, points=0, goal_diff=-7, goals_for=1),
    ]

    simulation = simulate_group_table(standings, [], third_place_qualifiers={0: 0.75})

    assert simulation["team-a"]["qualify_prob"] == 1.0
    assert simulation["team-b"]["qualify_prob"] == 1.0
    assert simulation["team-c"]["qualify_prob"] == 0.75
    assert simulation["team-d"]["qualify_prob"] == 0.0


def test_best_third_place_rule_qualifies_eight_best_third_place_teams():
    group_states_by_stage = {}
    for index in range(12):
        third_points = 20 - index
        stage_id = f"group-{index}"
        group_states_by_stage[stage_id] = [
            (
                1.0,
                [
                    {"team_id": f"{stage_id}-1", "points": 9, "goal_diff": 6, "goals_for": 8, "seed_rank": 1},
                    {"team_id": f"{stage_id}-2", "points": 6, "goal_diff": 3, "goals_for": 5, "seed_rank": 2},
                    {
                        "team_id": f"{stage_id}-3",
                        "points": third_points,
                        "goal_diff": third_points,
                        "goals_for": third_points,
                        "seed_rank": 3,
                    },
                    {"team_id": f"{stage_id}-4", "points": 0, "goal_diff": -6, "goals_for": 1, "seed_rank": 4},
                ],
            )
        ]

    state_probabilities = third_place_state_qualifying_probabilities(group_states_by_stage)

    for index in range(8):
        assert state_probabilities[(f"group-{index}", 0)] == 1.0
    for index in range(8, 12):
        assert state_probabilities[(f"group-{index}", 0)] == 0.0
