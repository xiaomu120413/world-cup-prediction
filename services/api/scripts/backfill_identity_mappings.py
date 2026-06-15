from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import String, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.schema import (
    data_source_links,
    historical_international_matches,
    injury_reports,
    lineup_snapshots,
    player_aliases,
    players,
    team_aliases,
    teams,
)
from app.db.session import SessionLocal


def normalize_name(value: str | None) -> str:
    return "".join(ch.lower() for ch in (value or "").strip() if ch.isalnum())


def alias_source_id(source_id: str, alias: str, is_primary: bool) -> str:
    if is_primary:
        return source_id
    return f"{source_id}:{hashlib.sha256(alias.encode('utf-8')).hexdigest()[:12]}"


def player_source_id_from_code(code: str) -> str | None:
    if code.startswith("DQD-P"):
        return code.removeprefix("DQD-P")
    return None


def upsert_player_alias_rows(db, rows: list[dict]) -> int:
    if not rows:
        return 0
    statement = (
        pg_insert(player_aliases)
        .values(rows)
        .on_conflict_do_update(
            index_elements=["source", "source_player_id"],
            set_={
                "player_id": pg_insert(player_aliases).excluded.player_id,
                "team_id": pg_insert(player_aliases).excluded.team_id,
                "alias": pg_insert(player_aliases).excluded.alias,
                "confidence": pg_insert(player_aliases).excluded.confidence,
                "is_primary": pg_insert(player_aliases).excluded.is_primary,
            },
        )
        .returning(player_aliases.c.id)
    )
    return len(db.execute(statement).all())


def backfill_roster_player_aliases(db) -> int:
    alias_rows = []
    seen = set()
    player_rows = db.execute(
        select(players.c.id, players.c.team_id, players.c.code, players.c.name_zh, players.c.name_en)
        .where(players.c.code.like("DQD-P%"))
        .order_by(players.c.code)
    ).mappings()
    for row in player_rows:
        source_id = player_source_id_from_code(row["code"])
        if not source_id:
            continue
        aliases = []
        for alias in (row["name_zh"], row["name_en"], row["code"]):
            if alias and alias not in aliases:
                aliases.append(alias)
        for index, alias in enumerate(aliases):
            is_primary = index == 0
            source_player_id = alias_source_id(source_id, alias, is_primary)
            key = ("dongqiudi", source_player_id)
            if key in seen:
                continue
            seen.add(key)
            alias_rows.append(
                {
                    "player_id": row["id"],
                    "team_id": row["team_id"],
                    "source": "dongqiudi",
                    "source_player_id": source_player_id,
                    "alias": alias,
                    "confidence": 0.95,
                    "is_primary": is_primary,
                }
            )
    return upsert_player_alias_rows(db, alias_rows)


def backfill_lineup_player_aliases(db) -> int:
    alias_rows = []
    seen = set()
    rows = db.execute(
        select(
            lineup_snapshots.c.player_id,
            lineup_snapshots.c.team_id,
            lineup_snapshots.c.source_player_id,
            lineup_snapshots.c.player_name,
        )
        .where(lineup_snapshots.c.player_id.is_not(None))
        .where(lineup_snapshots.c.source_player_id.is_not(None))
    ).mappings()
    for row in rows:
        source_player_id = str(row["source_player_id"])
        alias = row["player_name"]
        key = ("dongqiudi", source_player_id)
        if key in seen:
            continue
        seen.add(key)
        alias_rows.append(
            {
                "player_id": row["player_id"],
                "team_id": row["team_id"],
                "source": "dongqiudi",
                "source_player_id": source_player_id,
                "alias": alias,
                "confidence": 0.9,
                "is_primary": True,
            }
        )
    return upsert_player_alias_rows(db, alias_rows)


def update_lineup_player_ids(db) -> int:
    result = db.execute(
        text(
            """
            update lineup_snapshots ls
            set player_id = pa.player_id
            from player_aliases pa
            where pa.source = 'dongqiudi'
              and pa.source_player_id = ls.source_player_id
              and ls.source_player_id is not null
              and ls.player_id is distinct from pa.player_id
            """
        )
    )
    return max(result.rowcount or 0, 0)


def backfill_historical_team_aliases(db) -> dict:
    rows = db.execute(
        text(
            """
            select source, home_team_id as team_id, home_team_name as alias
            from historical_international_matches
            union all
            select source, away_team_id as team_id, away_team_name as alias
            from historical_international_matches
            """
        )
    ).mappings()
    grouped = defaultdict(set)
    for row in rows:
        alias = (row["alias"] or "").strip()
        if alias:
            grouped[(row["source"], alias)].add(row["team_id"])

    alias_rows = []
    ambiguous = []
    for (source, alias), team_ids in grouped.items():
        if len(team_ids) != 1:
            ambiguous.append({"source": source, "alias": alias, "team_ids": sorted(str(item) for item in team_ids)})
            continue
        source_team_id = f"alias:{hashlib.sha256(f'{source}:{alias}'.encode('utf-8')).hexdigest()[:20]}"
        alias_rows.append(
            {
                "team_id": next(iter(team_ids)),
                "source": source,
                "source_team_id": source_team_id,
                "alias": alias,
                "confidence": 0.9,
                "is_primary": False,
            }
        )

    written = 0
    for offset in range(0, len(alias_rows), 1000):
        batch = alias_rows[offset : offset + 1000]
        if not batch:
            continue
        statement = (
            pg_insert(team_aliases)
            .values(batch)
            .on_conflict_do_update(
                index_elements=["source", "alias"],
                set_={
                    "team_id": pg_insert(team_aliases).excluded.team_id,
                    "source_team_id": pg_insert(team_aliases).excluded.source_team_id,
                    "confidence": pg_insert(team_aliases).excluded.confidence,
                    "is_primary": pg_insert(team_aliases).excluded.is_primary,
                },
            )
            .returning(team_aliases.c.id)
        )
        written += len(db.execute(statement).all())
    return {"written": written, "ambiguous": ambiguous}


def player_name_index(db) -> dict[tuple[object, str], set[object]]:
    index = defaultdict(set)
    rows = db.execute(
        select(players.c.id, players.c.team_id, players.c.name_zh, players.c.name_en, player_aliases.c.alias)
        .select_from(players.outerjoin(player_aliases, player_aliases.c.player_id == players.c.id))
    ).mappings()
    for row in rows:
        for candidate in (row["name_zh"], row["name_en"], row["alias"]):
            key = normalize_name(candidate)
            if key:
                index[(row["team_id"], key)].add(row["id"])
    return index


def backfill_injury_player_ids(db) -> dict:
    index = player_name_index(db)
    rows = db.execute(
        select(
            injury_reports.c.id,
            injury_reports.c.team_id,
            injury_reports.c.player_id,
            injury_reports.c.is_model_eligible,
            data_source_links.c.metadata,
        )
        .select_from(
            injury_reports.join(
                data_source_links,
                (data_source_links.c.entity_type == "injury_report")
                & (data_source_links.c.entity_key == injury_reports.c.id.cast(String)),
            )
        )
    ).mappings().all()

    updated = 0
    unmapped_model_eligible = 0
    unmatched_names = []
    for row in rows:
        metadata = row["metadata"] or {}
        player_name = metadata.get("player_name")
        if not player_name:
            continue
        candidates = index.get((row["team_id"], normalize_name(player_name)), set())
        if len(candidates) == 1:
            player_id = next(iter(candidates))
            if row["player_id"] != player_id:
                db.execute(update(injury_reports).where(injury_reports.c.id == row["id"]).values(player_id=player_id))
                updated += 1
            continue
        if row["is_model_eligible"]:
            db.execute(update(injury_reports).where(injury_reports.c.id == row["id"]).values(is_model_eligible=False))
            unmapped_model_eligible += 1
        unmatched_names.append({"report_id": str(row["id"]), "player_name": player_name, "candidate_count": len(candidates)})
    return {
        "updated": updated,
        "unmapped_model_eligible_disabled": unmapped_model_eligible,
        "unmatched_names": unmatched_names,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill canonical team/player identity mappings.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with SessionLocal() as db:
        result = {
            "dry_run": args.dry_run,
            "roster_player_aliases": backfill_roster_player_aliases(db),
            "lineup_player_aliases": backfill_lineup_player_aliases(db),
            "lineup_player_ids_updated": update_lineup_player_ids(db),
            "historical_team_aliases": backfill_historical_team_aliases(db),
            "injury_player_ids": backfill_injury_player_ids(db),
        }
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
