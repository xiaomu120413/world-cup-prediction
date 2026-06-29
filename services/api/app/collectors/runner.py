from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import and_, delete, func, insert, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.collectors.adapters import RawSnapshot, build_adapter
from app.collectors.normalizers import canonical_records_from_snapshot, news_items_from_snapshot
from app.db.schema import (
    collector_runs,
    competition_stages,
    competitions,
    data_source_links,
    group_standings,
    matches,
    news_items,
    player_form_snapshots,
    player_aliases,
    players,
    raw_snapshots,
    team_aliases,
    team_form_snapshots,
    teams,
    venues,
)

API_TZ = ZoneInfo("Asia/Shanghai")


def snapshot_checksum(snapshot: RawSnapshot) -> str:
    raw = json.dumps(snapshot.payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class CollectorRunner:
    def __init__(self, db: Session):
        self.db = db

    def run(self, source: str, source_type: str, dry_run: bool = False) -> dict:
        started_at = datetime.now(API_TZ)
        try:
            snapshot = build_adapter(source, source_type).fetch()
            checksum = snapshot_checksum(snapshot)
            if dry_run:
                normalized_records = self.count_normalized_records(snapshot)
                return {
                    "status": "completed",
                    "source": source,
                    "source_type": source_type,
                    "dry_run": True,
                    "records_read": self.count_records(snapshot),
                    "records_written": 0,
                    "normalized_records": normalized_records,
                    "checksum": checksum,
                }

            self.acquire_job_lock(source, source_type)
            snapshot_id, inserted = self.write_snapshot(snapshot, checksum)
            normalized_written = self.write_normalized_records(snapshot, snapshot_id)
            counted_normalized_written = normalized_written if inserted else 0
            self.write_run(
                source=source,
                source_type=source_type,
                status="success",
                started_at=started_at,
                records_read=self.count_records(snapshot),
                records_written=(1 if inserted else 0) + counted_normalized_written,
                snapshot_ids=[snapshot_id],
            )
            self.db.commit()
            return {
                "status": "completed",
                "source": source,
                "source_type": source_type,
                "dry_run": False,
                "records_read": self.count_records(snapshot),
                "records_written": (1 if inserted else 0) + counted_normalized_written,
                "raw_snapshot_written": inserted,
                "normalized_records_written": counted_normalized_written,
                "snapshot_ids": [str(snapshot_id)],
                "checksum": checksum,
            }
        except Exception as exc:
            if not dry_run:
                self.db.rollback()
                self.write_run(
                    source=source,
                    source_type=source_type,
                    status="failed",
                    started_at=started_at,
                    records_read=0,
                    records_written=0,
                    snapshot_ids=[],
                    error_message=str(exc),
                )
                self.db.commit()
            raise

    def acquire_job_lock(self, source: str, source_type: str) -> None:
        self.db.execute(
            text("select pg_advisory_xact_lock(hashtext(:lock_key)::bigint)"),
            {"lock_key": f"collector:{source}:{source_type}"},
        )

    @staticmethod
    def count_records(snapshot: RawSnapshot) -> int:
        total = 0
        for value in snapshot.payload.values():
            if isinstance(value, list):
                total += len(value)
        return total or 1

    @staticmethod
    def count_normalized_records(snapshot: RawSnapshot) -> int:
        canonical = canonical_records_from_snapshot(snapshot)
        return len(news_items_from_snapshot(snapshot)) + sum(len(value) for value in canonical.values())

    def write_snapshot(self, snapshot: RawSnapshot, checksum: str):
        statement = (
            pg_insert(raw_snapshots)
            .values(
                source=snapshot.source,
                source_type=snapshot.source_type,
                source_url=snapshot.source_url,
                checksum=checksum,
                payload=snapshot.payload,
                parser_version=snapshot.parser_version,
            )
            .on_conflict_do_nothing(index_elements=["source", "source_type", "checksum"])
            .returning(raw_snapshots.c.id)
        )
        inserted_id = self.db.execute(statement).scalar_one_or_none()
        if inserted_id is not None:
            return inserted_id, True

        existing_id = self.db.execute(
            select(raw_snapshots.c.id).where(
                raw_snapshots.c.source == snapshot.source,
                raw_snapshots.c.source_type == snapshot.source_type,
                raw_snapshots.c.checksum == checksum,
            )
        ).scalar_one()
        return existing_id, False

    def write_normalized_records(self, snapshot: RawSnapshot, snapshot_id=None) -> int:
        written = self.write_news_items(snapshot)
        self.write_news_source_links(snapshot, snapshot_id)
        canonical = canonical_records_from_snapshot(snapshot)
        if not any(canonical.values()):
            return written

        team_ids = self.upsert_teams(canonical["teams"])
        self.write_source_links(snapshot, snapshot_id, self.team_source_links(canonical["teams"]))
        written += self.upsert_team_aliases(canonical["team_aliases"], team_ids)
        self.write_source_links(snapshot, snapshot_id, self.team_alias_source_links(canonical["team_aliases"]))
        venue_ids = self.upsert_venues(canonical.get("venues", []))
        self.write_source_links(snapshot, snapshot_id, self.venue_source_links(canonical.get("venues", [])))
        stage_ids = self.ensure_stages(canonical["matches"], canonical["standings"])
        written += self.upsert_matches(canonical["matches"], team_ids, stage_ids, venue_ids)
        self.write_source_links(snapshot, snapshot_id, self.match_source_links(canonical["matches"]))
        written += self.replace_standings(canonical["standings"], team_ids, stage_ids, snapshot_id)
        self.write_source_links(snapshot, snapshot_id, self.standing_source_links(canonical["standings"]))
        written += self.replace_team_forms(canonical.get("team_forms", []), team_ids)
        self.write_source_links(snapshot, snapshot_id, self.team_form_source_links(canonical.get("team_forms", [])))
        player_ids = self.upsert_players(canonical["players"], team_ids)
        self.write_source_links(snapshot, snapshot_id, self.player_source_links(canonical["players"]))
        written += self.replace_player_forms(canonical["player_forms"], player_ids, team_ids)
        self.write_source_links(snapshot, snapshot_id, self.player_form_source_links(canonical["player_forms"]))
        return written

    def write_news_items(self, snapshot: RawSnapshot) -> int:
        values = news_items_from_snapshot(snapshot)
        if not values:
            return 0

        statement = (
            pg_insert(news_items)
            .values(values)
            .on_conflict_do_nothing(index_elements=["source_url"])
            .returning(news_items.c.id)
        )
        return len(self.db.execute(statement).all())

    def write_news_source_links(self, snapshot: RawSnapshot, snapshot_id=None) -> int:
        news_values = news_items_from_snapshot(snapshot)
        source_links = [
            {
                "entity_type": "news_item",
                "entity_key": value["source_url"],
                "source_record_id": value["source_url"],
                "confidence": 1.0,
                "metadata": {"title": value["title"]},
            }
            for value in news_values
        ]
        return self.write_source_links(snapshot, snapshot_id, source_links)

    def write_source_links(self, snapshot: RawSnapshot, snapshot_id, values: list[dict]) -> int:
        if not values:
            return 0

        rows = []
        seen = set()
        for value in values:
            key = (value["entity_type"], value["entity_key"], snapshot.source, snapshot.source_type)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "entity_type": value["entity_type"],
                    "entity_key": str(value["entity_key"]),
                    "source": snapshot.source,
                    "source_type": snapshot.source_type,
                    "source_url": snapshot.source_url,
                    "raw_snapshot_id": snapshot_id,
                    "source_record_id": value.get("source_record_id"),
                    "confidence": value.get("confidence", 1.0),
                    "metadata": value.get("metadata", {}),
                }
            )
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
        return len(self.db.execute(statement).all())

    @staticmethod
    def team_source_links(values: list[dict]) -> list[dict]:
        return [
            {
                "entity_type": "team",
                "entity_key": value["code"],
                "source_record_id": value["code"],
                "confidence": 1.0,
                "metadata": {"name": value["name_zh"]},
            }
            for value in values
        ]

    @staticmethod
    def team_alias_source_links(values: list[dict]) -> list[dict]:
        return [
            {
                "entity_type": "team_alias",
                "entity_key": f"{value['source']}:{value['alias']}",
                "source_record_id": value.get("source_team_id"),
                "confidence": value.get("confidence", 1.0),
                "metadata": {"team_code": value["team_code"], "alias": value["alias"]},
            }
            for value in values
        ]

    @staticmethod
    def venue_source_links(values: list[dict]) -> list[dict]:
        return [
            {
                "entity_type": "venue",
                "entity_key": value["code"],
                "source_record_id": value["code"],
                "confidence": 1.0,
                "metadata": {"name": value["name"], "city": value["city"], "country": value["country"]},
            }
            for value in values
        ]

    @staticmethod
    def match_source_links(values: list[dict]) -> list[dict]:
        return [
            {
                "entity_type": "match",
                "entity_key": value["public_id"],
                "source_record_id": value["public_id"],
                "confidence": value.get("source_confidence", 1.0),
                "metadata": {
                    "home_team_code": value["home_team_code"],
                    "away_team_code": value["away_team_code"],
                    "stage_code": value["stage_code"],
                    "kickoff_at": value["kickoff_at"].isoformat(),
                },
            }
            for value in values
        ]

    @staticmethod
    def standing_source_links(values: list[dict]) -> list[dict]:
        return [
            {
                "entity_type": "group_standing",
                "entity_key": f"{value['stage_code']}:{value['team_code']}",
                "source_record_id": f"{value['stage_code']}:{value['team_code']}",
                "confidence": 1.0,
                "metadata": {"rank": value["rank"], "points": value["points"]},
            }
            for value in values
        ]

    @staticmethod
    def team_form_source_links(values: list[dict]) -> list[dict]:
        return [
            {
                "entity_type": "team_form",
                "entity_key": f"{value['team_code']}:{value['as_of_at'].isoformat()}",
                "source_record_id": value["team_code"],
                "confidence": 1.0,
                "metadata": {
                    "recent_matches": value["recent_matches"],
                    "data_quality": value["data_quality"],
                },
            }
            for value in values
        ]

    @staticmethod
    def player_source_links(values: list[dict]) -> list[dict]:
        return [
            {
                "entity_type": "player",
                "entity_key": value["code"],
                "source_record_id": value["code"],
                "confidence": 1.0,
                "metadata": {"team_code": value["team_code"], "name": value["name_zh"]},
            }
            for value in values
        ]

    @staticmethod
    def player_form_source_links(values: list[dict]) -> list[dict]:
        return [
            {
                "entity_type": "player_form",
                "entity_key": f"{value['player_code']}:{value['as_of_at'].isoformat()}",
                "source_record_id": value["player_code"],
                "confidence": 1.0,
                "metadata": {
                    "team_code": value["team_code"],
                    "recent_matches": value["recent_matches"],
                    "source_count": value["source_count"],
                },
            }
            for value in values
        ]

    def upsert_venues(self, values: list[dict]) -> dict[str, object]:
        if not values:
            return {}
        statement = (
            pg_insert(venues)
            .values(values)
            .on_conflict_do_update(
                index_elements=["code"],
                set_={
                    "name": pg_insert(venues).excluded.name,
                    "city": pg_insert(venues).excluded.city,
                    "country": pg_insert(venues).excluded.country,
                    "timezone": pg_insert(venues).excluded.timezone,
                    "capacity": pg_insert(venues).excluded.capacity,
                    "altitude_m": pg_insert(venues).excluded.altitude_m,
                    "surface": pg_insert(venues).excluded.surface,
                    "weather_profile": pg_insert(venues).excluded.weather_profile,
                },
            )
            .returning(venues.c.code, venues.c.id)
        )
        rows = self.db.execute(statement).mappings().all()
        return {row["code"]: row["id"] for row in rows}

    @staticmethod
    def normalize_team_match_key(value: str | None) -> str:
        return "".join(ch.lower() for ch in (value or "").strip() if ch.isalnum())

    def resolve_roster_team_ids(self, values: list[dict]) -> dict[str, object]:
        if not values:
            return {}

        roster_team_ids = select(players.c.team_id).where(players.c.code.like("DQD-P%")).distinct().subquery()
        roster_rows = self.db.execute(
            select(
                teams.c.id,
                teams.c.code,
                teams.c.name_zh,
                teams.c.name_en,
                team_aliases.c.alias,
            )
            .select_from(
                teams.join(roster_team_ids, roster_team_ids.c.team_id == teams.c.id).outerjoin(
                    team_aliases, team_aliases.c.team_id == teams.c.id
                )
            )
        ).mappings()

        index: dict[str, object] = {}
        ambiguous_keys: set[str] = set()
        for row in roster_rows:
            for candidate in (row["code"], row["name_zh"], row["name_en"], row["alias"]):
                key = self.normalize_team_match_key(candidate)
                if not key or key in ambiguous_keys:
                    continue
                if key not in index:
                    index[key] = row["id"]
                elif index[key] != row["id"]:
                    index.pop(key, None)
                    ambiguous_keys.add(key)

        resolved = {}
        for value in values:
            for candidate in (value.get("code"), value.get("name_zh"), value.get("name_en")):
                key = self.normalize_team_match_key(candidate)
                if key in index:
                    team_id = index[key]
                    resolved[value["code"]] = team_id
                    break
        return resolved

    def upsert_teams(self, values: list[dict]) -> dict[str, object]:
        if not values:
            return {}
        team_ids = self.resolve_roster_team_ids(values)
        unresolved_values = [value for value in values if value["code"] not in team_ids]
        if not unresolved_values:
            return team_ids

        statement = (
            pg_insert(teams)
            .values(unresolved_values)
            .on_conflict_do_update(
                index_elements=["code"],
                set_={
                    "name_zh": pg_insert(teams).excluded.name_zh,
                    "name_en": pg_insert(teams).excluded.name_en,
                    "quality_status": pg_insert(teams).excluded.quality_status,
                    "updated_at": text("now()"),
                },
            )
            .returning(teams.c.code, teams.c.id)
        )
        rows = self.db.execute(statement).mappings().all()
        team_ids.update({row["code"]: row["id"] for row in rows})
        return team_ids

    def upsert_team_aliases(self, values: list[dict], team_ids: dict[str, object]) -> int:
        if not values:
            return 0
        rows = []
        seen = set()
        for value in values:
            key = (value["source"], value["alias"])
            team_id = team_ids.get(value["team_code"])
            if team_id is None or key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "team_id": team_id,
                    "source": value["source"],
                    "source_team_id": value["source_team_id"],
                    "alias": value["alias"],
                    "confidence": value["confidence"],
                    "is_primary": value["is_primary"],
                }
            )
        if not rows:
            return 0
        statement = (
            pg_insert(team_aliases)
            .values(rows)
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
        return len(self.db.execute(statement).all())

    @staticmethod
    def source_player_id_from_code(code: str | None) -> str | None:
        if code and code.startswith("DQD-P"):
            return code.removeprefix("DQD-P")
        return None

    @staticmethod
    def player_alias_source_id(source_player_id: str, alias: str, is_primary: bool) -> str:
        if is_primary:
            return source_player_id
        return f"{source_player_id}:{hashlib.sha256(alias.encode('utf-8')).hexdigest()[:12]}"

    def upsert_player_aliases(self, player_values: list[dict], player_ids: dict[str, object]) -> int:
        rows = []
        seen = set()
        for value in player_values:
            player_id = player_ids.get(value["code"])
            source_player_id = self.source_player_id_from_code(value.get("code"))
            if player_id is None or not source_player_id:
                continue

            candidates = []
            for alias in (value.get("name_zh"), value.get("name_en"), value.get("code")):
                if alias and alias not in candidates:
                    candidates.append(alias)
            for index, alias in enumerate(candidates):
                is_primary = index == 0
                source_alias_id = self.player_alias_source_id(source_player_id, alias, is_primary)
                key = ("dongqiudi", source_alias_id)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "player_id": player_id,
                        "team_id": value["team_id"],
                        "source": "dongqiudi",
                        "source_player_id": source_alias_id,
                        "alias": alias,
                        "confidence": 0.95,
                        "is_primary": is_primary,
                    }
                )
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
        return len(self.db.execute(statement).all())

    def ensure_stages(self, match_values: list[dict], standing_values: list[dict]) -> dict[str, object]:
        stage_codes = {item["stage_code"] for item in match_values}
        stage_codes.update(item["stage_code"] for item in standing_values)
        if not stage_codes:
            return {}
        stage_metadata = {
            item["stage_code"]: {
                "name": item.get("stage_name") or item["stage_code"].replace("-", " ").title(),
                "stage_type": item.get("stage_type") or ("group" if item["stage_code"].startswith("group") else "knockout"),
            }
            for item in [*match_values, *standing_values]
        }

        competition_id = self.ensure_default_competition()
        existing = self.db.execute(
            select(competition_stages.c.code, competition_stages.c.id).where(
                and_(
                    competition_stages.c.competition_id == competition_id,
                    competition_stages.c.code.in_(stage_codes),
                )
            )
        ).mappings().all()
        stage_ids = {row["code"]: row["id"] for row in existing}
        for row in existing:
            metadata = stage_metadata.get(row["code"])
            if metadata:
                self.db.execute(
                    competition_stages.update()
                    .where(competition_stages.c.id == row["id"])
                    .values(name=metadata["name"], stage_type=metadata["stage_type"])
                )
        missing = [code for code in stage_codes if code not in stage_ids]
        if missing:
            rows = [
                {
                    "competition_id": competition_id,
                    "code": code,
                    "name": stage_metadata.get(code, {}).get("name", code.replace("-", " ").title()),
                    "stage_type": stage_metadata.get(code, {}).get(
                        "stage_type",
                        "group" if code.startswith("group") else "knockout",
                    ),
                    "sort_order": 1,
                }
                for code in missing
            ]
            inserted = (
                pg_insert(competition_stages)
                .values(rows)
                .on_conflict_do_nothing(index_elements=["competition_id", "code"])
                .returning(competition_stages.c.code, competition_stages.c.id)
            )
            for row in self.db.execute(inserted).mappings().all():
                stage_ids[row["code"]] = row["id"]
        return stage_ids

    def ensure_default_competition(self):
        statement = (
            pg_insert(competitions)
            .values(
                code="world_cup_2026",
                name="World Cup 2026",
                host_countries=["United States", "Canada", "Mexico"],
                start_date=date(2026, 6, 11),
                end_date=date(2026, 7, 19),
            )
            .on_conflict_do_update(
                index_elements=["code"],
                set_={"updated_at": text("now()")},
            )
            .returning(competitions.c.id)
        )
        return self.db.execute(statement).scalar_one()

    def upsert_matches(
        self,
        values: list[dict],
        team_ids: dict[str, object],
        stage_ids: dict[str, object],
        venue_ids: dict[str, object] | None = None,
    ) -> int:
        rows = []
        competition_id = self.ensure_default_competition() if values else None
        venue_ids = venue_ids or {}
        for value in values:
            home_team_id = team_ids.get(value["home_team_code"])
            away_team_id = team_ids.get(value["away_team_code"])
            stage_id = stage_ids.get(value["stage_code"])
            if home_team_id is None or away_team_id is None or stage_id is None:
                continue
            rows.append(
                {
                    "public_id": value["public_id"],
                    "competition_id": competition_id,
                    "stage_id": stage_id,
                    "home_team_id": home_team_id,
                    "away_team_id": away_team_id,
                    "venue_id": venue_ids.get(value.get("venue_code")),
                    "kickoff_at": value["kickoff_at"],
                    "status": value["status"],
                    "home_score": value["home_score"],
                    "away_score": value["away_score"],
                    "neutral_site": value["neutral_site"],
                    "source_confidence": value["source_confidence"],
                }
            )
        if not rows:
            return 0
        statement = (
            pg_insert(matches)
            .values(rows)
            .on_conflict_do_update(
                index_elements=["public_id"],
                set_={
                    "stage_id": pg_insert(matches).excluded.stage_id,
                    "home_team_id": pg_insert(matches).excluded.home_team_id,
                    "away_team_id": pg_insert(matches).excluded.away_team_id,
                    "venue_id": pg_insert(matches).excluded.venue_id,
                    "kickoff_at": pg_insert(matches).excluded.kickoff_at,
                    "status": pg_insert(matches).excluded.status,
                    "home_score": pg_insert(matches).excluded.home_score,
                    "away_score": pg_insert(matches).excluded.away_score,
                    "neutral_site": pg_insert(matches).excluded.neutral_site,
                    "source_confidence": pg_insert(matches).excluded.source_confidence,
                    "updated_at": text("now()"),
                },
            )
            .returning(matches.c.id)
        )
        return len(self.db.execute(statement).all())

    def replace_standings(
        self,
        values: list[dict],
        team_ids: dict[str, object],
        stage_ids: dict[str, object],
        snapshot_id,
    ) -> int:
        rows = []
        for value in values:
            stage_id = stage_ids.get(value["stage_code"])
            team_id = team_ids.get(value["team_code"])
            if stage_id is None or team_id is None:
                continue
            rows.append(
                {
                    "stage_id": stage_id,
                    "team_id": team_id,
                    "played": value["played"],
                    "wins": value["wins"],
                    "draws": value["draws"],
                    "losses": value["losses"],
                    "goals_for": value["goals_for"],
                    "goals_against": value["goals_against"],
                    "goal_diff": value["goal_diff"],
                    "points": value["points"],
                    "rank": value["rank"],
                    "snapshot_id": snapshot_id,
                }
            )
        if not rows:
            return 0

        stage_ids_to_replace = {row["stage_id"] for row in rows}
        self.db.execute(delete(group_standings).where(group_standings.c.stage_id.in_(stage_ids_to_replace)))
        self.db.execute(insert(group_standings), rows)
        return len(rows)

    def replace_team_forms(self, values: list[dict], team_ids: dict[str, object]) -> int:
        rows = []
        for value in values:
            team_id = team_ids.get(value["team_code"])
            if team_id is None:
                continue
            rows.append(
                {
                    "team_id": team_id,
                    "as_of_at": value["as_of_at"],
                    "recent_matches": value["recent_matches"],
                    "points_per_match": value["points_per_match"],
                    "goals_for_per_match": value["goals_for_per_match"],
                    "goals_against_per_match": value["goals_against_per_match"],
                    "lineup_stability_score": value["lineup_stability_score"],
                    "injury_impact_score": value["injury_impact_score"],
                    "data_quality": value["data_quality"],
                }
            )
        if not rows:
            return 0
        for row in rows:
            self.db.execute(
                delete(team_form_snapshots).where(
                    and_(
                        team_form_snapshots.c.team_id == row["team_id"],
                        team_form_snapshots.c.as_of_at == row["as_of_at"],
                    )
                )
            )
        self.db.execute(insert(team_form_snapshots), rows)
        return len(rows)

    def upsert_players(self, values: list[dict], team_ids: dict[str, object]) -> dict[str, object]:
        rows = []
        for value in values:
            team_id = team_ids.get(value["team_code"])
            if team_id is None:
                continue
            rows.append(
                {
                    "team_id": team_id,
                    "code": value["code"],
                    "name_zh": value["name_zh"],
                    "name_en": value["name_en"],
                    "position": value["position"],
                    "shirt_number": value["shirt_number"],
                    "club_name": value["club_name"],
                    "market_value_eur": value["market_value_eur"],
                    "is_key_player": value["is_key_player"],
                    "quality_status": value["quality_status"],
                }
            )
        if not rows:
            return {}
        statement = (
            pg_insert(players)
            .values(rows)
            .on_conflict_do_update(
                index_elements=["code"],
                set_={
                    "team_id": pg_insert(players).excluded.team_id,
                    "name_zh": pg_insert(players).excluded.name_zh,
                    "name_en": func.coalesce(pg_insert(players).excluded.name_en, players.c.name_en),
                    "position": func.coalesce(pg_insert(players).excluded.position, players.c.position),
                    "shirt_number": func.coalesce(pg_insert(players).excluded.shirt_number, players.c.shirt_number),
                    "club_name": func.coalesce(pg_insert(players).excluded.club_name, players.c.club_name),
                    "market_value_eur": func.coalesce(pg_insert(players).excluded.market_value_eur, players.c.market_value_eur),
                    "is_key_player": pg_insert(players).excluded.is_key_player,
                    "quality_status": pg_insert(players).excluded.quality_status,
                    "updated_at": text("now()"),
                },
            )
            .returning(players.c.code, players.c.id)
        )
        player_rows = self.db.execute(statement).mappings().all()
        player_ids = {row["code"]: row["id"] for row in player_rows}
        self.upsert_player_aliases(rows, player_ids)
        return player_ids

    def replace_player_forms(
        self,
        values: list[dict],
        player_ids: dict[str, object],
        team_ids: dict[str, object],
    ) -> int:
        rows = []
        for value in values:
            player_id = player_ids.get(value["player_code"])
            team_id = team_ids.get(value["team_code"])
            if player_id is None or team_id is None:
                continue
            rows.append(
                {
                    "player_id": player_id,
                    "team_id": team_id,
                    "as_of_at": value["as_of_at"],
                    "recent_matches": value["recent_matches"],
                    "minutes": value["minutes"],
                    "goals": value["goals"],
                    "assists": value["assists"],
                    "shots": value["shots"],
                    "key_passes": value["key_passes"],
                    "rating": value["rating"],
                    "availability_status": value["availability_status"],
                    "form_score": value["form_score"],
                    "source_count": value["source_count"],
                }
            )
        if not rows:
            return 0
        for row in rows:
            self.db.execute(
                delete(player_form_snapshots).where(
                    and_(
                        player_form_snapshots.c.player_id == row["player_id"],
                        player_form_snapshots.c.as_of_at == row["as_of_at"],
                    )
                )
            )
        self.db.execute(insert(player_form_snapshots), rows)
        return len(rows)

    def write_run(
        self,
        source: str,
        source_type: str,
        status: str,
        started_at: datetime,
        records_read: int,
        records_written: int,
        snapshot_ids: list,
        error_message: str | None = None,
    ) -> None:
        self.db.execute(
            insert(collector_runs).values(
                source=source,
                job_type=source_type,
                status=status,
                started_at=started_at,
                finished_at=datetime.now(API_TZ),
                records_read=records_read,
                records_written=records_written,
                error_message=error_message,
                snapshot_ids=snapshot_ids,
            )
        )
