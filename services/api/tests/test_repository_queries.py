from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.repositories.public_data import PublicDataRepository, source_player_id_from_code


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


def test_team_news_query_filters_related_team_and_names():
    team_uuid = uuid4()
    sql = compile_query(PublicDataRepository.team_news_query(team_uuid, "阿根廷", "Argentina"))

    assert "ANY (news_items.related_team_ids)" in sql
    assert "news_items.title ILIKE" in sql
    assert "news_items.summary ILIKE" in sql
    assert "ORDER BY coalesce(news_items.published_at, news_items.fetched_at) DESC" in sql


def test_team_profile_queries_include_design_report_sources():
    team_uuid = uuid4()
    stage_uuid = uuid4()

    group_sql = compile_query(PublicDataRepository.team_group_profile_query(team_uuid))
    simulation_sql = compile_query(PublicDataRepository.latest_team_group_simulation_query(team_uuid, stage_uuid))
    results_sql = compile_query(PublicDataRepository.team_match_results_query(team_uuid))
    coach_sql = compile_query(PublicDataRepository.coach_query(team_uuid))
    matches_sql = compile_query(PublicDataRepository.team_matches_query(team_uuid))

    assert "group_standings.team_id" in group_sql
    assert "group_simulations.rank_1_prob" in simulation_sql
    assert "team_match_results.opponent_rank_bucket" in results_sql
    assert "coaches.team_id" in coach_sql
    assert "matches.home_team_id" in matches_sql
    assert "matches.away_team_id" in matches_sql


def test_dongqiudi_player_source_id_is_extracted_from_canonical_code():
    assert source_player_id_from_code("DQD-P50000116") == "50000116"
    assert source_player_id_from_code("mbappe") is None


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
