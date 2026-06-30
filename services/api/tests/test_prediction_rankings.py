from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.predictions.service import (
    DEFAULT_PREDICTION_MODEL_VERSION,
    DEFAULT_SCORELINE_MODEL_VERSION,
    DEFAULT_SMALL_MODEL_VERSION,
    BaselinePredictionService,
    simulate_group_table,
    third_place_qualifying_probabilities,
    third_place_state_qualifying_probabilities,
)
from app.predictions.small_outcome_model import HistoricalMatch, TeamState
from app.predictions.tournament_ranker import (
    assign_darkhorse_probabilities,
    assign_tournament_probabilities,
    knockout_advancement_probability,
    simulate_tournament_paths,
    third_place_assignment,
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

    assert qualified_score - at_risk_score > 0.08


def test_darkhorse_ranking_excludes_top_champion_favorites_before_scoring_upside():
    scored = [
        {"team_id": f"team-{index}", "score": 1.2 - index * 0.01, "fifa_rank": index + 1}
        for index in range(16)
    ]
    assign_tournament_probabilities(scored)

    darkhorses = assign_darkhorse_probabilities(scored)

    assert darkhorses
    assert all(item["favorite_rank"] > 10 for item in darkhorses)


def test_third_place_assignment_finds_valid_round_of_32_slots():
    assignment = third_place_assignment(set("ABCDEFGH"))

    assert assignment is not None
    assert set(assignment) == {"M74", "M77", "M79", "M80", "M81", "M82", "M85", "M87"}
    assert set(assignment.values()) == set("ABCDEFGH")


def test_knockout_monte_carlo_outputs_path_probabilities():
    group_state_distributions = {}
    teams_by_id = {}
    for group_index, group_code in enumerate("ABCDEFGHIJKL"):
        ranked = []
        for rank in range(1, 5):
            team_id = f"{group_code}{rank}"
            teams_by_id[team_id] = SimpleNamespace(
                team_id=team_id,
                code=team_id,
                fifa_rank=group_index * 4 + rank,
                elo_rating=2100 - group_index * 8 - rank * 3,
            )
            ranked.append(
                {
                    "team_id": team_id,
                    "seed_rank": rank,
                    "points": 10 - rank,
                    "goal_diff": 5 - rank,
                    "goals_for": 7 - rank,
                }
            )
        group_state_distributions[group_code] = [(1.0, ranked)]

    result = simulate_tournament_paths(group_state_distributions, teams_by_id, iterations=300, seed=17)

    assert result["iterations"] == 300
    assert sum(result["champion_probabilities"].values()) == pytest.approx(1.0)
    assert sum(result["semifinal_probabilities"].values()) == pytest.approx(4.0)
    assert sum(result["round32_probabilities"].values()) == pytest.approx(32.0)
    assert max(result["champion_probabilities"].values()) > 0

    callback_calls = []
    callback_result = simulate_tournament_paths(
        group_state_distributions,
        teams_by_id,
        iterations=20,
        seed=17,
        pair_probability=lambda team_a, team_b: callback_calls.append((team_a.team_id, team_b.team_id)) or 0.5,
    )

    assert callback_result["iterations"] == 20
    assert callback_calls


def test_knockout_monte_carlo_honors_finished_match_winner():
    group_state_distributions = {}
    teams_by_id = {}
    for group_index, group_code in enumerate("ABCDEFGHIJKL"):
        ranked = []
        for rank in range(1, 5):
            team_id = f"{group_code}{rank}"
            teams_by_id[team_id] = SimpleNamespace(
                team_id=team_id,
                code=team_id,
                fifa_rank=group_index * 4 + rank,
                elo_rating=2100 - group_index * 8 - rank * 3,
            )
            ranked.append(
                {
                    "team_id": team_id,
                    "seed_rank": rank,
                    "points": 10 - rank,
                    "goal_diff": 5 - rank,
                    "goals_for": 7 - rank,
                }
            )
        group_state_distributions[group_code] = [(1.0, ranked)]

    result = simulate_tournament_paths(
        group_state_distributions,
        teams_by_id,
        iterations=300,
        seed=17,
        fixed_match_winners={"M73": "A2"},
    )

    assert result["iterations"] == 300
    assert result["champion_probabilities"]["B2"] == 0.0
    assert result["champion_probabilities"]["A2"] > 0.0


def test_knockout_probability_uses_market_value_and_current_tournament_form():
    strong_context = SimpleNamespace(
        team_id="strong-context",
        code="AAA",
        fifa_rank=18,
        elo_rating=1900,
        market_value_eur=950_000_000,
        group_played=2,
        group_points=6,
        group_goal_diff=5,
        group_goals_for=6,
    )
    weak_context = SimpleNamespace(
        team_id="weak-context",
        code="BBB",
        fifa_rank=18,
        elo_rating=1900,
        market_value_eur=150_000_000,
        group_played=2,
        group_points=1,
        group_goal_diff=-2,
        group_goals_for=1,
    )
    neutral_context = SimpleNamespace(
        **{
            **strong_context.__dict__,
            "market_value_eur": weak_context.market_value_eur,
            "group_points": weak_context.group_points,
            "group_goal_diff": weak_context.group_goal_diff,
            "group_goals_for": weak_context.group_goals_for,
        }
    )

    context_probability = knockout_advancement_probability(strong_context, weak_context)
    neutral_probability = knockout_advancement_probability(neutral_context, weak_context)

    assert context_probability > neutral_probability
    assert context_probability > 0.5


def test_small_outcome_knockout_probability_is_neutral_site_symmetric():
    service = BaselinePredictionService(db=None)
    runtime = SimpleNamespace(final_states={})
    team_a = SimpleNamespace(
        team_id="team-a",
        code="AAA",
        fifa_rank=5,
        elo_rating=2050,
        market_value_eur=1_000_000_000,
        group_played=2,
        group_points=6,
        group_goal_diff=4,
        group_goals_for=5,
    )
    team_b = SimpleNamespace(
        team_id="team-b",
        code="BBB",
        fifa_rank=8,
        elo_rating=2000,
        market_value_eur=900_000_000,
        group_played=2,
        group_points=6,
        group_goal_diff=4,
        group_goals_for=5,
    )

    snapshot_at = datetime(2026, 6, 24, tzinfo=timezone.utc)
    team_a_probability = service.knockout_small_outcome_advancement_probability(team_a, team_b, runtime, snapshot_at)
    team_b_probability = service.knockout_small_outcome_advancement_probability(team_b, team_a, runtime, snapshot_at)

    assert team_a_probability + team_b_probability == pytest.approx(1.0)
    assert team_a_probability > 0.5


def test_current_world_cup_results_are_folded_into_prediction_team_state():
    service = BaselinePredictionService(db=None)
    finished_at = datetime(2026, 6, 18, tzinfo=timezone.utc)
    cutoff_at = datetime(2026, 6, 20, tzinfo=timezone.utc)
    base_states = {
        "france": TeamState(elo=1900.0),
        "argentina": TeamState(elo=1900.0),
    }
    service.finished_tournament_matches = lambda: [
        HistoricalMatch(
            match_id="dongqiudi-fra-arg",
            played_at=finished_at,
            home_team_id="france",
            away_team_id="argentina",
            home_team_code="FRA",
            away_team_code="ARG",
            home_score=2,
            away_score=0,
            tournament="FIFA World Cup",
            neutral=True,
        )
    ]

    current_states = service.states_with_current_tournament_results(base_states, cutoff_at)

    assert base_states["france"].matches == 0
    assert current_states["france"].matches == 1
    assert current_states["argentina"].matches == 1
    assert current_states["france"].elo > base_states["france"].elo
    assert current_states["france"].summary(10)["goals_for"] == pytest.approx(2.0)


def test_ranking_probability_delta_uses_previous_snapshot_value():
    assert BaselinePredictionService.ranking_probability_delta(0.12345, 0.1) == 0.02345
    assert BaselinePredictionService.ranking_probability_delta(0.08, None) == 0.0


def test_eliminated_team_constraints_zero_champion_probability_and_renormalize():
    scored = [
        {"team_id": "winner-a", "champion_prob": 0.4, "semifinal_prob": 0.8, "round32_prob": 1.0},
        {"team_id": "eliminated", "champion_prob": 0.3, "semifinal_prob": 0.6, "round32_prob": 1.0},
        {"team_id": "winner-b", "champion_prob": 0.3, "semifinal_prob": 0.5, "round32_prob": 1.0},
    ]

    constrained = BaselinePredictionService.apply_eliminated_team_constraints(scored, {"eliminated"})

    eliminated = next(item for item in constrained if item["team_id"] == "eliminated")
    assert eliminated["champion_prob"] == 0.0
    assert eliminated["semifinal_prob"] == 0.0
    assert sum(item["champion_prob"] for item in constrained) == pytest.approx(1.0)
    assert constrained[0]["champion_prob"] == pytest.approx(4 / 7)


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


def test_best_third_place_rule_splits_equal_tiebreakers_across_remaining_slots():
    group_states_by_stage = {}
    for index in range(12):
        stage_id = f"group-{index}"
        group_states_by_stage[stage_id] = [
            (
                1.0,
                [
                    {"team_id": f"{stage_id}-1", "points": 9, "goal_diff": 6, "goals_for": 8, "seed_rank": 1},
                    {"team_id": f"{stage_id}-2", "points": 6, "goal_diff": 3, "goals_for": 5, "seed_rank": 2},
                    {"team_id": f"{stage_id}-3", "points": 4, "goal_diff": 0, "goals_for": 3, "seed_rank": 3},
                    {"team_id": f"{stage_id}-4", "points": 0, "goal_diff": -6, "goals_for": 1, "seed_rank": 4},
                ],
            )
        ]

    state_probabilities = third_place_state_qualifying_probabilities(group_states_by_stage)
    team_probabilities = third_place_qualifying_probabilities(group_states_by_stage)

    for index in range(12):
        assert state_probabilities[(f"group-{index}", 0)] == pytest.approx(8 / 12)
        assert team_probabilities[f"group-{index}-3"] == pytest.approx(8 / 12)


def test_best_third_place_rule_splits_last_slot_between_equal_third_place_teams():
    group_states_by_stage = {}
    for index in range(12):
        stage_id = f"group-{index}"
        third_points = 12 if index < 7 else 6 if index < 9 else 3
        third_goal_diff = 6 if index < 7 else 0 if index < 9 else -3
        group_states_by_stage[stage_id] = [
            (
                1.0,
                [
                    {"team_id": f"{stage_id}-1", "points": 9, "goal_diff": 7, "goals_for": 9, "seed_rank": 1},
                    {"team_id": f"{stage_id}-2", "points": 6, "goal_diff": 3, "goals_for": 5, "seed_rank": 2},
                    {
                        "team_id": f"{stage_id}-3",
                        "points": third_points,
                        "goal_diff": third_goal_diff,
                        "goals_for": 4,
                        "seed_rank": 3,
                    },
                    {"team_id": f"{stage_id}-4", "points": 0, "goal_diff": -6, "goals_for": 1, "seed_rank": 4},
                ],
            )
        ]

    state_probabilities = third_place_state_qualifying_probabilities(group_states_by_stage)

    for index in range(7):
        assert state_probabilities[(f"group-{index}", 0)] == 1.0
    for index in range(7, 9):
        assert state_probabilities[(f"group-{index}", 0)] == pytest.approx(0.5)
    for index in range(9, 12):
        assert state_probabilities[(f"group-{index}", 0)] == 0.0
