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
