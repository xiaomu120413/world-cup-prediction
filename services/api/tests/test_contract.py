from fastapi.testclient import TestClient
import pytest

from app.api import routes as api_routes
from app.core.config import Settings, get_settings
from app.main import app

client = TestClient(app)


def database_settings() -> Settings:
    return Settings(data_backend="database", cache_enabled=False)


def offline_settings() -> Settings:
    return Settings(data_backend="offline", cache_enabled=False)


def match_payload(match_id: str = "france-senegal-2026-06-16") -> dict:
    return {
        "id": match_id,
        "home_team": {"id": "france", "name": "France", "abbr": "FRA"},
        "away_team": {"id": "senegal", "name": "Senegal", "abbr": "SEN"},
        "kickoff_at": "2026-06-16T19:00:00+08:00",
        "stage": "group",
        "status": "scheduled",
        "venue": {"name": "MetLife Stadium"},
        "prediction_summary": {
            "home_win_prob": 0.715,
            "draw_prob": 0.181,
            "away_win_prob": 0.104,
            "confidence": 0.82,
        },
    }


class ContractRepository:
    def get_data_status(self):
        return {
            "mode": "database",
            "canonical_ready": True,
            "player_form_ready": True,
            "primary_source": "dongqiudi",
            "table_counts": {"teams": 48, "matches": 104},
            "collection_catalog": {"domains": [], "jobs": []},
            "real_data_audit": {"status": "pass", "no_sample_data": True},
            "latest_collector_runs": [],
        }

    def get_home_data(self, date, timezone):
        return {
            "featured_match": match_payload(),
            "upcoming_matches": [match_payload("iraq-norway-2026-06-16")],
            "champion_rankings": [
                {"team": {"id": "france", "name": "France", "abbr": "FRA"}, "probability": 0.122}
            ],
            "date": date,
            "timezone": timezone,
        }

    def has_real_matches(self):
        return True

    def list_matches(self, include_prediction=True, real_only=True, match_date=None, timezone="Asia/Shanghai"):
        match = match_payload()
        if not include_prediction:
            match = {**match, "prediction_summary": None}
        return [match]

    def get_match(self, match_id):
        return match_payload(match_id)

    def get_match_prediction(self, match_id):
        return {
            "match_id": match_id,
            "generated_at": "2026-06-16T17:30:00+08:00",
            "probabilities": {"home_win": 0.715, "draw": 0.181, "away_win": 0.104},
            "expected_goals": {"home": 2.1, "away": 0.7},
            "confidence": "high",
            "scorelines": [{"home_goals": 1, "away_goals": 0, "probability": 0.146}],
            "key_factors": [{"label": "Elo", "value": 304, "note": "rating gap"}],
        }

    def get_match_ai_report(self, match_id):
        return {
            "match_id": match_id,
            "title": "France vs Senegal AI report",
            "content": "Stored model output and feature evidence are available.",
            "confidence_label": "high",
            "evidence": [{"label": "Elo", "value": 304, "note": "rating gap"}],
            "probabilities": {"home_win": 0.715, "draw": 0.181, "away_win": 0.104},
            "expected_goals": {"home": 2.1, "away": 0.7},
            "scorelines": [{"home_goals": 1, "away_goals": 0, "probability": 0.146}],
            "feature_sources": ["match_predictions"],
            "source": "match_predictions",
            "generated_at": "2026-06-16T17:30:00+08:00",
        }

    def list_groups(self):
        return [{"id": "group-a", "name": "Group A", "matches_finished": 2, "matches_total": 6}]

    def get_group_detail(self, group_id):
        return {
            "id": group_id,
            "name": "Group A",
            "standings": [
                {
                    "rank": 1,
                    "team": {"id": "mexico", "name": "Mexico", "abbr": "MEX"},
                    "record": "1-0-0",
                    "points": 3,
                    "goals": "2:0",
                }
            ],
        }

    def get_group_simulation(self, group_id):
        return {
            "group_id": group_id,
            "simulation_count": 50000,
            "teams": [
                {"team": {"id": "mexico", "name": "Mexico", "abbr": "MEX"}, "qualify_prob": 0.8}
            ],
        }

    def list_rankings(self, ranking_type, limit):
        values = [
            {"team": {"id": "france", "name": "France", "abbr": "FRA"}, "probability": 0.122}
        ]
        return values[:limit]

    def list_teams(self):
        return [
            {"id": "france", "name": "France", "abbr": "FRA", "fifa_rank": 3},
            {"id": "senegal", "name": "Senegal", "abbr": "SEN", "fifa_rank": 15},
        ]

    def get_team_profile(self, team_id):
        if team_id != "france":
            return None
        return {
            "team": {"id": "france", "name": "France", "abbr": "FRA", "fifa_rank": 3, "elo_rating": 2104},
            "summary": "Database-backed team profile.",
            "ratings": [{"label": "attack", "value": 8.8}],
            "form": {"headline": "8W 1D 1L", "stats": []},
            "key_players": [{"id": "mbappe", "name": "Mbappe", "position": "FW"}],
            "probabilities": [],
            "risks": [],
        }

    def list_team_matches(self, team_id):
        if team_id != "france":
            return None
        return [match_payload()]

    def get_player_detail(self, player_id):
        if player_id != "mbappe":
            return None
        return {
            "id": "mbappe",
            "code": "DQD-P50000116",
            "source_player_id": "50000116",
            "name": "Mbappe",
            "name_en": "Kylian Mbappe",
            "team": {"id": "france", "name": "France", "abbr": "FRA"},
            "position": "FW",
            "shirt_number": 10,
            "club": "Real Madrid",
            "market_value_eur": 180000000,
            "form": 9.1,
            "recent_form": {"matches": 10, "goals": 8, "assists": 2, "rating": 8.3},
            "injuries": [],
            "insights": [],
            "quality_status": "verified",
            "updated_at": "2026-06-16T17:30:00+08:00",
        }


class EmptyDatabaseRepository:
    def get_home_data(self, date, timezone):
        return None

    def list_rankings(self, ranking_type, limit):
        return []


@pytest.fixture(autouse=True)
def use_database_repository_by_default(monkeypatch):
    app.dependency_overrides[get_settings] = database_settings
    monkeypatch.setattr(api_routes, "cached_json", lambda settings, key, producer: producer())
    monkeypatch.setattr(api_routes, "with_public_repository", lambda callback: callback(ContractRepository()))
    yield
    app.dependency_overrides.clear()


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
    assert body["data"]["featured_match"]["prediction_summary"]["home_win_prob"] == 0.715


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
    assert body["mode"] == "database"
    assert body["canonical_ready"] is True
    assert body["real_data_audit"]["status"] == "pass"


def test_matches_today_contract():
    response = client.get("/api/v1/matches/today")
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["prediction_summary"]["home_win_prob"] == 0.715


def test_match_detail_contract():
    response = client.get("/api/v1/matches/france-senegal-2026-06-16")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["home_team"]["id"] == "france"
    assert body["away_team"]["id"] == "senegal"


def test_match_prediction_probability_sum():
    response = client.get("/api/v1/matches/france-senegal-2026-06-16/prediction")
    assert response.status_code == 200
    probs = response.json()["data"]["probabilities"]
    assert abs(sum(probs.values()) - 1) < 0.001


def test_match_ai_report_contract():
    response = client.get("/api/v1/matches/france-senegal-2026-06-16/ai-report")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["match_id"] == "france-senegal-2026-06-16"
    assert body["confidence_label"] == "high"
    assert len(body["evidence"]) >= 1


def test_rankings_contract():
    response = client.get("/api/v1/predictions/rankings?type=champion")
    assert response.status_code == 200
    assert response.json()["data"][0]["team"]["id"] == "france"


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
    assert len(response.json()["data"]["standings"]) == 1


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
    assert body["id"] == "france"
    assert len(body["ratings"]) >= 1


def test_team_profile_contract():
    response = client.get("/api/v1/teams/france/profile")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["team"]["id"] == "france"
    assert len(body["key_players"]) >= 1


def test_team_matches_contract():
    response = client.get("/api/v1/teams/france/matches")
    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "france-senegal-2026-06-16"


def test_player_detail_contract():
    response = client.get("/api/v1/players/mbappe")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["id"] == "mbappe"
    assert body["team"]["id"] == "france"


def test_public_api_requires_database_backend():
    app.dependency_overrides[get_settings] = offline_settings
    try:
        response = client.get("/api/v1/home")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_BACKEND_REQUIRED"


def test_database_home_requires_real_data(monkeypatch):
    monkeypatch.setattr(api_routes, "cached_json", lambda settings, key, producer: producer())
    monkeypatch.setattr(api_routes, "with_public_repository", lambda callback: callback(EmptyDatabaseRepository()))

    response = client.get("/api/v1/home")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "HOME_DATA_NOT_FOUND"


def test_database_rankings_empty_result_stays_empty(monkeypatch):
    monkeypatch.setattr(api_routes, "cached_json", lambda settings, key, producer: producer())
    monkeypatch.setattr(api_routes, "with_public_repository", lambda callback: callback(EmptyDatabaseRepository()))

    response = client.get("/api/v1/predictions/rankings?type=champion")

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_admin_requires_token():
    response = client.post("/api/admin/predictions/recompute", json={"scope": "matchday"})
    assert response.status_code == 401


def test_admin_collector_requires_explicit_real_source():
    response = client.post(
        "/api/admin/collectors/run",
        headers={"Authorization": "Bearer change-me"},
        json={"source": "test_fixture", "dry_run": True},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "REAL_SOURCE_REQUIRED"
