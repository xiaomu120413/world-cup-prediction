from fastapi.testclient import TestClient
import pytest

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_home_contract():
    response = client.get("/api/v1/home")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "meta" in body
    assert body["data"]["featured_match"]["prediction"]["home_win_prob"] == 0.44


def test_version_contract():
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["api_version"] == "v1"
    assert body["data"]["minimum_miniapp_version"] == "0.1.0"


def test_data_status_contract():
    response = client.get("/api/v1/data-status")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["mode"] == "mock"
    assert body["canonical_ready"] is False
    assert body["latest_collector_runs"] == []


def test_matches_today_contract():
    response = client.get("/api/v1/matches/today")
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) >= 1
    assert body["data"][0]["prediction_summary"]["home_win_prob"] == 0.44


def test_match_detail_contract():
    response = client.get("/api/v1/matches/usa-paraguay-2026-06-13")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["home_team"]["name"] == "美国"
    assert body["away_team"]["name"] == "巴拉圭"


def test_match_prediction_probability_sum():
    response = client.get("/api/v1/matches/usa-paraguay-2026-06-13/prediction")
    assert response.status_code == 200
    probs = response.json()["data"]["probabilities"]
    assert abs(sum(probs.values()) - 1) < 0.001


def test_match_ai_report_contract():
    response = client.get("/api/v1/matches/usa-paraguay-2026-06-13/ai-report")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["confidence_label"] == "中等信心"
    assert len(body["evidence"]) >= 1


def test_missing_match_returns_error():
    response = client.get("/api/v1/matches/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MATCH_NOT_FOUND"


def test_rankings_contract():
    response = client.get("/api/v1/predictions/rankings?type=champion")
    assert response.status_code == 200
    assert response.json()["data"][0]["team"]["name"] == "法国"


@pytest.mark.parametrize("ranking_type", ["champion", "semifinal", "darkhorse"])
def test_all_ranking_types_have_data(ranking_type):
    response = client.get(f"/api/v1/predictions/rankings?type={ranking_type}")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["ranking_type"] == ranking_type
    assert len(body["data"]) >= 1


def test_groups_contract():
    response = client.get("/api/v1/groups")
    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "group-a"


def test_group_detail_contract():
    response = client.get("/api/v1/groups/group-a")
    assert response.status_code == 200
    assert len(response.json()["data"]["standings"]) == 4


def test_group_simulation_contract():
    response = client.get("/api/v1/groups/group-a/simulation")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["simulation_count"] == 50000
    assert body["teams"][0]["qualify_prob"] > 0


def test_teams_contract():
    response = client.get("/api/v1/teams")
    assert response.status_code == 200
    assert any(team["id"] == "france" for team in response.json()["data"])


def test_team_detail_contract():
    response = client.get("/api/v1/teams/france")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["name"] == "法国"
    assert len(body["ratings"]) >= 1


def test_team_profile_contract():
    response = client.get("/api/v1/teams/france/profile")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["team"]["id"] == "france"
    assert len(body["key_players"]) >= 1


def test_team_matches_contract():
    response = client.get("/api/v1/teams/usa/matches")
    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "usa-paraguay-2026-06-13"


def test_player_detail_contract():
    response = client.get("/api/v1/players/mbappe")
    assert response.status_code == 200
    assert response.json()["data"]["recent_form"]["goals"] == 8


def test_admin_requires_token():
    response = client.post("/api/admin/predictions/recompute", json={"scope": "matchday"})
    assert response.status_code == 401
