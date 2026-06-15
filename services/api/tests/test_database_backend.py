import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.collectors.adapters import RawSnapshot
from app.collectors.runner import CollectorRunner
from app.core.config import Settings
from app.db.session import SessionLocal
from app.db.schema import data_source_links, group_standings, matches, player_form_snapshots, players, team_aliases, teams, venues
from app.main import app
from app.predictions.service import BaselinePredictionService


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


def ensure_sample_match_with_prediction() -> None:
    with SessionLocal() as db:
        CollectorRunner(db).run("local_sample", "schedule")
        BaselinePredictionService(db).recompute(
            scope="test",
            match_ids=["usa-paraguay-2026-06-13"],
            seed=20260615,
        )


def test_database_match_detail_contract(database_client):
    ensure_sample_match_with_prediction()
    response = database_client.get("/api/v1/matches/usa-paraguay-2026-06-13")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["home_team"]["id"] == "usa"
    assert body["away_team"]["id"] == "paraguay"


def test_database_prediction_contract(database_client):
    ensure_sample_match_with_prediction()
    response = database_client.get("/api/v1/matches/usa-paraguay-2026-06-13/prediction")
    assert response.status_code == 200
    body = response.json()["data"]
    assert abs(sum(body["probabilities"].values()) - 1) < 0.001
    assert len(body["scorelines"]) >= 4


def test_database_teams_contract(database_client):
    response = database_client.get("/api/v1/teams")
    assert response.status_code == 200
    teams = response.json()["data"]
    assert any(team["id"] == "france" and team["abbr"] == "FRA" for team in teams)


def test_database_home_contract(database_client):
    response = database_client.get("/api/v1/home")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["featured_match"]["id"].startswith(("dongqiudi-", "usa-paraguay-2026-06-13"))
    assert len(body["champion_rankings"]) == 3


def test_database_data_status_contract(database_client):
    with SessionLocal() as db:
        CollectorRunner(db).run("local_sample", "schedule")
        CollectorRunner(db).run("local_sample", "player_ranking")

    response = database_client.get("/api/v1/data-status")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["mode"] == "database"
    assert body["canonical_ready"] is True
    assert body["player_form_ready"] is True
    assert body["table_counts"]["matches"] >= 1
    assert body["table_counts"]["player_form_snapshots"] >= 2
    assert body["table_counts"]["data_source_links"] >= 1
    assert len(body["latest_collector_runs"]) >= 1


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
    assert body[0]["rank"] == 1
    assert 0 < body[0]["probability"] < 1


def test_database_team_profile_uses_player_form(database_client):
    with SessionLocal() as db:
        CollectorRunner(db).run("local_sample", "player_ranking")

    response = database_client.get("/api/v1/teams/france/profile")
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["team"]["id"] == "france"
    assert body["data_sources"]["players"] == "players"
    assert len(body["key_players"]) >= 1
    assert body["form"]["stats"][1]["value"] >= 1


def test_database_baseline_recompute_writes_outputs():
    with SessionLocal() as db:
        result = BaselinePredictionService(db).recompute(
            scope="test",
            match_ids=["usa-paraguay-2026-06-13"],
            seed=20260615,
        )

    assert result["status"] == "completed"
    assert result["matches_written"] == 1
    assert result["rankings_written"] >= 3
    assert result["group_simulations_written"] >= 4


def test_database_collector_writes_idempotent_raw_snapshot():
    with SessionLocal() as db:
        first = CollectorRunner(db).run("local_sample", "schedule")
        second = CollectorRunner(db).run("local_sample", "schedule")

    assert first["status"] == "completed"
    assert first["records_written"] in (0, 1)
    assert second["status"] == "completed"
    assert second["records_written"] == 0
    assert first["snapshot_ids"] == second["snapshot_ids"]


def test_database_collector_normalizes_schedule_to_canonical_tables():
    with SessionLocal() as db:
        result = CollectorRunner(db).run("local_sample", "schedule")
        match_exists = db.execute(
            select(func.count()).select_from(matches).where(matches.c.public_id == "usa-paraguay-2026-06-13")
        ).scalar_one()
        alias_exists = db.execute(
            select(func.count()).select_from(team_aliases).where(team_aliases.c.alias == "United States")
        ).scalar_one()

    assert result["status"] == "completed"
    assert match_exists == 1
    assert alias_exists >= 1


def test_database_collector_records_schedule_source_links():
    with SessionLocal() as db:
        CollectorRunner(db).run("local_sample", "schedule")
        match_source = db.execute(
            select(data_source_links).where(
                data_source_links.c.entity_type == "match",
                data_source_links.c.entity_key == "usa-paraguay-2026-06-13",
                data_source_links.c.source == "local_sample",
                data_source_links.c.source_type == "schedule",
            )
        ).mappings().first()
        team_source_count = db.execute(
            select(func.count())
            .select_from(data_source_links)
            .where(
                data_source_links.c.entity_type == "team",
                data_source_links.c.source == "local_sample",
                data_source_links.c.source_type == "schedule",
            )
        ).scalar_one()

    assert match_source is not None
    assert match_source.raw_snapshot_id is not None
    assert match_source.source_url is not None
    assert team_source_count >= 2


def test_database_collector_normalizes_standings_idempotently():
    with SessionLocal() as db:
        CollectorRunner(db).run("local_sample", "standings")
        first_count = db.execute(select(func.count()).select_from(group_standings)).scalar_one()
        CollectorRunner(db).run("local_sample", "standings")
        second_count = db.execute(select(func.count()).select_from(group_standings)).scalar_one()

    assert first_count >= 4
    assert second_count == first_count


def test_database_collector_normalizes_player_rankings_idempotently():
    with SessionLocal() as db:
        CollectorRunner(db).run("local_sample", "player_ranking")
        first_players = db.execute(select(func.count()).select_from(players)).scalar_one()
        first_forms = db.execute(select(func.count()).select_from(player_form_snapshots)).scalar_one()
        CollectorRunner(db).run("local_sample", "player_ranking")
        second_players = db.execute(select(func.count()).select_from(players)).scalar_one()
        second_forms = db.execute(select(func.count()).select_from(player_form_snapshots)).scalar_one()

    assert first_players >= 2
    assert first_forms >= 2
    assert second_players == first_players
    assert second_forms == first_forms


def test_database_collector_records_player_source_links():
    with SessionLocal() as db:
        CollectorRunner(db).run("local_sample", "player_ranking")
        player_source_count = db.execute(
            select(func.count())
            .select_from(data_source_links)
            .where(
                data_source_links.c.entity_type == "player",
                data_source_links.c.source == "local_sample",
                data_source_links.c.source_type == "player_ranking",
            )
        ).scalar_one()
        form_source_count = db.execute(
            select(func.count())
            .select_from(data_source_links)
            .where(
                data_source_links.c.entity_type == "player_form",
                data_source_links.c.source == "local_sample",
                data_source_links.c.source_type == "player_ranking",
            )
        ).scalar_one()

    assert player_source_count >= 2
    assert form_source_count >= 2


def test_database_collector_serializes_concurrent_same_job():
    def run_job():
        with SessionLocal() as db:
            return CollectorRunner(db).run("local_sample", "standings")

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: run_job(), range(2)))

    with SessionLocal() as db:
        rows = db.execute(select(group_standings.c.stage_id, group_standings.c.team_id)).all()

    assert all(result["status"] == "completed" for result in results)
    assert len(rows) == len(set(rows))


def test_database_collector_normalizes_news_items_idempotently():
    snapshot = RawSnapshot(
        source="dongqiudi",
        source_type="homepage",
        source_url="https://pc.dongqiudi.com/",
        payload={
            "items": [
                {
                    "type": "link",
                    "title": "足球 世界杯 测试新闻",
                    "href": "https://pc.dongqiudi.com/articles/test-news",
                }
            ]
        },
    )
    with SessionLocal() as db:
        runner = CollectorRunner(db)
        first = runner.write_normalized_records(snapshot)
        second = runner.write_normalized_records(snapshot)
        db.commit()

    assert first in (0, 1)
    assert second == 0


def test_database_collector_writes_fixture_venues():
    snapshot = RawSnapshot(
        source="thestatsapi",
        source_type="fixtures",
        source_url="https://www.thestatsapi.com/world-cup/data/fixtures.json",
        payload={
            "venues": [
                {
                    "code": "test-venue",
                    "name": "Test Venue",
                    "city": "Test City",
                    "country": "Test Country",
                    "timezone": "UTC",
                }
            ],
            "matches": [
                {
                    "public_id": "thestatsapi-match-test",
                    "competition_code": "world_cup_2026",
                    "stage_code": "group-test",
                    "stage_name": "Group Test",
                    "stage_type": "group",
                    "home": "Test Home",
                    "away": "Test Away",
                    "kickoff_at": "2026-06-11T19:00:00Z",
                    "status": "scheduled",
                    "venue_code": "test-venue",
                    "source_confidence": 0.95,
                }
            ],
        },
    )

    with SessionLocal() as db:
        runner = CollectorRunner(db)
        runner.write_normalized_records(snapshot)
        db.commit()
        venue_exists = db.execute(
            select(func.count()).select_from(venues).where(venues.c.code == "test-venue")
        ).scalar_one()
        match_row = db.execute(
            select(matches.c.venue_id).where(matches.c.public_id == "thestatsapi-match-test")
        ).first()
        db.execute(
            data_source_links.delete().where(
                data_source_links.c.entity_type.in_(["match", "venue"]),
                data_source_links.c.entity_key.in_(["thestatsapi-match-test", "test-venue"]),
            )
        )
        db.execute(matches.delete().where(matches.c.public_id == "thestatsapi-match-test"))
        db.execute(teams.delete().where(teams.c.name_zh.in_(["Test Home", "Test Away"])))
        db.execute(venues.delete().where(venues.c.code == "test-venue"))
        db.commit()

    assert venue_exists == 1
    assert match_row is not None
    assert match_row.venue_id is not None
