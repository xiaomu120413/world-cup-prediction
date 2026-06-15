from app.collectors.adapters import DongqiudiHomepageAdapter, LocalSampleAdapter, RawSnapshot, build_adapter
from app.collectors.catalog import COLLECTOR_CATALOG, collection_catalog_summary
from app.collectors.normalizers import canonical_records_from_snapshot, news_items_from_snapshot
from app.collectors.runner import snapshot_checksum


def test_local_sample_adapter_fetches_schedule_snapshot():
    snapshot = LocalSampleAdapter("schedule").fetch()

    assert snapshot.source == "local_sample"
    assert snapshot.source_type == "schedule"
    assert len(snapshot.payload["matches"]) == 1


def test_snapshot_checksum_is_stable():
    snapshot = LocalSampleAdapter("schedule").fetch()

    assert snapshot_checksum(snapshot) == snapshot_checksum(snapshot)


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


def test_collection_catalog_tracks_required_data_domains():
    summary = collection_catalog_summary({"dongqiudi_matches": 3, "news_items": 10})

    assert any(job["job_id"] == "dongqiudi_homepage" for job in COLLECTOR_CATALOG)
    assert summary["domains"][0]["domain"] == "matches"
    assert summary["domains"][0]["status"] == "partial_real"
    assert any(domain["domain"] == "player_form" for domain in summary["domains"])


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
    snapshot = LocalSampleAdapter("schedule").fetch()

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
    snapshot = LocalSampleAdapter("standings").fetch()

    records = canonical_records_from_snapshot(snapshot)

    assert len(records["standings"]) == 4
    assert records["standings"][0]["stage_code"] == "group-a"
    assert records["standings"][0]["team_code"] == "FRA"


def test_canonical_records_from_player_ranking_snapshot():
    snapshot = LocalSampleAdapter("player_ranking").fetch()

    records = canonical_records_from_snapshot(snapshot)

    assert len(records["players"]) == 2
    assert records["players"][0]["team_code"] == "FRA"
    assert records["player_forms"][0]["goals"] == 3
