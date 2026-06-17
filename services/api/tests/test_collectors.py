from datetime import UTC, datetime

from app.collectors.adapters import (
    DongqiudiHomepageAdapter,
    DongqiudiWorldCupDataAdapter,
    RawSnapshot,
    TheStatsApiFixturesAdapter,
    build_adapter,
)
from app.collectors.catalog import COLLECTOR_CATALOG, collection_catalog_summary
from app.collectors.normalizers import canonical_records_from_snapshot, news_items_from_snapshot
from app.collectors.runner import CollectorRunner, snapshot_checksum
from scripts.collect_dongqiudi_match_context import parse_kickoff


def schedule_snapshot() -> RawSnapshot:
    return RawSnapshot(
        source="test_fixture",
        source_type="schedule",
        source_url=None,
        payload={
            "matches": [
                {
                    "public_id": "usa-paraguay-2026-06-13",
                    "home": "USA",
                    "away": "PAR",
                    "kickoff_at": "2026-06-13T01:00:00+08:00",
                    "status": "scheduled",
                }
            ]
        },
        parser_version="test_fixture_v1",
    )


def standings_snapshot() -> RawSnapshot:
    return RawSnapshot(
        source="test_fixture",
        source_type="standings",
        source_url=None,
        payload={
            "groups": [
                {
                    "code": "group-a",
                    "teams": [
                        {"code": "FRA", "rank": 1, "points": 3},
                        {"code": "BRA", "rank": 2, "points": 3},
                        {"code": "USA", "rank": 3, "points": 0},
                        {"code": "PAR", "rank": 4, "points": 0},
                    ],
                }
            ]
        },
        parser_version="test_fixture_v1",
    )


def player_ranking_snapshot() -> RawSnapshot:
    return RawSnapshot(
        source="test_fixture",
        source_type="player_ranking",
        source_url=None,
        payload={
            "players": [
                {"name": "fixture_forward", "team": "FRA", "goals": 3, "assists": 1},
                {"name": "fixture_midfielder", "team": "BRA", "goals": 1, "assists": 2},
            ]
        },
        parser_version="test_fixture_v1",
    )


def test_test_fixture_schedule_snapshot_shape():
    snapshot = schedule_snapshot()

    assert snapshot.source == "test_fixture"
    assert snapshot.source_type == "schedule"
    assert len(snapshot.payload["matches"]) == 1


def test_snapshot_checksum_is_stable():
    snapshot = schedule_snapshot()

    assert snapshot_checksum(snapshot) == snapshot_checksum(snapshot)


def test_dongqiudi_schedule_start_play_is_parsed_as_utc():
    assert parse_kickoff("2026-06-16 22:00:00") == datetime(2026, 6, 16, 22, 0, tzinfo=UTC)


def test_runner_counts_all_top_level_list_records():
    snapshot = RawSnapshot(
        source="test",
        source_type="multi",
        source_url=None,
        payload={"venues": [{"id": 1}, {"id": 2}], "matches": [{"id": 1}, {"id": 2}, {"id": 3}]},
    )

    assert CollectorRunner.count_records(snapshot) == 5


def test_dongqiudi_homepage_adapter_parses_static_html():
    html = """
    <html>
      <head><title>懂球帝</title></head>
      <body>
        <div>今日重要赛事</div><div>06月15日 · 2场</div>
        <div>世界杯</div><div>FT</div><div>科特迪瓦</div><div>1 - 0</div><div>厄瓜多尔</div>
        <div>世界杯</div><div>瑞典</div><div>10:00</div><div>突尼斯</div>
        <a href="/articles/1">足球 世界杯 德国7-1大胜库拉索</a>
      </body>
    </html>
    """

    snapshot = DongqiudiHomepageAdapter("homepage").parse(html, "https://pc.dongqiudi.com/")

    assert snapshot.source == "dongqiudi"
    assert snapshot.source_type == "homepage"
    assert snapshot.payload["title"] == "懂球帝"
    assert any(item["type"] == "link" for item in snapshot.payload["items"])
    assert any(item["type"] == "match_block" for item in snapshot.payload["items"])
    assert snapshot.payload["matches"][0]["home"] == "科特迪瓦"
    assert snapshot.payload["matches"][0]["away"] == "厄瓜多尔"
    assert snapshot.payload["matches"][0]["status"] == "finished"


def test_build_adapter_supports_dongqiudi_source():
    adapter = build_adapter("dongqiudi", "homepage")

    assert adapter.source == "dongqiudi"


def test_build_adapter_supports_dongqiudi_world_cup_data_source():
    adapter = build_adapter("dongqiudi", "world_cup_player_rankings")

    assert adapter.source == "dongqiudi"
    assert adapter.source_type == "world_cup_player_rankings"


def test_build_adapter_supports_thestatsapi_source():
    adapter = build_adapter("thestatsapi", "fixtures")

    assert adapter.source == "thestatsapi"


def test_collection_catalog_tracks_required_data_domains():
    summary = collection_catalog_summary(
        {
            "dongqiudi_matches": 3,
            "thestatsapi_matches": 104,
            "news_items": 10,
            "dongqiudi_standings_snapshots": 1,
            "dongqiudi_player_ranking_snapshots": 1,
            "player_market_values": 20,
        }
    )

    assert any(job["job_id"] == "dongqiudi_homepage" for job in COLLECTOR_CATALOG)
    assert summary["domains"][0]["domain"] == "matches"
    assert summary["domains"][0]["status"] == "partial_real"
    assert "thestatsapi/fixtures" in summary["domains"][0]["current_source"]
    assert next(domain for domain in summary["domains"] if domain["domain"] == "standings")["status"] == "partial_real"
    assert next(domain for domain in summary["domains"] if domain["domain"] == "player_form")["status"] == "partial_real"
    assert next(domain for domain in summary["domains"] if domain["domain"] == "market_value")["status"] == "partial_real"


def test_dongqiudi_world_cup_standings_parser():
    data = {
        "content": {
            "rounds": [
                {
                    "content": {
                        "data": [
                            {
                                "name": "A组",
                                "data": [
                                    {
                                        "team_id": "50001278",
                                        "team_name": "墨西哥",
                                        "rank": "1",
                                        "matches_total": "1",
                                        "matches_won": "1",
                                        "matches_draw": "0",
                                        "matches_lost": "0",
                                        "goals_pro": "2",
                                        "goals_against": "0",
                                        "points": "3",
                                    }
                                ],
                            }
                        ]
                    }
                }
            ]
        }
    }

    groups = DongqiudiWorldCupDataAdapter.extract_groups(data)

    assert groups[0]["code"] == "group-a"
    assert groups[0]["teams"][0]["team"] == "墨西哥"
    assert groups[0]["teams"][0]["goal_diff"] == 2


def test_dongqiudi_world_cup_player_ranking_parser_merges_stats():
    ranking_payloads = {
        "goals": {
            "content": {
                "data": [
                    {
                        "person_id": "50259320",
                        "person_name": "哈弗茨",
                        "team_id": "50000868",
                        "team_name": "德国",
                        "count": "2",
                    }
                ]
            }
        },
        "assists": {
            "content": {
                "data": [
                    {
                        "person_id": "50259320",
                        "person_name": "哈弗茨",
                        "team_id": "50000868",
                        "team_name": "德国",
                        "count": "1",
                    }
                ]
            }
        },
        "appearances": {
            "content": {
                "data": [
                    {
                        "person_id": "50259320",
                        "person_name": "Havertz",
                        "team_id": "50000868",
                        "team_name": "Germany",
                        "count": "1",
                    }
                ]
            }
        },
        "minutes": {
            "content": {
                "data": [
                    {
                        "person_id": "50259320",
                        "person_name": "Havertz",
                        "team_id": "50000868",
                        "team_name": "Germany",
                        "count": "90",
                    }
                ]
            }
        },
        "starts": {
            "content": {
                "data": [
                    {
                        "person_id": "50259320",
                        "person_name": "Havertz",
                        "team_id": "50000868",
                        "team_name": "Germany",
                        "count": "1",
                    }
                ]
            }
        },
    }

    players = DongqiudiWorldCupDataAdapter.extract_players(ranking_payloads, {"50259320": 75000000})

    assert players == [
        {
            "code": "DQD-P50259320",
            "source_player_id": "50259320",
            "name": "哈弗茨",
            "team": "德国",
            "source_team_id": "50000868",
            "market_value_eur": 75000000,
            "recent_matches": 1,
            "source_count": 4,
            "goals": 2,
            "assists": 1,
            "minutes": 90,
            "starts": 1,
        }
    ]


def test_dongqiudi_market_value_parser_keeps_eur_values():
    values = DongqiudiWorldCupDataAdapter.extract_market_values(
        {
            "content": {
                "data": [
                    {"person_id": "1", "currency": "EUR", "value": "100000000"},
                    {"person_id": "2", "currency": "USD", "value": "90000000"},
                ]
            }
        }
    )

    assert values == {"1": 100000000}


def test_thestatsapi_fixtures_adapter_parses_static_json():
    snapshot = TheStatsApiFixturesAdapter("fixtures").parse(
        {
            "source": "TheStatsAPI",
            "license": "fixture license",
            "tournament": {"edition": "2026 FIFA World Cup"},
            "fixtures": [
                {
                    "matchNumber": 1,
                    "date": "2026-06-11",
                    "kickoffUtc": "2026-06-11T19:00:00Z",
                    "stage": "group-stage",
                    "group": "A",
                    "homeTeam": "Mexico",
                    "awayTeam": "South Africa",
                    "stadium": "Estadio Azteca",
                    "hostCity": "mexico-city",
                    "matchUrl": "https://www.thestatsapi.com/world-cup/matches/1",
                }
            ],
        }
    )

    assert snapshot.source == "thestatsapi"
    assert snapshot.source_type == "fixtures"
    assert snapshot.payload["venues"][0]["code"] == "estadio-azteca"
    assert snapshot.payload["venues"][0]["timezone"] == "America/Mexico_City"
    assert snapshot.payload["matches"][0]["public_id"] == "thestatsapi-match-1"
    assert snapshot.payload["matches"][0]["venue_code"] == "estadio-azteca"


def test_canonical_records_from_thestatsapi_fixture_snapshot():
    snapshot = RawSnapshot(
        source="thestatsapi",
        source_type="fixtures",
        source_url="https://www.thestatsapi.com/world-cup/data/fixtures.json",
        payload={
            "venues": [
                {
                    "code": "estadio-azteca",
                    "name": "Estadio Azteca",
                    "city": "Mexico City",
                    "country": "Mexico",
                    "timezone": "America/Mexico_City",
                }
            ],
            "matches": [
                {
                    "public_id": "thestatsapi-match-1",
                    "competition_code": "world_cup_2026",
                    "stage_code": "group-a",
                    "stage_name": "Group A",
                    "stage_type": "group",
                    "home": "Mexico",
                    "away": "South Africa",
                    "kickoff_at": "2026-06-11T19:00:00Z",
                    "status": "scheduled",
                    "venue_code": "estadio-azteca",
                    "source_confidence": 0.95,
                }
            ],
        },
    )

    records = canonical_records_from_snapshot(snapshot)

    assert records["venues"][0]["name"] == "Estadio Azteca"
    assert records["matches"][0]["venue_code"] == "estadio-azteca"
    assert {team["name_zh"] for team in records["teams"]} == {"Mexico", "South Africa"}


def test_news_items_from_dongqiudi_snapshot():
    snapshot = RawSnapshot(
        source="dongqiudi",
        source_type="homepage",
        source_url="https://pc.dongqiudi.com/",
        payload={
            "items": [
                {
                    "type": "link",
                    "title": "足球 世界杯 德国7-1大胜库拉索",
                    "href": "https://pc.dongqiudi.com/articles/1",
                },
                {"type": "match_block", "competition": "世界杯"},
            ]
        },
    )

    values = news_items_from_snapshot(snapshot)

    assert len(values) == 1
    assert values[0]["source"] == "dongqiudi"
    assert values[0]["language"] == "zh"


def test_canonical_records_from_schedule_snapshot():
    snapshot = schedule_snapshot()

    records = canonical_records_from_snapshot(snapshot)

    assert {team["code"] for team in records["teams"]} == {"USA", "PAR"}
    assert records["matches"][0]["public_id"] == "usa-paraguay-2026-06-13"
    assert records["matches"][0]["home_team_code"] == "USA"
    assert any(alias["alias"] == "United States" for alias in records["team_aliases"])


def test_canonical_records_from_dongqiudi_homepage_matches():
    snapshot = RawSnapshot(
        source="dongqiudi",
        source_type="homepage",
        source_url="https://pc.dongqiudi.com/",
        payload={
            "matches": [
                {
                    "public_id": "dongqiudi-civ-ecuador-2026-06-15",
                    "competition_code": "world_cup_2026",
                    "stage_code": "world-cup-homepage",
                    "stage_name": "世界杯",
                    "stage_type": "group",
                    "home": "科特迪瓦",
                    "away": "厄瓜多尔",
                    "kickoff_at": "2026-06-15T00:00:00+08:00",
                    "status": "finished",
                    "home_score": 1,
                    "away_score": 0,
                    "source_confidence": 0.7,
                }
            ]
        },
    )

    records = canonical_records_from_snapshot(snapshot)

    assert len(records["teams"]) == 2
    assert records["teams"][0]["code"].startswith("DQD")
    assert records["matches"][0]["stage_name"] == "世界杯"
    assert records["matches"][0]["home_score"] == 1


def test_canonical_records_from_standings_snapshot():
    snapshot = standings_snapshot()

    records = canonical_records_from_snapshot(snapshot)

    assert len(records["standings"]) == 4
    assert len(records["team_forms"]) == 0
    assert records["standings"][0]["stage_code"] == "group-a"
    assert records["standings"][0]["team_code"] == "FRA"


def test_canonical_records_from_real_standings_create_team_forms():
    snapshot = RawSnapshot(
        source="dongqiudi",
        source_type="world_cup_standings",
        source_url="https://sport-data.dongqiudi.com/soccer/biz/data/standing?season_id=26123",
        payload={
            "as_of_at": "2026-06-15T12:00:00+08:00",
            "groups": [
                {
                    "code": "group-a",
                    "name": "A组",
                    "teams": [
                        {
                            "team": "墨西哥",
                            "rank": 1,
                            "played": 1,
                            "wins": 1,
                            "draws": 0,
                            "losses": 0,
                            "goals_for": 2,
                            "goals_against": 0,
                            "points": 3,
                        }
                    ],
                }
            ],
        },
    )

    records = canonical_records_from_snapshot(snapshot)

    assert records["standings"][0]["stage_name"] == "A组"
    assert records["team_forms"][0]["team_code"].startswith("DQD")
    assert records["team_forms"][0]["points_per_match"] == 3.0
    assert records["team_forms"][0]["goals_for_per_match"] == 2.0


def test_canonical_records_from_player_ranking_snapshot():
    snapshot = player_ranking_snapshot()

    records = canonical_records_from_snapshot(snapshot)

    assert len(records["players"]) == 2
    assert records["players"][0]["team_code"] == "FRA"
    assert records["player_forms"][0]["goals"] == 3
