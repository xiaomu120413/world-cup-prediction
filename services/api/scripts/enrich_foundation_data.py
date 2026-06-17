from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import and_, delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.schema import data_source_links, matches, raw_snapshots, teams, venues, weather_snapshots
from app.db.session import SessionLocal

API_TZ = ZoneInfo("Asia/Shanghai")
FIFA_STADIUM_INFO_URL = (
    "https://www.fifa.com/en/tournaments/mens/worldcup/"
    "canadamexicousa2026/articles/stadium-information-details"
)
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
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
        "code": "bc-place-stadium",
        "capacity": 59687,
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
        "code": "estadio-bbva-bancomer",
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

    unused_legacy_codes = ["bc-place", "estadio-bbva", "los-angeles"]
    db.execute(
        data_source_links.delete().where(
            data_source_links.c.entity_key.in_(unused_legacy_codes),
            data_source_links.c.entity_type == "venue",
        )
    )
    for legacy_code in unused_legacy_codes:
        db.execute(
            data_source_links.delete().where(
                data_source_links.c.entity_type == "weather_snapshot",
                data_source_links.c.entity_key.like(f"{legacy_code}:%"),
            )
        )
    db.execute(
        delete(weather_snapshots).where(
            weather_snapshots.c.venue_id.in_(
                select(venues.c.id).where(
                    venues.c.code.in_(unused_legacy_codes),
                    ~venues.c.id.in_(select(matches.c.venue_id).where(matches.c.venue_id.is_not(None))),
                )
            )
        )
    )
    db.execute(
        delete(venues).where(
            venues.c.code.in_(unused_legacy_codes),
            ~venues.c.id.in_(select(matches.c.venue_id).where(matches.c.venue_id.is_not(None))),
        )
    )
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
        .where(
            raw_snapshots.c.source == "dongqiudi",
            raw_snapshots.c.source_type.in_(["world_cup_team_details", "world_cup_player_rankings"]),
        )
        .order_by(raw_snapshots.c.fetched_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    rows = db.execute(
        text(
            """
            with selected_players as (
                select p.team_id, p.market_value_eur
                from players p
                where p.market_value_eur is not null
                  and p.code like 'DQD-P%'
            )
            select t.id, t.code, sum(sp.market_value_eur) as market_value_eur, count(*) as player_count
            from teams t
            join selected_players sp on sp.team_id = t.id
            group by t.id, t.code
            """
        )
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
                    "aggregation": "sum_market_value_eur_from_dongqiudi_member_v2_roster",
                    "selected_roster_priority": ["Dongqiudi team/member_v2 roster"],
                },
            }
        )
    links_written = write_source_links(db, latest_market_snapshot, source_links)
    return {"team_market_values": len(rows), "team_market_value_source_links": links_written}


def skip_fifa_squad_import() -> dict:
    return {
        "fifa_squad_import": "skipped",
        "player_roster_source": "dongqiudi/team_member_v2",
    }


def main() -> None:
    with SessionLocal() as db:
        result = {}
        result.update(skip_fifa_squad_import())
        result.update(enrich_venues(db))
        result.update(write_weather_snapshots(db))
        result.update(aggregate_team_market_values(db))
        db.commit()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
