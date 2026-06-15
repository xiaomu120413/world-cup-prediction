from __future__ import annotations

import hashlib

from app.collectors.adapters import RawSnapshot


def stable_checksum(*parts: str) -> str:
    value = "|".join(parts)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def news_items_from_snapshot(snapshot: RawSnapshot) -> list[dict]:
    if snapshot.source != "dongqiudi":
        return []

    values = []
    for item in snapshot.payload.get("items", []):
        if item.get("type") != "link" or not item.get("href") or not item.get("title"):
            continue
        values.append(
            {
                "source": snapshot.source,
                "source_url": item["href"],
                "title": item["title"],
                "summary": None,
                "language": "zh",
                "checksum": stable_checksum(snapshot.source, item["href"], item["title"]),
            }
        )
    return values
