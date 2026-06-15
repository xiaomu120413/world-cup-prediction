from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import httpx
from sqlalchemy import or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.schema import data_source_links, raw_snapshots, team_aliases, teams
from app.db.session import SessionLocal

FIFA_RANKINGS_URL = "https://api.fifa.com/api/v3/rankings?gender=1&count=300"
FIFA_CODE_TO_TEAM_CODE = {
    "ALG": "ALGERIA",
    "ARG": "ARGENTINA",
    "AUS": "AUSTRALIA",
    "AUT": "AUSTRIA",
    "BEL": "BELGIUM",
    "BIH": "BOSNIA-AND-HERZEGOVINA",
    "BRA": "BRA",
    "CAN": "CANADA",
    "CIV": "COTE-D-IVOIRE",
    "CPV": "CABO-VERDE",
    "COL": "COLOMBIA",
    "COD": "CONGO-DR",
    "CRO": "CROATIA",
    "CUW": "CURACAO",
    "CZE": "CZECHIA",
    "ECU": "ECUADOR",
    "EGY": "EGYPT",
    "ENG": "ENG",
    "ESP": "SPAIN",
    "FRA": "FRA",
    "GER": "GERMANY",
    "GHA": "GHANA",
    "HAI": "HAITI",
    "IRN": "IR-IRAN",
    "IRQ": "IRAQ",
    "JOR": "JORDAN",
    "JPN": "JAPAN",
    "KOR": "KOREA-REPUBLIC",
    "KSA": "SAUDI-ARABIA",
    "MAR": "MOROCCO",
    "MEX": "MEXICO",
    "NED": "NETHERLANDS",
    "NOR": "NORWAY",
    "NZL": "NEW-ZEALAND",
    "PAN": "PANAMA",
    "PAR": "PAR",
    "POR": "PORTUGAL",
    "QAT": "QATAR",
    "RSA": "SOUTH-AFRICA",
    "SCO": "SCOTLAND",
    "SEN": "SENEGAL",
    "SUI": "SWITZERLAND",
    "SWE": "SWEDEN",
    "TUN": "TUNISIA",
    "TUR": "TURKIYE",
    "URU": "URUGUAY",
    "USA": "USA",
    "UZB": "UZBEKISTAN",
}


def checksum(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def write_raw_snapshot(db, payload: dict):
    statement = (
        pg_insert(raw_snapshots)
        .values(
            source="fifa",
            source_type="mens_world_ranking",
            source_url=FIFA_RANKINGS_URL,
            checksum=checksum(payload),
            payload=payload,
            parser_version="fifa_mens_world_ranking_v1",
        )
        .on_conflict_do_nothing(index_elements=["source", "source_type", "checksum"])
        .returning(raw_snapshots.c.id)
    )
    inserted = db.execute(statement).scalar_one_or_none()
    if inserted:
        return inserted
    return db.execute(
        select(raw_snapshots.c.id).where(
            raw_snapshots.c.source == "fifa",
            raw_snapshots.c.source_type == "mens_world_ranking",
            raw_snapshots.c.checksum == checksum(payload),
        )
    ).scalar_one()


def english_name(item: dict) -> str | None:
    names = item.get("TeamName") or []
    for name in names:
        if name.get("Locale") in {"en-GB", "en-US", "en"} and name.get("Description"):
            return name["Description"]
    return names[0].get("Description") if names else None


def find_team(db, country_code: str, name: str | None):
    code_candidates = [country_code]
    mapped_code = FIFA_CODE_TO_TEAM_CODE.get(country_code)
    if mapped_code and mapped_code not in code_candidates:
        code_candidates.append(mapped_code)
    team = db.execute(
        select(teams.c.id, teams.c.code)
        .outerjoin(team_aliases, team_aliases.c.team_id == teams.c.id)
        .where(
            or_(
                teams.c.code.in_(code_candidates),
                teams.c.name_en == name,
                teams.c.name_zh == name,
                team_aliases.c.alias == country_code,
                team_aliases.c.alias.in_(code_candidates),
                team_aliases.c.alias == name,
            )
        )
        .order_by(teams.c.code.asc())
        .limit(1)
    ).mappings().first()
    return team


def main() -> None:
    response = httpx.get(
        FIFA_RANKINGS_URL,
        timeout=30.0,
        headers={
            "User-Agent": "world-cup-prediction-bot/0.1 (+low-frequency research collector)",
            "Origin": "https://inside.fifa.com",
            "Referer": "https://inside.fifa.com/fifa-world-ranking/men",
        },
        follow_redirects=True,
    )
    response.raise_for_status()
    payload = response.json()

    with SessionLocal() as db:
        snapshot_id = write_raw_snapshot(db, payload)
        source_links = []
        updated = 0
        unmatched = []
        for item in payload.get("Results", []):
            country_code = item.get("IdCountry")
            name = english_name(item)
            rank = item.get("Rank")
            if not country_code or not rank:
                continue
            team = find_team(db, country_code, name)
            if team is None:
                unmatched.append({"country_code": country_code, "name": name, "rank": rank})
                continue
            db.execute(
                update(teams)
                .where(teams.c.id == team.id)
                .values(
                    fifa_rank=rank,
                    confederation=item.get("ConfederationName"),
                    updated_at=text("now()"),
                )
            )
            db.execute(
                pg_insert(team_aliases)
                .values(
                    team_id=team.id,
                    source="fifa",
                    source_team_id=country_code,
                    alias=country_code,
                    confidence=1.0,
                    is_primary=False,
                )
                .on_conflict_do_nothing()
            )
            source_links.append(
                {
                    "entity_type": "team_fifa_rank",
                    "entity_key": team.code,
                    "source": "fifa",
                    "source_type": "mens_world_ranking",
                    "source_url": FIFA_RANKINGS_URL,
                    "raw_snapshot_id": snapshot_id,
                    "source_record_id": country_code,
                    "confidence": 0.98,
                    "metadata": {
                        "rank": rank,
                        "previous_rank": item.get("PrevRank"),
                        "points": item.get("DecimalTotalPoints"),
                        "pub_date": item.get("PubDate"),
                        "country_code": country_code,
                        "name": name,
                    },
                }
            )
            updated += 1
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
    print(
        json.dumps(
            {
                "ranking_records_read": len(payload.get("Results", [])),
                "teams_updated": updated,
                "source_links": len(source_links),
                "unmatched": unmatched[:20],
                "unmatched_count": len(unmatched),
            },
            ensure_ascii=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
