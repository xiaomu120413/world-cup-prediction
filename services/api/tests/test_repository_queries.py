from sqlalchemy.dialects import postgresql

from app.repositories.public_data import PublicDataRepository


def compile_query(query):
    return str(query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def test_match_query_targets_public_id():
    sql = compile_query(PublicDataRepository.match_query("usa-paraguay-2026-06-13"))
    assert "matches.public_id = 'usa-paraguay-2026-06-13'" in sql
    assert "home_team" in sql
    assert "away_team" in sql


def test_latest_prediction_query_orders_by_generation_time():
    sql = compile_query(PublicDataRepository.latest_prediction_query("usa-paraguay-2026-06-13"))
    assert "ORDER BY match_predictions.generated_at DESC" in sql
    assert "LIMIT 1" in sql


def test_rankings_query_filters_ranking_type():
    sql = compile_query(PublicDataRepository.rankings_query("champion", 20))
    assert "ranking_predictions.ranking_type = 'champion'" in sql
    assert "ORDER BY ranking_predictions.rank ASC" in sql


def test_teams_query_filters_to_roster_teams():
    sql = compile_query(PublicDataRepository.teams_query())
    assert "EXISTS" in sql
    assert "players.team_id = teams.id" in sql
    assert "players.code LIKE 'DQD-P%%'" in sql


def test_matches_query_filters_matchday_and_orders_upcoming_ascending():
    sql = compile_query(PublicDataRepository.matches_query(real_only=True, match_date="2026-06-17"))

    assert "matches.public_id LIKE 'dongqiudi-%%'" in sql
    assert "matches.kickoff_at >=" in sql
    assert "matches.kickoff_at <" in sql
    assert "matches.kickoff_at ASC" in sql


def test_groups_query_exposes_only_world_cup_letter_groups():
    sql = compile_query(PublicDataRepository.groups_query())

    assert "competition_stages.code IN" in sql
    assert "'group-a'" in sql
    assert "'group-l'" in sql


def test_prediction_summary_marks_draw_when_draw_is_highest():
    summary = PublicDataRepository.prediction_summary(
        {
            "probabilities": {"home_win": 0.31, "draw": 0.36, "away_win": 0.33},
            "confidence": "medium",
        }
    )

    assert summary["tendency"] == "draw"
