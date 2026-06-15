from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RawSnapshot:
    source: str
    source_type: str
    source_url: str | None
    payload: dict
    parser_version: str = "local_sample_v1"


class CollectorAdapter(Protocol):
    source: str
    source_type: str

    def fetch(self) -> RawSnapshot:
        ...


class LocalSampleAdapter:
    source = "local_sample"

    def __init__(self, source_type: str):
        self.source_type = source_type

    def fetch(self) -> RawSnapshot:
        payload = SAMPLE_PAYLOADS.get(self.source_type)
        if payload is None:
            raise ValueError(f"Unsupported local sample source_type: {self.source_type}")
        return RawSnapshot(
            source=self.source,
            source_type=self.source_type,
            source_url=f"local://sample/{self.source_type}",
            payload=payload,
        )


SAMPLE_PAYLOADS = {
    "schedule": {
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
    "standings": {
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
    "player_ranking": {
        "players": [
            {"name": "sample_forward", "team": "FRA", "goals": 3, "assists": 1},
            {"name": "sample_midfielder", "team": "BRA", "goals": 1, "assists": 2},
        ]
    },
}


def build_adapter(source: str, source_type: str) -> CollectorAdapter:
    if source == "local_sample":
        return LocalSampleAdapter(source_type)
    raise ValueError(f"Unsupported collector source: {source}")
