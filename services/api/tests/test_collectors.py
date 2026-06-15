from app.collectors.adapters import DongqiudiHomepageAdapter, LocalSampleAdapter, RawSnapshot, build_adapter
from app.collectors.normalizers import news_items_from_snapshot
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
        <a href="/articles/1">足球 世界杯 德国7-1大胜库拉索</a>
        <div>世界杯</div><div>德国</div><div>7 - 1</div><div>库拉索</div>
      </body>
    </html>
    """

    snapshot = DongqiudiHomepageAdapter("homepage").parse(html, "https://pc.dongqiudi.com/")

    assert snapshot.source == "dongqiudi"
    assert snapshot.source_type == "homepage"
    assert snapshot.payload["title"] == "懂球帝"
    assert any(item["type"] == "link" for item in snapshot.payload["items"])
    assert any(item["type"] == "match_block" for item in snapshot.payload["items"])


def test_build_adapter_supports_dongqiudi_source():
    adapter = build_adapter("dongqiudi", "homepage")

    assert adapter.source == "dongqiudi"


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
