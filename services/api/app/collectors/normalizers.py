from __future__ import annotations

import hashlib
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from app.collectors.adapters import RawSnapshot

API_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_AS_OF_AT = "2026-06-13T18:00:00+08:00"


TEAM_LOOKUP = {
    "USA": {"code": "USA", "name_zh": "United States", "name_en": "United States", "aliases": ["USA", "US", "United States", "美国"]},
    "UNITED STATES": {"code": "USA", "name_zh": "United States", "name_en": "United States", "aliases": ["USA", "US", "United States", "美国"]},
    "美国": {"code": "USA", "name_zh": "United States", "name_en": "United States", "aliases": ["USA", "US", "United States", "美国"]},
    "PAR": {"code": "PAR", "name_zh": "Paraguay", "name_en": "Paraguay", "aliases": ["PAR", "Paraguay", "巴拉圭"]},
    "PARAGUAY": {"code": "PAR", "name_zh": "Paraguay", "name_en": "Paraguay", "aliases": ["PAR", "Paraguay", "巴拉圭"]},
    "巴拉圭": {"code": "PAR", "name_zh": "Paraguay", "name_en": "Paraguay", "aliases": ["PAR", "Paraguay", "巴拉圭"]},
    "FRA": {"code": "FRA", "name_zh": "France", "name_en": "France", "aliases": ["FRA", "France", "法国"]},
    "FRANCE": {"code": "FRA", "name_zh": "France", "name_en": "France", "aliases": ["FRA", "France", "法国"]},
    "法国": {"code": "FRA", "name_zh": "France", "name_en": "France", "aliases": ["FRA", "France", "法国"]},
    "BRA": {"code": "BRA", "name_zh": "Brazil", "name_en": "Brazil", "aliases": ["BRA", "Brazil", "巴西"]},
    "BRAZIL": {"code": "BRA", "name_zh": "Brazil", "name_en": "Brazil", "aliases": ["BRA", "Brazil", "巴西"]},
    "巴西": {"code": "BRA", "name_zh": "Brazil", "name_en": "Brazil", "aliases": ["BRA", "Brazil", "巴西"]},
    "ENG": {"code": "ENG", "name_zh": "England", "name_en": "England", "aliases": ["ENG", "England", "英格兰"]},
    "ENGLAND": {"code": "ENG", "name_zh": "England", "name_en": "England", "aliases": ["ENG", "England", "英格兰"]},
    "英格兰": {"code": "ENG", "name_zh": "England", "name_en": "England", "aliases": ["ENG", "England", "英格兰"]},
}


def stable_checksum(*parts: str) -> str:
    value = "|".join(parts)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_team_ref(value: str | None) -> dict | None:
    if not value:
        return None
    key = value.strip()
    if not key:
        return None
    team = TEAM_LOOKUP.get(key.upper()) or TEAM_LOOKUP.get(key)
    if team:
        return team

    code = re.sub(r"[^A-Za-z0-9]+", "-", key).strip("-").upper()[:32]
    if not code:
        return None
    return {"code": code, "name_zh": key, "name_en": key, "aliases": [key, code]}


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", value)
    return value.strip("-") or stable_checksum(value)[:12]


def parse_datetime(value: str | None) -> datetime:
    raw = value or DEFAULT_AS_OF_AT
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(API_TZ)


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


def canonical_records_from_snapshot(snapshot: RawSnapshot) -> dict:
    records = {
        "teams": {},
        "team_aliases": [],
        "matches": [],
        "standings": [],
        "players": [],
        "player_forms": [],
    }

    collect_schedule(snapshot, records)
    collect_standings(snapshot, records)
    collect_player_rankings(snapshot, records)
    return {
        "teams": list(records["teams"].values()),
        "team_aliases": records["team_aliases"],
        "matches": records["matches"],
        "standings": records["standings"],
        "players": records["players"],
        "player_forms": records["player_forms"],
    }


def add_team(records: dict, source: str, raw_value: str | None) -> dict | None:
    team = normalize_team_ref(raw_value)
    if team is None:
        return None

    records["teams"][team["code"]] = {
        "code": team["code"],
        "name_zh": team["name_zh"],
        "name_en": team["name_en"],
        "quality_status": "source",
    }
    for alias in team["aliases"]:
        records["team_aliases"].append(
            {
                "source": source,
                "source_team_id": f"{team['code']}:{alias}",
                "alias": alias,
                "team_code": team["code"],
                "confidence": 1.0,
                "is_primary": alias == team["code"],
            }
        )
    return team


def collect_schedule(snapshot: RawSnapshot, records: dict) -> None:
    for item in snapshot.payload.get("matches", []):
        home = add_team(records, snapshot.source, item.get("home"))
        away = add_team(records, snapshot.source, item.get("away"))
        if home is None or away is None:
            continue
        records["matches"].append(
            {
                "public_id": item.get("public_id") or stable_checksum(home["code"], away["code"], item.get("kickoff_at", ""))[:32],
                "competition_code": item.get("competition_code", "world_cup_2026"),
                "stage_code": item.get("stage_code", "group-a"),
                "stage_name": item.get("stage_name", "Group A"),
                "stage_type": item.get("stage_type", "group"),
                "home_team_code": home["code"],
                "away_team_code": away["code"],
                "venue_code": item.get("venue_code"),
                "kickoff_at": parse_datetime(item.get("kickoff_at")),
                "status": item.get("status", "scheduled"),
                "home_score": item.get("home_score"),
                "away_score": item.get("away_score"),
                "neutral_site": item.get("neutral_site", True),
                "source_confidence": item.get("source_confidence", 0.8),
            }
        )


def collect_standings(snapshot: RawSnapshot, records: dict) -> None:
    for group in snapshot.payload.get("groups", []):
        stage_code = group.get("code", "group-a")
        for item in group.get("teams", []):
            team = add_team(records, snapshot.source, item.get("code") or item.get("team"))
            if team is None:
                continue
            wins = int(item.get("wins", 0))
            draws = int(item.get("draws", 0))
            losses = int(item.get("losses", 0))
            goals_for = int(item.get("goals_for", 0))
            goals_against = int(item.get("goals_against", 0))
            records["standings"].append(
                {
                    "stage_code": stage_code,
                    "team_code": team["code"],
                    "played": int(item.get("played", wins + draws + losses)),
                    "wins": wins,
                    "draws": draws,
                    "losses": losses,
                    "goals_for": goals_for,
                    "goals_against": goals_against,
                    "goal_diff": int(item.get("goal_diff", goals_for - goals_against)),
                    "points": int(item.get("points", wins * 3 + draws)),
                    "rank": int(item.get("rank", 99)),
                }
            )


def collect_player_rankings(snapshot: RawSnapshot, records: dict) -> None:
    as_of_at = parse_datetime(snapshot.payload.get("as_of_at"))
    for item in snapshot.payload.get("players", []):
        team = add_team(records, snapshot.source, item.get("team"))
        name = item.get("name")
        if team is None or not name:
            continue

        player_code = item.get("code") or f"{team['code']}-{slugify(name)}"
        records["players"].append(
            {
                "code": player_code,
                "team_code": team["code"],
                "name_zh": name,
                "name_en": item.get("name_en"),
                "position": item.get("position"),
                "shirt_number": item.get("shirt_number"),
                "club_name": item.get("club_name"),
                "market_value_eur": item.get("market_value_eur"),
                "is_key_player": item.get("is_key_player", False),
                "quality_status": "source",
            }
        )
        records["player_forms"].append(
            {
                "player_code": player_code,
                "team_code": team["code"],
                "as_of_at": as_of_at,
                "recent_matches": int(item.get("recent_matches", 10)),
                "minutes": item.get("minutes"),
                "goals": item.get("goals"),
                "assists": item.get("assists"),
                "shots": item.get("shots"),
                "key_passes": item.get("key_passes"),
                "rating": item.get("rating"),
                "availability_status": item.get("availability_status", "available"),
                "form_score": item.get("form_score"),
                "source_count": int(item.get("source_count", 1)),
            }
        )
