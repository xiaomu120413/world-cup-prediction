from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import and_, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.collectors.normalizers import normalize_team_ref, slugify
from app.db.schema import (
    competition_stages,
    competitions,
    data_source_links,
    lineup_snapshots,
    matches,
    player_aliases,
    players,
    raw_snapshots,
    team_aliases,
    team_form_snapshots,
    team_match_results,
    teams,
)
from app.db.session import SessionLocal

API_TZ = ZoneInfo("Asia/Shanghai")
SCHEDULE_URL = (
    "https://sport-data.dongqiudi.com/soccer/biz/data/schedule"
    "?season_id=26123&app=dqd&version=853&platform=ios&language=zh-cn&round_all=1"
)
LINEUP_URL_TEMPLATE = "https://sport-data.dongqiudi.com/soccer/biz/match/lineup/{match_id}?app=dqd&lang=zh-cn"


def checksum(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def write_raw_snapshot(db, source: str, source_type: str, source_url: str, payload: dict, parser_version: str):
    statement = (
        pg_insert(raw_snapshots)
        .values(
            source=source,
            source_type=source_type,
            source_url=source_url,
            checksum=checksum(payload),
            payload=payload,
            parser_version=parser_version,
        )
        .on_conflict_do_nothing(index_elements=["source", "source_type", "checksum"])
        .returning(raw_snapshots.c.id)
    )
    inserted = db.execute(statement).scalar_one_or_none()
    if inserted:
        return inserted
    return db.execute(
        select(raw_snapshots.c.id).where(
            and_(
                raw_snapshots.c.source == source,
                raw_snapshots.c.source_type == source_type,
                raw_snapshots.c.checksum == checksum(payload),
            )
        )
    ).scalar_one()


def write_source_links(db, rows: list[dict]) -> int:
    if not rows:
        return 0
    statement = (
        pg_insert(data_source_links)
        .values(rows)
        .on_conflict_do_update(
            index_elements=["entity_type", "entity_key", "source", "source_type"],
            set_={
                "source_url": pg_insert(data_source_links).excluded.source_url,
                "raw_snapshot_id": pg_insert(data_source_links).excluded.raw_snapshot_id,
                "source_record_id": pg_insert(data_source_links).excluded.source_record_id,
                "confidence": pg_insert(data_source_links).excluded.confidence,
                "fetched_at": text("now()"),
                "metadata": pg_insert(data_source_links).excluded["metadata"],
            },
        )
        .returning(data_source_links.c.id)
    )
    return len(db.execute(statement).all())


def fetch_json(url: str) -> dict:
    response = httpx.get(
        url,
        timeout=30.0,
        headers={
            "User-Agent": "world-cup-prediction-bot/0.1 (+low-frequency research collector)",
            "Accept": "application/json",
            "Referer": "https://pc.dongqiudi.com/",
        },
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.json()


def schedule_rows(payload: dict) -> list[dict]:
    rows = []
    for group in payload.get("content", {}).get("matches", []):
        for item in group.get("data", []):
            if isinstance(item, dict) and item.get("match_id"):
                rows.append(item)
    return rows


def normalize_match_id(value: str) -> str:
    return value.removeprefix("dongqiudi-").strip()


def filter_schedule_rows(schedule: list[dict], match_ids: list[str] | None) -> list[dict]:
    if not match_ids:
        return schedule
    allowed = {normalize_match_id(value) for value in match_ids}
    return [item for item in schedule if str(item.get("match_id")) in allowed]


def ensure_competition(db):
    competition_id = db.execute(select(competitions.c.id).where(competitions.c.code == "world_cup_2026")).scalar_one_or_none()
    if competition_id is None:
        competition_id = db.execute(
            pg_insert(competitions)
            .values(
                code="world_cup_2026",
                name="FIFA World Cup 2026",
                host_countries=["Canada", "Mexico", "United States"],
                start_date="2026-06-11",
                end_date="2026-07-19",
            )
            .on_conflict_do_nothing(index_elements=["code"])
            .returning(competitions.c.id)
        ).scalar_one_or_none()
    if competition_id is None:
        competition_id = db.execute(select(competitions.c.id).where(competitions.c.code == "world_cup_2026")).scalar_one()

    stage_id = db.execute(
        select(competition_stages.c.id).where(
            competition_stages.c.competition_id == competition_id,
            competition_stages.c.code == "dongqiudi-schedule",
        )
    ).scalar_one_or_none()
    if stage_id is None:
        stage_id = db.execute(
            pg_insert(competition_stages)
            .values(
                competition_id=competition_id,
                code="dongqiudi-schedule",
                name="Dongqiudi Schedule Context",
                stage_type="group",
                sort_order=98,
            )
            .on_conflict_do_nothing(index_elements=["competition_id", "code"])
            .returning(competition_stages.c.id)
        ).scalar_one_or_none()
    if stage_id is None:
        stage_id = db.execute(
            select(competition_stages.c.id).where(
                competition_stages.c.competition_id == competition_id,
                competition_stages.c.code == "dongqiudi-schedule",
            )
        ).scalar_one()
    return competition_id, stage_id


def team_code_from_name(name: str) -> str:
    normalized = normalize_team_ref(name)
    if normalized is None:
        return f"DQD{hashlib.sha256(name.encode('utf-8')).hexdigest()[:10].upper()}"
    return normalized["code"]


def normalize_match_name(value: str | None) -> str:
    return "".join(ch.lower() for ch in (value or "").strip() if ch.isalnum())


def team_has_roster(db, team_id) -> bool:
    return (
        db.execute(
            select(players.c.id)
            .where(players.c.team_id == team_id, players.c.code.like("DQD-P%"))
            .limit(1)
        ).first()
        is not None
    )


def find_canonical_roster_team(db, name: str):
    target = normalize_match_name(name)
    if not target:
        return None
    rows = db.execute(
        select(
            teams.c.id,
            teams.c.code,
            teams.c.name_zh,
            teams.c.name_en,
            team_aliases.c.alias,
        )
        .select_from(teams.join(players, players.c.team_id == teams.c.id).outerjoin(team_aliases, team_aliases.c.team_id == teams.c.id))
        .where(players.c.code.like("DQD-P%"))
    ).mappings().all()
    for row in rows:
        candidates = {row.name_zh, row.name_en, row.alias}
        if any(normalize_match_name(candidate) == target for candidate in candidates if candidate):
            return {"id": row.id, "code": row.code}
    return None


def link_dongqiudi_team_id(db, team_id, code: str, name: str, source_team_id: str | None) -> None:
    aliases = {name, code}
    source_team_id_updated = 0
    if source_team_id:
        aliases.add(str(source_team_id))
        result = db.execute(
            update(team_aliases)
            .where(team_aliases.c.source == "dongqiudi", team_aliases.c.source_team_id == str(source_team_id))
            .values(team_id=team_id, confidence=1.0, is_primary=False)
        )
        source_team_id_updated = result.rowcount or 0
    for alias in {item.strip() for item in aliases if item and str(item).strip()}:
        if source_team_id and alias == str(source_team_id) and source_team_id_updated:
            continue
        db.execute(
            pg_insert(team_aliases)
            .values(
                team_id=team_id,
                source="dongqiudi",
                source_team_id=str(source_team_id) if source_team_id and alias == str(source_team_id) else f"{code}:{alias}",
                alias=alias,
                confidence=1.0,
                is_primary=alias == code,
            )
            .on_conflict_do_update(
                index_elements=["source", "alias"],
                set_={
                    "team_id": pg_insert(team_aliases).excluded.team_id,
                    "source_team_id": pg_insert(team_aliases).excluded.source_team_id,
                    "confidence": pg_insert(team_aliases).excluded.confidence,
                    "is_primary": pg_insert(team_aliases).excluded.is_primary,
                },
            )
        )


def ensure_team(db, name: str, source_team_id: str | None):
    if source_team_id:
        row = db.execute(
            select(teams.c.id, teams.c.code)
            .select_from(teams.join(team_aliases, team_aliases.c.team_id == teams.c.id))
            .where(team_aliases.c.source == "dongqiudi", team_aliases.c.source_team_id == source_team_id)
            .limit(1)
        ).mappings().first()
        if row and team_has_roster(db, row.id):
            return {"id": row.id, "code": row.code}

    canonical_row = find_canonical_roster_team(db, name)
    if canonical_row:
        link_dongqiudi_team_id(db, canonical_row["id"], canonical_row["code"], name, source_team_id)
        return canonical_row

    alias_row = db.execute(
        select(teams.c.id, teams.c.code)
        .select_from(teams.join(team_aliases, team_aliases.c.team_id == teams.c.id))
        .where(team_aliases.c.source == "dongqiudi", team_aliases.c.alias == name)
        .limit(1)
    ).mappings().first()
    if alias_row:
        if source_team_id:
            db.execute(
                pg_insert(team_aliases)
                .values(
                    team_id=alias_row.id,
                    source="dongqiudi",
                    source_team_id=source_team_id,
                    alias=name,
                    confidence=1.0,
                    is_primary=False,
                )
                .on_conflict_do_nothing()
            )
        return {"id": alias_row.id, "code": alias_row.code}

    normalized = normalize_team_ref(name) or {"code": team_code_from_name(name), "name_zh": name, "name_en": name, "aliases": [name]}
    team_id = db.execute(
        pg_insert(teams)
        .values(code=normalized["code"], name_zh=normalized["name_zh"], name_en=normalized["name_en"], quality_status="source")
        .on_conflict_do_update(
            index_elements=["code"],
            set_={"name_zh": pg_insert(teams).excluded.name_zh, "name_en": pg_insert(teams).excluded.name_en, "updated_at": text("now()")},
        )
        .returning(teams.c.id)
    ).scalar_one()
    for alias in set([name, normalized["code"], *normalized.get("aliases", [])]):
        db.execute(
            pg_insert(team_aliases)
            .values(
                team_id=team_id,
                source="dongqiudi",
                source_team_id=source_team_id if alias == name else f"{normalized['code']}:{alias}",
                alias=alias,
                confidence=1.0,
                is_primary=alias == normalized["code"],
            )
            .on_conflict_do_nothing()
        )
    return {"id": team_id, "code": normalized["code"]}


def parse_kickoff(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    # Dongqiudi's schedule payload exposes start_play alongside date_utc/time_utc.
    # The value is zone-less, so keep it aligned with the UTC fields instead of
    # stamping it as Beijing time.
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def result_for(goals_for: int | None, goals_against: int | None, status: str) -> str:
    if status != "Played" or goals_for is None or goals_against is None:
        return "scheduled"
    if goals_for > goals_against:
        return "win"
    if goals_for < goals_against:
        return "loss"
    return "draw"


def rank_bucket(rank: int | None) -> str:
    if rank is None:
        return "unknown"
    if rank <= 10:
        return "top10"
    if rank <= 30:
        return "top30"
    if rank <= 50:
        return "top50"
    return "other"


def upsert_match_context(db, schedule: list[dict], snapshot_id) -> dict:
    _, stage_id = ensure_competition(db)
    source_links = []
    rows_written = 0
    result_rows = []
    for item in schedule:
        home = ensure_team(db, item["team_A_name"], item.get("team_A_id"))
        away = ensure_team(db, item["team_B_name"], item.get("team_B_id"))
        public_id = f"dongqiudi-{item['match_id']}"
        status = "finished" if item.get("status") == "Played" else "scheduled"
        home_score = int(item["score_A"]) if str(item.get("score_A", "")).isdigit() else None
        away_score = int(item["score_B"]) if str(item.get("score_B", "")).isdigit() else None
        match_id = db.execute(
            pg_insert(matches)
            .values(
                public_id=public_id,
                competition_id=db.execute(select(competition_stages.c.competition_id).where(competition_stages.c.id == stage_id)).scalar_one(),
                stage_id=stage_id,
                home_team_id=home["id"],
                away_team_id=away["id"],
                kickoff_at=parse_kickoff(item["start_play"]),
                status=status,
                home_score=home_score,
                away_score=away_score,
                neutral_site=True,
                source_confidence=0.95,
            )
            .on_conflict_do_update(
                index_elements=["public_id"],
                set_={
                    "home_team_id": pg_insert(matches).excluded.home_team_id,
                    "away_team_id": pg_insert(matches).excluded.away_team_id,
                    "kickoff_at": pg_insert(matches).excluded.kickoff_at,
                    "status": pg_insert(matches).excluded.status,
                    "home_score": pg_insert(matches).excluded.home_score,
                    "away_score": pg_insert(matches).excluded.away_score,
                    "source_confidence": pg_insert(matches).excluded.source_confidence,
                    "updated_at": text("now()"),
                },
            )
            .returning(matches.c.id)
        ).scalar_one()
        rows_written += 1
        source_links.append(
            {
                "entity_type": "match",
                "entity_key": public_id,
                "source": "dongqiudi",
                "source_type": "world_cup_schedule",
                "source_url": SCHEDULE_URL,
                "raw_snapshot_id": snapshot_id,
                "source_record_id": item["match_id"],
                "confidence": 0.95,
                "metadata": {
                    "source_home_team_id": item.get("team_A_id"),
                    "source_away_team_id": item.get("team_B_id"),
                    "status": item.get("status"),
                },
            }
        )
        result_rows.extend(
            team_result_rows(
                db,
                home["id"],
                away["id"],
                item,
                home_score,
                away_score,
                snapshot_id,
                "home",
            )
        )
        result_rows.extend(
            team_result_rows(
                db,
                away["id"],
                home["id"],
                item,
                away_score,
                home_score,
                snapshot_id,
                "away",
            )
        )

    if result_rows:
        db.execute(
            pg_insert(team_match_results)
            .values([row["values"] for row in result_rows])
            .on_conflict_do_update(
                index_elements=["team_id", "source_match_id"],
                set_={
                    "opponent_team_id": pg_insert(team_match_results).excluded.opponent_team_id,
                    "played_at": pg_insert(team_match_results).excluded.played_at,
                    "goals_for": pg_insert(team_match_results).excluded.goals_for,
                    "goals_against": pg_insert(team_match_results).excluded.goals_against,
                    "result": pg_insert(team_match_results).excluded.result,
                    "opponent_rank": pg_insert(team_match_results).excluded.opponent_rank,
                    "opponent_rank_bucket": pg_insert(team_match_results).excluded.opponent_rank_bucket,
                    "snapshot_id": pg_insert(team_match_results).excluded.snapshot_id,
                    "updated_at": text("now()"),
                },
            )
        )
        source_links.extend(row["source_link"] for row in result_rows)
    source_links_written = write_source_links(db, source_links)
    return {"matches_upserted": rows_written, "team_match_results_upserted": len(result_rows), "source_links": source_links_written}


def team_result_rows(db, team_id, opponent_team_id, item: dict, goals_for, goals_against, snapshot_id, side: str) -> list[dict]:
    opponent_rank = db.execute(select(teams.c.fifa_rank).where(teams.c.id == opponent_team_id)).scalar_one_or_none()
    source_match_id = f"{item['match_id']}:{side}"
    values = {
        "team_id": team_id,
        "opponent_team_id": opponent_team_id,
        "played_at": parse_kickoff(item["start_play"]),
        "competition_name": "FIFA World Cup 2026",
        "source_match_id": source_match_id,
        "is_neutral": True,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "result": result_for(goals_for, goals_against, item.get("status")),
        "opponent_rank": opponent_rank,
        "opponent_rank_bucket": rank_bucket(opponent_rank),
        "source_confidence": 0.95,
        "snapshot_id": snapshot_id,
    }
    return [
        {
            "values": values,
            "source_link": {
                "entity_type": "team_match_result",
                "entity_key": f"{team_id}:{source_match_id}",
                "source": "dongqiudi",
                "source_type": "world_cup_schedule",
                "source_url": SCHEDULE_URL,
                "raw_snapshot_id": snapshot_id,
                "source_record_id": source_match_id,
                "confidence": 0.95,
                "metadata": {"source_match_id": item["match_id"], "side": side},
            },
        }
    ]


def estimate_minutes(row: dict, is_starting: bool) -> int | None:
    events = row.get("events") or []
    if is_starting:
        sub_off = next((event for event in events if event.get("code") == "SO"), None)
        return to_int(sub_off.get("minute"), 90) if sub_off else 90
    sub_on = next((event for event in events if event.get("code") == "SI"), None)
    if sub_on:
        return max(0, 90 - to_int(sub_on.get("minute"), 90))
    return 0


def to_int(value, default: int | None = None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_lineup_rows(match_public_id: str, lineup_payload: dict, snapshot_id, db) -> list[dict]:
    match_row = db.execute(
        select(matches.c.id, matches.c.home_team_id, matches.c.away_team_id).where(matches.c.public_id == match_public_id)
    ).mappings().first()
    if match_row is None:
        return []

    template = next((item for item in lineup_payload.get("data", []) if item.get("template") == "match_lineup"), None)
    if not template:
        return []

    rows = []
    payload_data = template.get("data", {})
    sides = {"home": match_row.home_team_id, "away": match_row.away_team_id}
    for side, team_id in sides.items():
        side_payload = payload_data.get(side, {})
        for group_name, is_starting, status in (("start", True, "starter"), ("substitute", False, "substitute"), ("bench", False, "bench")):
            for item in side_payload.get(group_name, []):
                person = item.get("person") or {}
                name = person.get("name")
                if not name:
                    continue
                source_player_id = str(person.get("id")) if person.get("id") else None
                player_id = ensure_player(db, team_id, name, source_player_id, item)
                rows.append(
                    {
                        "match_id": match_row.id,
                        "team_id": team_id,
                        "player_id": player_id,
                        "source_player_id": source_player_id,
                        "player_name": name,
                        "shirt_number": to_int(item.get("shirt_number")),
                        "position": item.get("position"),
                        "is_starting": is_starting,
                        "minutes": estimate_minutes(item, is_starting),
                        "rating": to_float(person.get("rate")),
                        "status": status,
                        "source_confidence": 0.9,
                        "snapshot_id": snapshot_id,
                    }
                )
    return rows


def ensure_player(db, team_id, name: str, source_player_id: str | None, item: dict):
    def link_aliases(player_id, code: str) -> None:
        if not source_player_id:
            return
        aliases = []
        for alias in (name, code):
            if alias and alias not in aliases:
                aliases.append(alias)
        rows = []
        for index, alias in enumerate(aliases):
            is_primary = index == 0
            alias_source_player_id = (
                source_player_id
                if is_primary
                else f"{source_player_id}:{hashlib.sha256(alias.encode('utf-8')).hexdigest()[:12]}"
            )
            rows.append(
                {
                    "player_id": player_id,
                    "team_id": team_id,
                    "source": "dongqiudi",
                    "source_player_id": alias_source_player_id,
                    "alias": alias,
                    "confidence": 0.9,
                    "is_primary": is_primary,
                }
            )
        db.execute(
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
        )

    if source_player_id:
        existing = db.execute(select(players.c.id).where(players.c.code == f"DQD-P{source_player_id}")).scalar_one_or_none()
        if existing:
            link_aliases(existing, f"DQD-P{source_player_id}")
            return existing
    code = f"DQD-P{source_player_id}" if source_player_id else f"DQD-LINEUP-{slugify(name)}"
    player_id = db.execute(
        pg_insert(players)
        .values(
            team_id=team_id,
            code=code,
            name_zh=name,
            name_en=name,
            position=item.get("position"),
            shirt_number=to_int(item.get("shirt_number")),
            quality_status="source",
        )
        .on_conflict_do_update(
            index_elements=["code"],
            set_={
                "team_id": pg_insert(players).excluded.team_id,
                "name_zh": pg_insert(players).excluded.name_zh,
                "position": pg_insert(players).excluded.position,
                "shirt_number": pg_insert(players).excluded.shirt_number,
                "quality_status": pg_insert(players).excluded.quality_status,
                "updated_at": text("now()"),
            },
        )
        .returning(players.c.id)
    ).scalar_one()
    link_aliases(player_id, code)
    return player_id


def upsert_lineups(db, schedule: list[dict], include_scheduled: bool = False) -> dict:
    written = 0
    source_links = []
    fetched = 0
    errors = []
    for item in schedule:
        if item.get("status") != "Played" and not include_scheduled:
            continue
        match_public_id = f"dongqiudi-{item['match_id']}"
        url = LINEUP_URL_TEMPLATE.format(match_id=item["match_id"])
        try:
            payload = fetch_json(url)
        except Exception as exc:
            errors.append({"match_id": match_public_id, "error": str(exc)[:240]})
            continue
        snapshot_id = write_raw_snapshot(
            db,
            "dongqiudi",
            "match_lineup",
            url,
            {"source_match_id": item["match_id"], "lineup": payload},
            "dongqiudi_match_lineup_v1",
        )
        rows = extract_lineup_rows(match_public_id, payload, snapshot_id, db)
        fetched += 1
        if not rows:
            continue
        db.execute(
            pg_insert(lineup_snapshots)
            .values(rows)
            .on_conflict_do_update(
                index_elements=["match_id", "team_id", "source_player_id", "player_name"],
                set_={
                    "player_id": pg_insert(lineup_snapshots).excluded.player_id,
                    "shirt_number": pg_insert(lineup_snapshots).excluded.shirt_number,
                    "position": pg_insert(lineup_snapshots).excluded.position,
                    "is_starting": pg_insert(lineup_snapshots).excluded.is_starting,
                    "minutes": pg_insert(lineup_snapshots).excluded.minutes,
                    "rating": pg_insert(lineup_snapshots).excluded.rating,
                    "status": pg_insert(lineup_snapshots).excluded.status,
                    "source_confidence": pg_insert(lineup_snapshots).excluded.source_confidence,
                    "snapshot_id": pg_insert(lineup_snapshots).excluded.snapshot_id,
                    "updated_at": text("now()"),
                },
            )
        )
        written += len(rows)
        for row in rows:
            player_key = row["source_player_id"] or row["player_name"]
            entity_key = f"{match_public_id}:{row['team_id']}:{player_key}"
            source_links.append(
                {
                    "entity_type": "lineup_snapshot",
                    "entity_key": entity_key,
                    "source": "dongqiudi",
                    "source_type": "match_lineup",
                    "source_url": url,
                    "raw_snapshot_id": snapshot_id,
                    "source_record_id": f"{item['match_id']}:{player_key}",
                    "confidence": 0.9,
                    "metadata": {
                        "match_public_id": match_public_id,
                        "source_match_id": item["match_id"],
                        "is_starting": row["is_starting"],
                        "status": row["status"],
                    },
                }
            )
    links_written = write_source_links(db, source_links)
    return {
        "lineup_matches_fetched": fetched,
        "lineup_rows_upserted": written,
        "lineup_source_links": links_written,
        "lineup_errors": errors[:10],
    }


def update_lineup_stability(db) -> int:
    rows = db.execute(
        select(
            lineup_snapshots.c.team_id,
            lineup_snapshots.c.player_id,
            func.count(lineup_snapshots.c.id).label("starts"),
        )
        .where(lineup_snapshots.c.is_starting.is_(True))
        .group_by(lineup_snapshots.c.team_id, lineup_snapshots.c.player_id)
    ).mappings().all()
    by_team: dict[object, list[int]] = {}
    for row in rows:
        by_team.setdefault(row.team_id, []).append(int(row.starts))

    updated = 0
    for team_id, starts in by_team.items():
        matches_played = max(starts)
        if matches_played <= 0:
            continue
        top_starts = sorted(starts, reverse=True)[:11]
        score = round(10 * sum(top_starts) / (11 * matches_played), 2)
        db.execute(
            update(team_form_snapshots)
            .where(team_form_snapshots.c.team_id == team_id)
            .values(lineup_stability_score=score, data_quality="source")
        )
        updated += 1
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Dongqiudi World Cup schedule, scores and lineup context.")
    parser.add_argument("--match-id", action="append", dest="match_ids", help="Dongqiudi public id or source match_id to refresh. Repeatable.")
    parser.add_argument(
        "--include-scheduled-lineups",
        action="store_true",
        help="Fetch lineup endpoint for scoped scheduled matches, used by the T-90m refresh.",
    )
    args = parser.parse_args()

    schedule_payload = fetch_json(SCHEDULE_URL)
    all_schedule = schedule_rows(schedule_payload)
    schedule = filter_schedule_rows(all_schedule, args.match_ids)
    with SessionLocal() as db:
        schedule_snapshot_id = write_raw_snapshot(
            db,
            "dongqiudi",
            "world_cup_schedule",
            SCHEDULE_URL,
            {"source_url": SCHEDULE_URL, "matches": schedule},
            "dongqiudi_world_cup_schedule_v1",
        )
        result = {
            "schedule_matches_read": len(all_schedule),
            "schedule_matches_scoped": len(schedule),
            "scope_match_ids": args.match_ids or [],
        }
        result.update(upsert_match_context(db, schedule, schedule_snapshot_id))
        result.update(upsert_lineups(db, schedule, include_scheduled=args.include_scheduled_lineups))
        result["lineup_stability_teams_updated"] = update_lineup_stability(db)
        db.commit()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
