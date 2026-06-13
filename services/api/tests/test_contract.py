from fastapi.testclient import TestClient

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


def test_match_prediction_probability_sum():
    response = client.get("/api/v1/matches/usa-paraguay-2026-06-13/prediction")
    assert response.status_code == 200
    probs = response.json()["data"]["probabilities"]
    assert abs(sum(probs.values()) - 1) < 0.001


def test_missing_match_returns_error():
    response = client.get("/api/v1/matches/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MATCH_NOT_FOUND"


def test_rankings_contract():
    response = client.get("/api/v1/predictions/rankings?type=champion")
    assert response.status_code == 200
    assert response.json()["data"][0]["team"]["name"] == "法国"


def test_admin_requires_token():
    response = client.post("/api/admin/predictions/recompute", json={"scope": "matchday"})
    assert response.status_code == 401
