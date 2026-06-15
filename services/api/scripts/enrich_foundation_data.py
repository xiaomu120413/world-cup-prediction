from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import and_, delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.schema import coaches, data_source_links, players, raw_snapshots, teams, venues, weather_snapshots
from app.db.session import SessionLocal

API_TZ = ZoneInfo("Asia/Shanghai")
FIFA_STADIUM_INFO_URL = (
    "https://www.fifa.com/en/tournaments/mens/worldcup/"
    "canadamexicousa2026/articles/stadium-information-details"
)
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
FIFA_SQUAD_LIST_URL = "https://fdp.fifa.org/assetspublic/ce281/pdf/SquadLists-English.pdf"

FIFA_CODE_TO_TEAM_NAME = {
    "ALG": "阿尔及利亚",
    "ARG": "阿根廷",
    "AUS": "澳大利亚",
    "AUT": "奥地利",
    "BEL": "比利时",
    "BIH": "波黑",
    "BRA": "Brazil",
    "CAN": "加拿大",
    "CIV": "科特迪瓦",
    "COD": "刚果民主共和国",
    "COL": "哥伦比亚",
    "CPV": "佛得角",
    "CRO": "克罗地亚",
    "CUW": "库拉索",
    "CZE": "捷克",
    "ECU": "厄瓜多尔",
    "EGY": "埃及",
    "ENG": "England",
    "ESP": "西班牙",
    "FRA": "France",
    "GER": "德国",
    "GHA": "加纳",
    "HAI": "海地",
    "IRN": "伊朗",
    "IRQ": "伊拉克",
    "JOR": "约旦",
    "JPN": "日本",
    "KOR": "韩国",
    "KSA": "沙特阿拉伯",
    "MAR": "摩洛哥",
    "MEX": "墨西哥",
    "NED": "荷兰",
    "NOR": "挪威",
    "NZL": "新西兰",
    "PAN": "巴拿马",
    "PAR": "Paraguay",
    "POR": "葡萄牙",
    "QAT": "卡塔尔",
    "RSA": "南非",
    "SCO": "苏格兰",
    "SEN": "塞内加尔",
    "SUI": "瑞士",
    "SWE": "瑞典",
    "TUN": "突尼斯",
    "TUR": "土耳其",
    "URU": "乌拉圭",
    "USA": "United States",
    "UZB": "乌兹别克斯坦",
}


VENUE_ENRICHMENT = [
    {
        "code": "arrowhead-stadium",
        "capacity": 73000,
        "latitude": 39.0489,
        "longitude": -94.4839,
        "surface": "natural grass (tournament)",
        "roof_type": "open_air",
    },
    {
        "code": "at-t-stadium",
        "capacity": 94000,
        "latitude": 32.7473,
        "longitude": -97.0945,
        "surface": "natural grass (tournament)",
        "roof_type": "retractable_roof",
    },
    {
        "code": "bc-place",
        "capacity": 54000,
        "latitude": 49.2768,
        "longitude": -123.1119,
        "surface": "natural grass (tournament)",
        "roof_type": "retractable_roof",
    },
    {
        "code": "bmo-field",
        "capacity": 45000,
        "latitude": 43.6332,
        "longitude": -79.4186,
        "surface": "natural grass (tournament)",
        "roof_type": "open_air",
    },
    {
        "code": "estadio-akron",
        "capacity": 48000,
        "latitude": 20.6818,
        "longitude": -103.4622,
        "surface": "natural grass",
        "roof_type": "open_air",
    },
    {
        "code": "estadio-azteca",
        "capacity": 83000,
        "latitude": 19.3029,
        "longitude": -99.1504,
        "surface": "natural grass",
        "roof_type": "open_air",
    },
    {
        "code": "estadio-bbva",
        "capacity": 53500,
        "latitude": 25.6687,
        "longitude": -100.2447,
        "surface": "natural grass",
        "roof_type": "open_air",
    },
    {
        "code": "gillette-stadium",
        "capacity": 65000,
        "latitude": 42.0909,
        "longitude": -71.2643,
        "surface": "natural grass (tournament)",
        "roof_type": "open_air",
    },
    {
        "code": "hard-rock-stadium",
        "capacity": 65000,
        "latitude": 25.9580,
        "longitude": -80.2389,
        "surface": "natural grass",
        "roof_type": "open_air_partial_canopy",
    },
    {
        "code": "levi-s-stadium",
        "capacity": 71000,
        "latitude": 37.4032,
        "longitude": -121.9698,
        "surface": "natural grass",
        "roof_type": "open_air",
    },
    {
        "code": "lincoln-financial-field",
        "capacity": 69000,
        "latitude": 39.9008,
        "longitude": -75.1675,
        "surface": "natural grass",
        "roof_type": "open_air",
    },
    {
        "code": "lumen-field",
        "capacity": 69000,
        "latitude": 47.5952,
        "longitude": -122.3316,
        "surface": "natural grass (tournament)",
        "roof_type": "open_air_partial_roof",
    },
    {
        "code": "mercedes-benz-stadium",
        "capacity": 75000,
        "latitude": 33.7554,
        "longitude": -84.4008,
        "surface": "natural grass (tournament)",
        "roof_type": "retractable_roof",
    },
    {
        "code": "metlife-stadium",
        "capacity": 82500,
        "latitude": 40.8135,
        "longitude": -74.0745,
        "surface": "natural grass (tournament)",
        "roof_type": "open_air",
    },
    {
        "code": "nrg-stadium",
        "capacity": 72000,
        "latitude": 29.6847,
        "longitude": -95.4107,
        "surface": "natural grass (tournament)",
        "roof_type": "retractable_roof",
    },
    {
        "code": "sofi-stadium",
        "capacity": 70000,
        "latitude": 33.9535,
        "longitude": -118.3392,
        "surface": "natural grass (tournament)",
        "roof_type": "fixed_roof_open_sides",
    },
]


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


def write_source_links(db, snapshot_id, rows: list[dict]) -> int:
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


def enrich_venues(db) -> dict:
    payload = {
        "as_of_at": datetime.now(API_TZ).isoformat(),
        "source_note": "FIFA-published tournament capacities plus manually verified stadium coordinates for weather joins.",
        "venues": VENUE_ENRICHMENT,
    }
    snapshot_id = write_raw_snapshot(
        db,
        "manual_verified",
        "venue_enrichment",
        FIFA_STADIUM_INFO_URL,
        payload,
        "venue_enrichment_v1",
    )
    existing = {
        row.code: row.id
        for row in db.execute(select(venues.c.code, venues.c.id).where(venues.c.code.in_([v["code"] for v in VENUE_ENRICHMENT]))).all()
    }
    updated = 0
    source_links = []
    for item in VENUE_ENRICHMENT:
        venue_id = existing.get(item["code"])
        if venue_id is None:
            continue
        db.execute(
            update(venues)
            .where(venues.c.id == venue_id)
            .values(
                capacity=item["capacity"],
                surface=item["surface"],
                weather_profile={
                    "latitude": item["latitude"],
                    "longitude": item["longitude"],
                    "roof_type": item["roof_type"],
                    "profile_quality": "manual_verified_partial",
                    "source_url": FIFA_STADIUM_INFO_URL,
                },
            )
        )
        updated += 1
        source_links.append(
            {
                "entity_type": "venue",
                "entity_key": item["code"],
                "source": "manual_verified",
                "source_type": "venue_enrichment",
                "source_url": FIFA_STADIUM_INFO_URL,
                "raw_snapshot_id": snapshot_id,
                "source_record_id": item["code"],
                "confidence": 0.9,
                "metadata": {
                    "capacity": item["capacity"],
                    "surface": item["surface"],
                    "latitude": item["latitude"],
                    "longitude": item["longitude"],
                    "roof_type": item["roof_type"],
                },
            }
        )

    db.execute(data_source_links.delete().where(data_source_links.c.entity_key == "los-angeles"))
    db.execute(delete(venues).where(venues.c.code == "los-angeles"))
    source_links_written = write_source_links(db, snapshot_id, source_links)
    return {"venues_enriched": updated, "venue_source_links": source_links_written}


def fetch_open_meteo_weather(venue_rows: list[dict]) -> tuple[str, list[dict]]:
    results = []
    for row in venue_rows:
        profile = row["weather_profile"] or {}
        latitude = profile.get("latitude")
        longitude = profile.get("longitude")
        if latitude is None or longitude is None:
            continue
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m",
            "timezone": "UTC",
            "wind_speed_unit": "kmh",
        }
        response = httpx.get(OPEN_METEO_URL, params=params, timeout=20.0)
        response.raise_for_status()
        results.append(
            {
                "venue_code": row["code"],
                "source_url": str(response.url),
                "response": response.json(),
            }
        )
    return OPEN_METEO_URL, results


def write_weather_snapshots(db) -> dict:
    venue_rows = db.execute(
        select(venues.c.id, venues.c.code, venues.c.weather_profile).where(venues.c.weather_profile.is_not(None))
    ).mappings().all()
    source_url, weather_payloads = fetch_open_meteo_weather([dict(row) for row in venue_rows])
    payload = {"as_of_at": datetime.now(API_TZ).isoformat(), "items": weather_payloads}
    snapshot_id = write_raw_snapshot(
        db,
        "open_meteo",
        "venue_current_weather",
        source_url,
        payload,
        "open_meteo_current_weather_v1",
    )
    venue_ids = {row.code: row.id for row in venue_rows}
    rows = []
    source_links = []
    for item in weather_payloads:
        current = item["response"].get("current", {})
        observed_at = datetime.fromisoformat(current["time"].replace("Z", "+00:00")).replace(tzinfo=ZoneInfo("UTC"))
        venue_id = venue_ids[item["venue_code"]]
        row = {
            "venue_id": venue_id,
            "observed_at": observed_at,
            "provider": "open_meteo",
            "temperature_c": current.get("temperature_2m"),
            "humidity_pct": current.get("relative_humidity_2m"),
            "precipitation_mm": current.get("precipitation"),
            "wind_speed_kph": current.get("wind_speed_10m"),
            "wind_direction_deg": current.get("wind_direction_10m"),
            "weather_code": current.get("weather_code"),
            "source_url": item["source_url"],
            "data_quality": "current_observation_not_matchday",
        }
        rows.append(row)
        entity_key = f"{item['venue_code']}:{observed_at.isoformat().replace('+00:00', '+00:00')}"
        source_links.append(
            {
                "entity_type": "weather_snapshot",
                "entity_key": entity_key,
                "source": "open_meteo",
                "source_type": "venue_current_weather",
                "source_url": item["source_url"],
                "raw_snapshot_id": snapshot_id,
                "source_record_id": entity_key,
                "confidence": 0.85,
                "metadata": {"venue_code": item["venue_code"], "data_quality": "current_observation_not_matchday"},
            }
        )
    if rows:
        statement = (
            pg_insert(weather_snapshots)
            .values(rows)
            .on_conflict_do_update(
                index_elements=["venue_id", "provider", "observed_at"],
                set_={
                    "temperature_c": pg_insert(weather_snapshots).excluded.temperature_c,
                    "humidity_pct": pg_insert(weather_snapshots).excluded.humidity_pct,
                    "precipitation_mm": pg_insert(weather_snapshots).excluded.precipitation_mm,
                    "wind_speed_kph": pg_insert(weather_snapshots).excluded.wind_speed_kph,
                    "wind_direction_deg": pg_insert(weather_snapshots).excluded.wind_direction_deg,
                    "weather_code": pg_insert(weather_snapshots).excluded.weather_code,
                    "source_url": pg_insert(weather_snapshots).excluded.source_url,
                    "data_quality": pg_insert(weather_snapshots).excluded.data_quality,
                },
            )
        )
        db.execute(statement)
    links_written = write_source_links(db, snapshot_id, source_links)
    return {"weather_snapshots": len(rows), "weather_source_links": links_written}


def aggregate_team_market_values(db) -> dict:
    latest_market_snapshot = db.execute(
        select(raw_snapshots.c.id)
        .where(raw_snapshots.c.source == "dongqiudi", raw_snapshots.c.source_type == "world_cup_player_rankings")
        .order_by(raw_snapshots.c.fetched_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    rows = db.execute(
        select(
            teams.c.id,
            teams.c.code,
            func.sum(players.c.market_value_eur).label("market_value_eur"),
            func.count(players.c.id).label("player_count"),
        )
        .select_from(teams.join(players, players.c.team_id == teams.c.id))
        .where(players.c.market_value_eur.is_not(None))
        .group_by(teams.c.id, teams.c.code)
    ).mappings().all()

    source_links = []
    for row in rows:
        db.execute(update(teams).where(teams.c.id == row.id).values(market_value_eur=row.market_value_eur, updated_at=text("now()")))
        source_links.append(
            {
                "entity_type": "team_market_value",
                "entity_key": row.code,
                "source": "dongqiudi",
                "source_type": "derived_player_market_values",
                "source_url": "https://sport-data.dongqiudi.com/soccer/biz/data/market_value_ranking",
                "raw_snapshot_id": latest_market_snapshot,
                "source_record_id": row.code,
                "confidence": 0.65,
                "metadata": {
                    "player_count": int(row.player_count),
                    "aggregation": "sum_matched_player_market_value_eur",
                    "quality": "partial_roster_coverage",
                },
            }
        )
    links_written = write_source_links(db, latest_market_snapshot, source_links)
    return {"team_market_values": len(rows), "team_market_value_source_links": links_written}


def extract_fifa_squad_text() -> str:
    pdf_path = Path(__file__).resolve().parents[1] / ".tmp-fifa-squad-list.pdf"
    txt_path = Path(__file__).resolve().parents[1] / ".tmp-fifa-squad-list.txt"
    response = httpx.get(FIFA_SQUAD_LIST_URL, timeout=60.0, follow_redirects=True)
    response.raise_for_status()
    pdf_path.write_bytes(response.content)
    subprocess.run(["pdftotext", "-layout", str(pdf_path), str(txt_path)], check=True)
    return txt_path.read_text(encoding="utf-8", errors="replace")


def normalize_official_name(value: str) -> str:
    return " ".join(value.split())


def parse_fifa_squad_list(text_value: str) -> dict:
    teams_payload = []
    for page in text_value.split("\f"):
        team_match = re.search(r"([A-Za-z][A-Za-z\s\-]+?)\s*\(([A-Z]{3})\)", page)
        coach_match = re.search(r"Head coach\s+(.+?)(?:\s{2,}|\n)", page)
        if not team_match:
            continue
        fifa_code = team_match.group(2)
        players_payload = []
        for line in page.splitlines():
            player_match = re.match(r"^\s*(\d{1,2})\s+(GK|DF|MF|FW)\s+(.+?)(?:\s{2,}|$)", line)
            if not player_match:
                continue
            players_payload.append(
                {
                    "shirt_number": int(player_match.group(1)),
                    "position": player_match.group(2),
                    "name": normalize_official_name(player_match.group(3)),
                }
            )
        teams_payload.append(
            {
                "fifa_code": fifa_code,
                "team_name": normalize_official_name(team_match.group(1)),
                "mapped_team_name": FIFA_CODE_TO_TEAM_NAME.get(fifa_code),
                "coach_name": normalize_official_name(coach_match.group(1)) if coach_match else None,
                "players": players_payload,
            }
        )
    return {"source_url": FIFA_SQUAD_LIST_URL, "teams": teams_payload}


def import_fifa_squads(db) -> dict:
    parsed = parse_fifa_squad_list(extract_fifa_squad_text())
    snapshot_id = write_raw_snapshot(
        db,
        "fifa",
        "official_squad_list",
        FIFA_SQUAD_LIST_URL,
        parsed,
        "fifa_squad_pdf_v1",
    )
    team_rows = db.execute(select(teams.c.id, teams.c.code, teams.c.name_zh, teams.c.name_en)).mappings().all()
    team_by_name = {row.name_zh: row for row in team_rows}
    team_by_code = {row.code: row for row in team_rows}

    coach_rows = []
    player_rows = []
    source_links = []
    mapped_teams = 0
    for team_item in parsed["teams"]:
        mapped_name = team_item.get("mapped_team_name")
        team_row = team_by_name.get(mapped_name) or team_by_code.get(team_item["fifa_code"])
        if team_row is None:
            continue
        mapped_teams += 1
        if team_item.get("coach_name"):
            coach_rows.append(
                {
                    "team_id": team_row.id,
                    "name_zh": team_item["coach_name"],
                    "name_en": team_item["coach_name"],
                    "major_tournament_record": {"fifa_team_code": team_item["fifa_code"]},
                    "source_confidence": 0.95,
                    "quality_status": "source",
                }
            )
            source_links.append(
                {
                    "entity_type": "coach",
                    "entity_key": f"{team_row.code}:{team_item['coach_name']}",
                    "source": "fifa",
                    "source_type": "official_squad_list",
                    "source_url": FIFA_SQUAD_LIST_URL,
                    "raw_snapshot_id": snapshot_id,
                    "source_record_id": f"{team_item['fifa_code']}:coach",
                    "confidence": 0.95,
                    "metadata": {"team_code": team_row.code, "fifa_team_code": team_item["fifa_code"]},
                }
            )
        for player in team_item["players"]:
            player_code = f"FIFA-{team_item['fifa_code']}-{player['shirt_number']:02d}"
            player_rows.append(
                {
                    "team_id": team_row.id,
                    "code": player_code,
                    "name_zh": player["name"],
                    "name_en": player["name"],
                    "position": player["position"],
                    "shirt_number": player["shirt_number"],
                    "quality_status": "source",
                }
            )
            source_links.append(
                {
                    "entity_type": "player",
                    "entity_key": player_code,
                    "source": "fifa",
                    "source_type": "official_squad_list",
                    "source_url": FIFA_SQUAD_LIST_URL,
                    "raw_snapshot_id": snapshot_id,
                    "source_record_id": player_code,
                    "confidence": 0.95,
                    "metadata": {
                        "team_code": team_row.code,
                        "fifa_team_code": team_item["fifa_code"],
                        "shirt_number": player["shirt_number"],
                        "position": player["position"],
                    },
                }
            )

    if coach_rows:
        coach_statement = (
            pg_insert(coaches)
            .values(coach_rows)
            .on_conflict_do_update(
                index_elements=["team_id", "name_zh"],
                set_={
                    "name_en": pg_insert(coaches).excluded.name_en,
                    "major_tournament_record": pg_insert(coaches).excluded.major_tournament_record,
                    "source_confidence": pg_insert(coaches).excluded.source_confidence,
                    "quality_status": pg_insert(coaches).excluded.quality_status,
                    "updated_at": text("now()"),
                },
            )
        )
        db.execute(coach_statement)
    if player_rows:
        player_statement = (
            pg_insert(players)
            .values(player_rows)
            .on_conflict_do_update(
                index_elements=["code"],
                set_={
                    "team_id": pg_insert(players).excluded.team_id,
                    "name_zh": pg_insert(players).excluded.name_zh,
                    "name_en": pg_insert(players).excluded.name_en,
                    "position": pg_insert(players).excluded.position,
                    "shirt_number": pg_insert(players).excluded.shirt_number,
                    "quality_status": pg_insert(players).excluded.quality_status,
                    "updated_at": text("now()"),
                },
            )
        )
        db.execute(player_statement)
    links_written = write_source_links(db, snapshot_id, source_links)
    return {
        "fifa_squad_teams_mapped": mapped_teams,
        "fifa_coaches": len(coach_rows),
        "fifa_official_players": len(player_rows),
        "fifa_squad_source_links": links_written,
    }


def main() -> None:
    with SessionLocal() as db:
        result = {}
        result.update(import_fifa_squads(db))
        result.update(enrich_venues(db))
        result.update(write_weather_snapshots(db))
        result.update(aggregate_team_market_values(db))
        db.commit()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
