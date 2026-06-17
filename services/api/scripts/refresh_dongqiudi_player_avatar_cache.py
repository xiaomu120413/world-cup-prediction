from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.schema import data_source_links, raw_snapshots
from app.db.session import SessionLocal

PLAYER_AVATAR_CACHE_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "dongqiudi_player_avatars.json"
VALID_POSITION_TYPES = {
    "attacker",
    "midfielder",
    "defender",
    "goalkeeper",
    "前锋",
    "中场",
    "后卫",
    "门将",
}


def load_existing_cache() -> dict[str, str]:
    try:
        payload = json.loads(PLAYER_AVATAR_CACHE_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(key): value
        for key, value in payload.items()
        if isinstance(value, str) and value.startswith("http")
    }


def latest_team_detail_snapshot(db) -> dict[str, Any] | None:
    row = db.execute(
        select(
            raw_snapshots.c.id,
            raw_snapshots.c.payload,
            raw_snapshots.c.fetched_at,
        )
        .where(
            raw_snapshots.c.source == "dongqiudi",
            raw_snapshots.c.source_type == "world_cup_team_details",
        )
        .order_by(raw_snapshots.c.fetched_at.desc())
        .limit(1)
    ).mappings().first()
    return dict(row) if row else None


def iter_avatar_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    payload = snapshot.get("payload") or {}
    rows: list[dict[str, Any]] = []
    for team in payload.get("teams") or []:
        if not isinstance(team, dict):
            continue
        source_urls = team.get("source_urls") or {}
        member_url = source_urls.get("member") or payload.get("ranking_url")
        team_name = team.get("team_name")
        team_id = str(team.get("team_id") or "")
        groups = (((team.get("member") or {}).get("data") or {}).get("list") or [])
        for group in groups:
            if not isinstance(group, dict):
                continue
            group_title = group.get("title")
            for item in group.get("data") or []:
                if not isinstance(item, dict):
                    continue
                position_type = item.get("type") or group_title
                if position_type not in VALID_POSITION_TYPES:
                    continue
                person_id = str(item.get("person_id") or "").strip()
                logo = str(item.get("person_logo") or "").strip()
                if not person_id or not logo.startswith("http"):
                    continue
                rows.append(
                    {
                        "person_id": person_id,
                        "player_code": f"DQD-P{person_id}",
                        "avatar_url": logo,
                        "player_name": item.get("person_name"),
                        "team_id": team_id,
                        "team_name": team_name,
                        "source_url": member_url,
                        "raw_snapshot_id": snapshot["id"],
                        "fetched_at": snapshot["fetched_at"],
                        "position_type": position_type,
                        "group": group_title,
                    }
                )
    return rows


def write_cache(rows: list[dict[str, Any]]) -> dict[str, int]:
    existing = load_existing_cache()
    current_person_ids = {row["person_id"] for row in rows}
    avatars = {row["person_id"]: row["avatar_url"] for row in rows}
    next_cache = {
        person_id: avatars.get(person_id) or existing.get(person_id)
        for person_id in sorted(current_person_ids)
        if avatars.get(person_id) or existing.get(person_id)
    }
    PLAYER_AVATAR_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAYER_AVATAR_CACHE_PATH.write_text(
        json.dumps(next_cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "cache_entries_before": len(existing),
        "cache_entries_after": len(next_cache),
        "current_roster_players_seen": len(current_person_ids),
        "avatar_urls_seen": len(avatars),
    }


def upsert_source_links(db, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    values = [
        {
            "entity_type": "player_avatar",
            "entity_key": row["player_code"],
            "source": "dongqiudi",
            "source_type": "team_member_v2_person_logo",
            "source_url": row["source_url"],
            "raw_snapshot_id": row["raw_snapshot_id"],
            "source_record_id": row["person_id"],
            "confidence": Decimal("0.860"),
            "fetched_at": row["fetched_at"],
            "metadata": {
                "team_id": row["team_id"],
                "team_name": row["team_name"],
                "player_name": row["player_name"],
                "position_type": row["position_type"],
                "group": row["group"],
                "avatar_url": row["avatar_url"],
            },
        }
        for row in rows
    ]
    statement = pg_insert(data_source_links).values(values)
    db.execute(
        statement.on_conflict_do_update(
            index_elements=["entity_type", "entity_key", "source", "source_type"],
            set_={
                "source_url": statement.excluded.source_url,
                "raw_snapshot_id": statement.excluded.raw_snapshot_id,
                "source_record_id": statement.excluded.source_record_id,
                "confidence": statement.excluded.confidence,
                "fetched_at": statement.excluded.fetched_at,
                "metadata": statement.excluded.metadata,
            },
        )
    )
    return len(values)


def run() -> dict[str, Any]:
    with SessionLocal() as db:
        snapshot = latest_team_detail_snapshot(db)
        if not snapshot:
            raise RuntimeError("No dongqiudi/world_cup_team_details raw snapshot found.")
        rows = iter_avatar_rows(snapshot)
        cache_result = write_cache(rows)
        source_links_written = upsert_source_links(db, rows)
        db.commit()
    return {
        **cache_result,
        "player_avatar_source_links_written": source_links_written,
    }


def main() -> None:
    print(json.dumps(run(), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
