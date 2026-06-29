from __future__ import annotations

import hashlib
import json
import sys
import unicodedata
from pathlib import Path

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.schema import data_source_links, injury_reports, player_aliases, players, raw_snapshots, teams
from app.db.session import SessionLocal


VERIFIED_INJURY_ITEMS = [
    {
        "team": "Germany",
        "player_name": "Lennart Karl",
        "report_type": "injury",
        "status": "confirmed",
        "impact_score": -0.7,
        "source_url": "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/lennart-karl-germany-injury-withdrawal",
        "evidence_text": "FIFA reported that Lennart Karl was injured in training and ruled out of Germany's World Cup squad.",
        "confidence": 0.92,
    },
    {
        "team": "Brazil",
        "player_name": "Neymar",
        "report_type": "injury",
        "status": "doubtful",
        "impact_score": -0.8,
        "source_url": "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/brazil-neymar-injury",
        "evidence_text": "FIFA reported a Brazil injury blow for Neymar with a calf problem and an expected short-term absence window.",
        "confidence": 0.9,
    },
    {
        "team": "Japan",
        "player_name": "Wataru Endo",
        "report_type": "injury",
        "status": "confirmed",
        "impact_score": -0.85,
        "source_url": "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/japan-captain-endo-ruled-out-injury",
        "evidence_text": "FIFA reported that Japan captain Wataru Endo withdrew from the World Cup because of a foot injury.",
        "confidence": 0.92,
    },
    {
        "team": "Brazil",
        "player_name": "Wesley",
        "report_type": "injury",
        "status": "confirmed",
        "impact_score": -0.35,
        "source_url": "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/brazil-call-up-ederson-wesley-ancelotti",
        "evidence_text": "FIFA reported that Brazil planned to call up Ederson after Wesley withdrew from the squad.",
        "confidence": 0.9,
    },
    {
        "team": "Canada",
        "player_name": "Ismaël Koné",
        "report_type": "injury",
        "status": "confirmed",
        "impact_score": -0.8,
        "source": "guardian",
        "source_url": "https://www.theguardian.com/football/2026/jun/18/ismael-kone-injury-reaction-canada",
        "evidence_text": "The Guardian reported that Canada midfielder Ismaël Koné suffered a broken leg during the World Cup match against Qatar.",
        "confidence": 0.9,
    },
    {
        "team": "Canada",
        "player_name": "Stephen Eustáquio",
        "report_type": "injury",
        "status": "doubtful",
        "impact_score": -0.35,
        "source": "guardian",
        "source_url": "https://www.theguardian.com/football/2026/jun/28/alphonso-davies-returns-canada-world-cup-moment-of-destiny",
        "evidence_text": "The Guardian reported that Stephen Eustáquio missed Canada's match because of muscle fatigue.",
        "confidence": 0.86,
    },
    {
        "team": "South Africa",
        "player_name": "Themba Zwane",
        "report_type": "suspension",
        "status": "suspended",
        "impact_score": -0.7,
        "source": "espn",
        "source_url": "https://www.espn.com/espn/story/_/id/49097656/south-africa-themba-zwane-handed-three-match-ban-red-card-mexico-fifa-world-cup-opener",
        "evidence_text": "ESPN reported that South Africa's Themba Zwane received a three-match ban after being sent off in the opener against Mexico.",
        "confidence": 0.9,
    },
]


def checksum(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def write_raw_snapshot(db, payload: dict):
    statement = (
        pg_insert(raw_snapshots)
        .values(
            source="verified_public_news",
            source_type="verified_injury_news",
            source_url="multiple-public-sources",
            checksum=checksum(payload),
            payload=payload,
            parser_version="verified_injury_news_v2",
        )
        .on_conflict_do_nothing(index_elements=["source", "source_type", "checksum"])
        .returning(raw_snapshots.c.id)
    )
    inserted = db.execute(statement).scalar_one_or_none()
    if inserted:
        return inserted
    return db.execute(
        select(raw_snapshots.c.id).where(
            raw_snapshots.c.source == "verified_public_news",
            raw_snapshots.c.source_type == "verified_injury_news",
            raw_snapshots.c.checksum == checksum(payload),
        )
    ).scalar_one()


def find_team_id(db, team_name: str):
    return db.execute(
        text(
            """
            select t.id
            from teams t
            where t.name_en = :name or t.name_zh = :name or t.code = upper(:name)
               or exists (
                   select 1 from team_aliases a
                   where a.team_id = t.id and a.alias = :name
               )
            order by case when t.fifa_rank is null then 1 else 0 end, t.code
            limit 1
            """
        ),
        {"name": team_name},
    ).scalar_one_or_none()


def normalize_name(value: str | None) -> str:
    ascii_value = unicodedata.normalize("NFKD", (value or "").strip()).encode("ascii", "ignore").decode("ascii")
    return "".join(ch.lower() for ch in ascii_value if ch.isalnum())


def find_player_id(db, team_id, player_name: str):
    target = normalize_name(player_name)
    if not target:
        return None
    rows = db.execute(
        select(players.c.id, players.c.name_zh, players.c.name_en, player_aliases.c.alias)
        .select_from(players.outerjoin(player_aliases, player_aliases.c.player_id == players.c.id))
        .where(players.c.team_id == team_id)
    ).mappings().all()
    candidates = set()
    for row in rows:
        if any(normalize_name(value) == target for value in (row.name_zh, row.name_en, row.alias) if value):
            candidates.add(row.id)
    return next(iter(candidates)) if len(candidates) == 1 else None


def main() -> None:
    payload = {"items": VERIFIED_INJURY_ITEMS}
    with SessionLocal() as db:
        snapshot_id = write_raw_snapshot(db, payload)
        source_urls = [item["source_url"] for item in VERIFIED_INJURY_ITEMS]
        db.execute(
            text(
                """
                delete from data_source_links dsl
                where dsl.entity_type = 'injury_report'
                  and not exists (
                    select 1 from injury_reports ir
                    where ir.id::text = dsl.entity_key
                  )
                """
            )
        )
        existing_report_ids = [
            str(row.id)
            for row in db.execute(select(injury_reports.c.id).where(injury_reports.c.source_url.in_(source_urls))).mappings()
        ]
        if existing_report_ids:
            db.execute(
                delete(data_source_links).where(
                    data_source_links.c.entity_type == "injury_report",
                    data_source_links.c.entity_key.in_(existing_report_ids),
                )
            )
        db.execute(delete(injury_reports).where(injury_reports.c.source_url.in_(source_urls)))
        report_ids = []
        source_links = []
        for item in VERIFIED_INJURY_ITEMS:
            team_id = find_team_id(db, item["team"])
            if team_id is None:
                continue
            player_id = find_player_id(db, team_id, item["player_name"])
            report_id = db.execute(
                pg_insert(injury_reports)
                .values(
                    team_id=team_id,
                    player_id=player_id,
                    report_type=item["report_type"],
                    status=item["status"],
                    impact_score=item["impact_score"],
                    source_url=item["source_url"],
                    confidence=item["confidence"],
                    evidence_text=item["evidence_text"],
                    is_model_eligible=item["confidence"] >= 0.85,
                )
                .returning(injury_reports.c.id)
            ).scalar_one()
            report_ids.append(report_id)
            source_links.append(
                {
                    "entity_type": "injury_report",
                    "entity_key": str(report_id),
                    "source": item.get("source", "fifa"),
                    "source_type": "verified_injury_news",
                    "source_url": item["source_url"],
                    "raw_snapshot_id": snapshot_id,
                    "source_record_id": f"{item['team']}:{item['player_name']}",
                    "confidence": item["confidence"],
                    "metadata": {
                        "team": item["team"],
                        "player_name": item["player_name"],
                        "player_id": str(player_id) if player_id else None,
                        "status": item["status"],
                    },
                }
            )
        if source_links:
            db.execute(
                pg_insert(data_source_links)
                .values(source_links)
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
            )
        db.commit()
    print(json.dumps({"injury_reports_upserted": len(report_ids), "source_links": len(source_links)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
