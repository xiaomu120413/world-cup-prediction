import os

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="set RUN_DATABASE_TESTS=1 and DATABASE_URL to run PostgreSQL integration tests",
)


def database_settings() -> Settings:
    return Settings(data_backend="database", database_url=os.environ["DATABASE_URL"])


@pytest.fixture(name="database_client")
def fixture_database_client():
    app.dependency_overrides.clear()
    from app.core.config import get_settings

    app.dependency_overrides[get_settings] = database_settings
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


def test_database_match_detail_contract(database_client):
    response = database_client.get("/api/v1/matches/usa-paraguay-2026-06-13")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["home_team"]["id"] == "usa"
    assert body["away_team"]["id"] == "paraguay"


def test_database_prediction_contract(database_client):
    response = database_client.get("/api/v1/matches/usa-paraguay-2026-06-13/prediction")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["probabilities"]["home_win"] == 0.44
    assert len(body["scorelines"]) == 4


def test_database_teams_contract(database_client):
    response = database_client.get("/api/v1/teams")
    assert response.status_code == 200
    teams = response.json()["data"]
    assert any(team["id"] == "france" and team["abbr"] == "FRA" for team in teams)


def test_database_home_contract(database_client):
    response = database_client.get("/api/v1/home")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["featured_match"]["id"] == "usa-paraguay-2026-06-13"
    assert len(body["champion_rankings"]) == 3


def test_database_group_contract(database_client):
    response = database_client.get("/api/v1/groups/group-a")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["id"] == "group-a"
    assert len(body["standings"]) == 4


def test_database_rankings_contract(database_client):
    response = database_client.get("/api/v1/predictions/rankings?type=champion")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body[0]["team"]["id"] == "france"
    assert body[0]["probability"] == 0.158
