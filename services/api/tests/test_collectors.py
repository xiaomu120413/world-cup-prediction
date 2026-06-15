from app.collectors.adapters import LocalSampleAdapter
from app.collectors.runner import snapshot_checksum


def test_local_sample_adapter_fetches_schedule_snapshot():
    snapshot = LocalSampleAdapter("schedule").fetch()

    assert snapshot.source == "local_sample"
    assert snapshot.source_type == "schedule"
    assert len(snapshot.payload["matches"]) == 1


def test_snapshot_checksum_is_stable():
    snapshot = LocalSampleAdapter("schedule").fetch()

    assert snapshot_checksum(snapshot) == snapshot_checksum(snapshot)
