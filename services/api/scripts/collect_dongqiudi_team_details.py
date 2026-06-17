from __future__ import annotations

import concurrent.futures
import hashlib
import json
import re
import sys
import time
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import and_, delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.schema import (
    coaches,
    data_source_links,
    player_aliases,
    player_form_snapshots,
    players,
    raw_snapshots,
    team_aliases,
    team_stat_snapshots,
    teams,
)
from app.db.session import SessionLocal

API_TZ = ZoneInfo("Asia/Shanghai")
RANKING_TEAM_URL = "https://m.dongqiudi.com/stat/9/rankingTeam"
TEAM_PAGE_URL = "https://pc.dongqiudi.com/team/{team_id}"
TEAM_DETAIL_URL = "https://www.dongqiudi.com/api/data/v1/detail/team/{team_id}?app=dqd&lang=zh-cn"
TEAM_MEMBER_URL = "https://www.dongqiudi.com/sport-data/soccer/biz/dqd/v1/team/member_v2/{team_id}?app=dqd"
PLAYER_PAGE_URL = "https://www.dongqiudi.com/player/{person_id}.html"
TEAM_RANKING_TYPES_URL = (
    "https://sport-data.dongqiudi.com/soccer/biz/data/ranking/team"
    "?season_id=26123&app=dqd&version=853&platform=ios&language=zh-cn&app_type=&type=team"
)
MAX_WORKERS = 6
PLAYER_AVATAR_CACHE_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "dongqiudi_player_avatars.json"
# Low-frequency roster pages are collected as daily snapshots; using midnight keeps
# repeated local runs idempotent for player form rows on the same day.
AS_OF_AT = datetime.now(API_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
AS_OF_KEY = AS_OF_AT.isoformat()

TEAM_CODE_OVERRIDES = {
    "50000013": "ALGERIA",
    "50000067": "ARGENTINA",
    "50000087": "AUSTRALIA",
    "50000108": "AUSTRIA",
    "50000203": "BELGIUM",
    "50000219": "BOSNIA-AND-HERZEGOVINA",
    "50000269": "BRA",
    "50000303": "CANADA",
    "50000304": "CABO-VERDE",
    "50000364": "COLOMBIA",
    "50000366": "CONGO-DR",
    "50000396": "CROATIA",
    "50000453": "CZECHIA",
    "50000454": "COTE-D-IVOIRE",
    "50000510": "ECUADOR",
    "50000511": "EGYPT",
    "50000627": "ENG",
    "50000789": "FRA",
    "50000868": "GERMANY",
    "50000869": "GHANA",
    "50000916": "HAITI",
    "50000986": "IR-IRAN",
    "50000987": "IRAQ",
    "50001146": "JAPAN",
    "50001147": "JORDAN",
    "50001181": "KOREA-REPUBLIC",
    "50001278": "MEXICO",
    "50001289": "MOROCCO",
    "50001331": "NETHERLANDS",
    "50001332": "CURACAO",
    "50001341": "NEW-ZEALAND",
    "50001389": "NORWAY",
    "50001393": "PANAMA",
    "50001405": "PAR",
    "50001540": "PORTUGAL",
    "50001542": "QATAR",
    "50001640": "SAUDI-ARABIA",
    "50001683": "SCOTLAND",
    "50001684": "SENEGAL",
    "50001753": "SOUTH-AFRICA",
    "50001869": "SPAIN",
    "50001904": "SWEDEN",
    "50001931": "SWITZERLAND",
    "50001941": "TUNISIA",
    "50001977": "TURKIYE",
    "50002008": "USA",
    "50002026": "URUGUAY",
    "50002027": "UZBEKISTAN",
}

POSITION_MAP = {
    "attacker": "FW",
    "midfielder": "MF",
    "defender": "DF",
    "goalkeeper": "GK",
    "前锋": "FW",
    "中场": "MF",
    "后卫": "DF",
    "门将": "GK",
}


def checksum(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def source_headers(referer: str | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": "world-cup-prediction-bot/0.1 (+low-frequency research collector)",
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def fetch_text(url: str, referer: str | None = None) -> str:
    response = httpx.get(url, timeout=30.0, headers=source_headers(referer), follow_redirects=True)
    response.raise_for_status()
    return response.text


def fetch_json(url: str, referer: str | None = None) -> dict:
    response = httpx.get(url, timeout=30.0, headers=source_headers(referer), follow_redirects=True)
    response.raise_for_status()
    return response.json()


def write_raw_snapshot(db, source_type: str, source_url: str, payload: dict, parser_version: str):
    digest = checksum(payload)
    statement = (
        pg_insert(raw_snapshots)
        .values(
            source="dongqiudi",
            source_type=source_type,
            source_url=source_url,
            checksum=digest,
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
            raw_snapshots.c.source == "dongqiudi",
            raw_snapshots.c.source_type == source_type,
            raw_snapshots.c.checksum == digest,
        )
    ).scalar_one()


def write_source_links(db, rows: list[dict]) -> int:
    if not rows:
        return 0
    deduped: dict[tuple[str, str, str, str], dict] = {}
    for row in rows:
        key = (row["entity_type"], row["entity_key"], row["source"], row["source_type"])
        current = deduped.get(key)
        if current is None or float(row["confidence"]) >= float(current["confidence"]):
            deduped[key] = row
    statement = (
        pg_insert(data_source_links)
        .values(list(deduped.values()))
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


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    text_value = unicodedata.normalize("NFKD", value)
    text_value = "".join(ch for ch in text_value if not unicodedata.combining(ch))
    text_value = text_value.replace("'", " ")
    text_value = re.sub(r"[^a-zA-Z0-9]+", " ", text_value)
    return " ".join(text_value.lower().split())


def short_team_id(team_id: str) -> str:
    value = str(team_id)
    return str(int(value[4:])) if value.startswith("5000") and value[4:].isdigit() else value


def parse_world_cup_teams(html: str) -> list[dict[str, str]]:
    seen = set()
    rows = []
    for match in re.finditer(r'"team_id":"(\d+)".{0,600}?"team_name":"([^"]+)"', html):
        team_id, name = match.groups()
        if team_id in seen:
            continue
        seen.add(team_id)
        rows.append({"team_id": team_id, "short_team_id": short_team_id(team_id), "team_name": name.strip()})
    return rows


def parse_market_value(value: Any) -> int | None:
    if value is None:
        return None
    text_value = str(value).strip().replace(",", "")
    if not text_value or text_value in {"-", "0"}:
        return None
    text_value = text_value.replace("身价(欧)", "").replace("欧元", "").replace("欧", "").replace("€", "").strip()
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", text_value)
    if not match:
        return None
    try:
        amount = Decimal(match.group(1))
    except InvalidOperation:
        return None
    upper_value = text_value.upper()
    if "亿" in text_value:
        amount *= Decimal("100000000")
    elif "万" in text_value:
        amount *= Decimal("10000")
    elif "B" in upper_value:
        amount *= Decimal("1000000000")
    elif "M" in upper_value:
        amount *= Decimal("1000000")
    elif "K" in upper_value:
        amount *= Decimal("1000")
    return int(amount)


def statistic_value(item: dict, key: str) -> Any:
    for stat in item.get("statistic") or []:
        if key in stat:
            return stat[key]
    return None


def statistic_market_value(item: dict) -> int | None:
    for stat in item.get("statistic") or []:
        for key, value in stat.items():
            if "身价" in key:
                return parse_market_value(value)
    return None


def player_profile_market_value(person_id: str) -> int | None:
    try:
        html = fetch_text(PLAYER_PAGE_URL.format(person_id=person_id), "https://www.dongqiudi.com/")
    except Exception:
        return None
    match = re.search(r'market_value:"([0-9.]+)"', html)
    if not match:
        return None
    # Dongqiudi player profiles store market_value in ten-thousand EUR.
    return int(Decimal(match.group(1)) * Decimal("10000"))


def load_player_avatar_cache() -> dict[str, str]:
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


def update_player_avatar_cache(team_payloads: list[dict[str, Any]]) -> dict:
    existing = load_player_avatar_cache()
    current_person_ids: set[str] = set()
    avatars: dict[str, str] = {}
    for team_data in team_payloads:
        groups = (((team_data.get("member") or {}).get("data") or {}).get("list") or [])
        for group in groups:
            group_title = group.get("title")
            for item in group.get("data") or []:
                person_id = str(item.get("person_id") or "").strip()
                position = POSITION_MAP.get(item.get("type")) or POSITION_MAP.get(group_title) or group_title
                if not person_id or position not in {"FW", "MF", "DF", "GK"}:
                    continue
                current_person_ids.add(person_id)
                avatar_url = str(item.get("person_logo") or "").strip()
                if avatar_url.startswith("http"):
                    avatars[person_id] = avatar_url

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
        "player_avatar_cache_before": len(existing),
        "player_avatar_cache_after": len(next_cache),
        "player_avatar_urls_seen": len(avatars),
    }


def to_int(value: Any) -> int | None:
    if value is None:
        return None
    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else None


def parse_team_stat_numeric(value: Any, metric_type: str | None = None) -> tuple[Decimal | None, str | None]:
    if value is None:
        return None, None
    raw = str(value).strip().replace(",", "")
    if not raw or raw in {"-", "--"}:
        return None, None
    match = re.search(r"-?\d+(?:\.\d+)?", raw)
    if not match:
        return None, None
    try:
        amount = Decimal(match.group(0))
    except InvalidOperation:
        return None, None

    unit = "count"
    multiplier = Decimal("1")
    upper_raw = raw.upper()
    if "%" in raw:
        unit = "percent"
    if metric_type == "market_value":
        unit = "eur"
    if "\u4ebf" in raw:
        multiplier = Decimal("100000000")
    elif "\u4e07" in raw:
        multiplier = Decimal("10000")
    elif "B" in upper_raw:
        multiplier = Decimal("1000000000")
    elif "M" in upper_raw:
        multiplier = Decimal("1000000")
    elif "K" in upper_raw:
        multiplier = Decimal("1000")
    elif metric_type == "rating":
        unit = "rating"
    return amount * multiplier, unit


def parse_date(value: Any):
    if not value:
        return None
    text_value = str(value).replace(".", "-")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", text_value):
        return None
    return text_value


def parse_team_page_market_value(html: str) -> int | None:
    for pattern in (r'marketValue:"([^"]+)"', r"市值\s*(€?[0-9.]+[KMB]?)"):
        match = re.search(pattern, html)
        if match:
            value = parse_market_value(match.group(1))
            if value:
                return value
    return None


def source_link(
    entity_type: str,
    entity_key: str,
    source_type: str,
    source_url: str,
    snapshot_id,
    source_record_id: str,
    confidence: float,
    metadata: dict | None = None,
) -> dict:
    return {
        "entity_type": entity_type,
        "entity_key": entity_key,
        "source": "dongqiudi",
        "source_type": source_type,
        "source_url": source_url,
        "raw_snapshot_id": snapshot_id,
        "source_record_id": source_record_id,
        "confidence": confidence,
        "metadata": metadata or {},
    }


def collect_team(team: dict[str, str]) -> dict[str, Any]:
    team_id = team["team_id"]
    short_id = team["short_team_id"]
    page_url = TEAM_PAGE_URL.format(team_id=short_id)
    detail_url = TEAM_DETAIL_URL.format(team_id=short_id)
    member_url = TEAM_MEMBER_URL.format(team_id=short_id)
    last_error = None
    for attempt in range(3):
        try:
            page_html = fetch_text(page_url)
            detail = fetch_json(detail_url, page_url)
            member = fetch_json(member_url, page_url)
            return {
                **team,
                "source_urls": {
                    "page": page_url,
                    "detail": detail_url,
                    "member": member_url,
                },
                "page_market_value_eur": parse_team_page_market_value(page_html),
                "detail": detail,
                "member": member,
            }
        except Exception as exc:  # pragma: no cover - network retry path
            last_error = str(exc)
            time.sleep(0.5 * (attempt + 1))
    return {**team, "error": last_error}


def collect_all_teams(team_refs: list[dict[str, str]]) -> list[dict[str, Any]]:
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {executor.submit(collect_team, team): team for team in team_refs}
        for future in concurrent.futures.as_completed(future_map):
            results.append(future.result())
    return sorted(results, key=lambda item: item["team_id"])


def fetch_team_rankings() -> dict[str, Any]:
    types_payload = fetch_json(TEAM_RANKING_TYPES_URL, "https://pc.dongqiudi.com/data?cid=61&tab=team")
    metric_types = (types_payload.get("content") or {}).get("data") or []
    rankings = []
    for metric in metric_types:
        url = metric.get("url")
        if not url:
            continue
        try:
            payload = fetch_json(url, TEAM_RANKING_TYPES_URL)
            rankings.append(
                {
                    "type": metric.get("type"),
                    "name": metric.get("name"),
                    "url": url,
                    "rows": (payload.get("content") or {}).get("data") or [],
                }
            )
        except Exception as exc:  # pragma: no cover - network retry path
            rankings.append({"type": metric.get("type"), "name": metric.get("name"), "url": url, "error": str(exc), "rows": []})
    return {"types_url": TEAM_RANKING_TYPES_URL, "types": metric_types, "rankings": rankings}


def team_index(db) -> dict[str, Any]:
    rows = db.execute(select(teams.c.id, teams.c.code, teams.c.name_zh, teams.c.name_en)).mappings().all()
    by_code = {row.code: row for row in rows}
    alias_rows = db.execute(
        select(team_aliases.c.source_team_id, team_aliases.c.alias, teams.c.id, teams.c.code)
        .select_from(team_aliases.join(teams, team_aliases.c.team_id == teams.c.id))
    ).mappings().all()
    by_alias = {normalize_name(row.alias): row for row in alias_rows if row.alias}
    by_source_team_id = {row.source_team_id: row for row in alias_rows if row.source_team_id}
    return {"by_code": by_code, "by_alias": by_alias, "by_source_team_id": by_source_team_id}


def code_from_name(name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").upper()
    return normalized[:32] if normalized else f"DQD{hashlib.sha256(name.encode('utf-8')).hexdigest()[:10].upper()}"


def ensure_team(db, index: dict[str, Any], team_data: dict[str, Any]) -> dict:
    detail = team_data.get("detail") or {}
    base_info = detail.get("base_info") or {}
    source_team_id = str(base_info.get("team_id") or team_data["team_id"])
    team_name = base_info.get("team_name") or team_data.get("team_name") or source_team_id
    team_en_name = base_info.get("team_en_name") or team_name
    code = TEAM_CODE_OVERRIDES.get(source_team_id)

    if not code:
        source_row = index["by_source_team_id"].get(source_team_id)
        if source_row:
            code = source_row.code
    if not code:
        for candidate in (team_en_name, team_name):
            row = index["by_alias"].get(normalize_name(candidate))
            if row:
                code = row.code
                break
    if not code:
        code = code_from_name(team_en_name)

    team_id = db.execute(
        pg_insert(teams)
        .values(code=code, name_zh=team_name, name_en=team_en_name, market_value_eur=team_data.get("page_market_value_eur"), quality_status="source")
        .on_conflict_do_update(
            index_elements=["code"],
            set_={
                "name_zh": pg_insert(teams).excluded.name_zh,
                "name_en": pg_insert(teams).excluded.name_en,
                "market_value_eur": func.coalesce(pg_insert(teams).excluded.market_value_eur, teams.c.market_value_eur),
                "quality_status": "source",
                "updated_at": text("now()"),
            },
        )
        .returning(teams.c.id)
    ).scalar_one()

    aliases = {
        team_name,
        team_en_name,
        team_data.get("team_name"),
        source_team_id,
        short_team_id(source_team_id),
        code,
    }
    for alias in {item.strip() for item in aliases if item and str(item).strip()}:
        db.execute(
            pg_insert(team_aliases)
            .values(
                team_id=team_id,
                source="dongqiudi",
                source_team_id=source_team_id if alias == team_name else f"{source_team_id}:{alias}",
                alias=alias,
                confidence=1.0,
                is_primary=alias == team_name,
            )
            .on_conflict_do_update(
                index_elements=["source", "alias"],
                set_={
                    "team_id": team_id,
                    "source_team_id": pg_insert(team_aliases).excluded.source_team_id,
                    "confidence": pg_insert(team_aliases).excluded.confidence,
                    "is_primary": pg_insert(team_aliases).excluded.is_primary,
                },
            )
        )
    return {"id": team_id, "code": code, "source_team_id": source_team_id, "name_zh": team_name, "name_en": team_en_name}


def upsert_roster_players(db, team_row: dict, team_data: dict[str, Any], snapshot_id) -> dict:
    member = team_data.get("member") or {}
    groups = ((member.get("data") or {}).get("list") or [])
    source_url = team_data["source_urls"]["member"]
    player_rows = []
    player_alias_seed_rows = []
    form_rows = []
    links = []

    for group in groups:
        group_title = group.get("title")
        if group_title in {"教练", "工作人员"}:
            continue
        for item in group.get("data") or []:
            person_id = str(item.get("person_id") or "").strip()
            name = item.get("person_name")
            if not person_id or not name:
                continue
            code = f"DQD-P{person_id}"
            market_value = statistic_market_value(item)
            market_source_type = "team_member_v2_market_value"
            market_source_url = source_url
            if market_value is None:
                market_value = player_profile_market_value(person_id)
                market_source_type = "player_profile_market_value"
                market_source_url = PLAYER_PAGE_URL.format(person_id=person_id)
            position = POSITION_MAP.get(item.get("type")) or POSITION_MAP.get(group_title) or group_title
            if position not in {"FW", "MF", "DF", "GK"}:
                continue
            player_rows.append(
                {
                    "team_id": team_row["id"],
                    "code": code,
                    "name_zh": name,
                    "name_en": item.get("person_en_name") or name,
                    "position": position,
                    "shirt_number": to_int(item.get("shirtnumber")),
                    "club_name": item.get("nationality_name"),
                    "market_value_eur": market_value,
                    "is_key_player": bool(item.get("captain_logo")),
                    "quality_status": "source",
                }
            )
            aliases = []
            for alias in (name, item.get("person_en_name"), code):
                if alias and alias not in aliases:
                    aliases.append(alias)
            player_alias_seed_rows.append(
                {
                    "code": code,
                    "team_id": team_row["id"],
                    "source_player_id": person_id,
                    "aliases": aliases,
                }
            )
            links.append(
                source_link(
                    "player",
                    code,
                    "team_member_v2",
                    source_url,
                    snapshot_id,
                    person_id,
                    0.9,
                    {
                        "team_code": team_row["code"],
                        "source_team_id": team_row["source_team_id"],
                        "group": group_title,
                        "position_type": item.get("type"),
                        "club_or_affiliation": item.get("nationality_name"),
                        "scheme": item.get("scheme"),
                    },
                )
            )
            avatar_url = str(item.get("person_logo") or "").strip()
            if avatar_url.startswith("http"):
                links.append(
                    source_link(
                        "player_avatar",
                        code,
                        "team_member_v2_person_logo",
                        source_url,
                        snapshot_id,
                        person_id,
                        0.86,
                        {
                            "team_code": team_row["code"],
                            "source_team_id": team_row["source_team_id"],
                            "player_name": name,
                            "position_type": item.get("type"),
                            "group": group_title,
                            "avatar_url": avatar_url,
                        },
                    )
                )
            if market_value:
                links.append(
                    source_link(
                        "player_market_value",
                        code,
                        market_source_type,
                        market_source_url,
                        snapshot_id,
                        person_id,
                        0.86,
                        {
                            "team_code": team_row["code"],
                            "source_team_id": team_row["source_team_id"],
                            "statistic": item.get("statistic") or [],
                        },
                    )
                )

            appearances = to_int(statistic_value(item, "出场"))
            goals = to_int(statistic_value(item, "进球"))
            assists = to_int(statistic_value(item, "助攻"))
            if appearances is not None or goals is not None or assists is not None:
                form_rows.append(
                    {
                        "player_code": code,
                        "team_id": team_row["id"],
                        "as_of_at": AS_OF_AT,
                        "recent_matches": appearances or 0,
                        "minutes": None,
                        "goals": goals,
                        "assists": assists,
                        "shots": None,
                        "key_passes": None,
                        "rating": None,
                        "availability_status": "available",
                        "form_score": None,
                        "source_count": 1,
                        "source_link": source_link(
                            "player_form",
                            f"{code}:{AS_OF_KEY}",
                            "team_member_v2_statistic",
                            source_url,
                            snapshot_id,
                            person_id,
                            0.82,
                            {
                                "team_code": team_row["code"],
                                "source_team_id": team_row["source_team_id"],
                                "statistic": item.get("statistic") or [],
                            },
                        ),
                    }
                )

    if player_rows:
        db.execute(
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
                    "club_name": pg_insert(players).excluded.club_name,
                    "market_value_eur": func.coalesce(pg_insert(players).excluded.market_value_eur, players.c.market_value_eur),
                    "is_key_player": pg_insert(players).excluded.is_key_player,
                    "quality_status": pg_insert(players).excluded.quality_status,
                    "updated_at": text("now()"),
                },
            )
        )
        player_ids = {
            row.code: row.id
            for row in db.execute(
                select(players.c.code, players.c.id).where(players.c.code.in_([row["code"] for row in player_rows]))
            ).mappings().all()
        }
        alias_rows = []
        seen_alias_ids = set()
        for seed in player_alias_seed_rows:
            player_id = player_ids.get(seed["code"])
            if not player_id:
                continue
            for index, alias in enumerate(seed["aliases"]):
                is_primary = index == 0
                source_player_id = (
                    seed["source_player_id"]
                    if is_primary
                    else f"{seed['source_player_id']}:{hashlib.sha256(alias.encode('utf-8')).hexdigest()[:12]}"
                )
                if source_player_id in seen_alias_ids:
                    continue
                seen_alias_ids.add(source_player_id)
                alias_rows.append(
                    {
                        "player_id": player_id,
                        "team_id": seed["team_id"],
                        "source": "dongqiudi",
                        "source_player_id": source_player_id,
                        "alias": alias,
                        "confidence": 0.95,
                        "is_primary": is_primary,
                    }
                )
        if alias_rows:
            db.execute(
                pg_insert(player_aliases)
                .values(alias_rows)
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

    if form_rows:
        player_ids = {
            row.code: row.id
            for row in db.execute(
                select(players.c.code, players.c.id).where(players.c.code.in_([row["player_code"] for row in form_rows]))
            ).mappings().all()
        }
        values = []
        for row in form_rows:
            player_id = player_ids.get(row["player_code"])
            if not player_id:
                continue
            db.execute(
                delete(player_form_snapshots).where(
                    and_(
                        player_form_snapshots.c.player_id == player_id,
                        player_form_snapshots.c.as_of_at == AS_OF_AT,
                    )
                )
            )
            values.append({key: value for key, value in row.items() if key not in {"player_code", "source_link"}} | {"player_id": player_id})
            links.append(row["source_link"])
        if values:
            db.execute(pg_insert(player_form_snapshots).values(values))

    return {
        "players": len(player_rows),
        "player_forms": len(form_rows),
        "links": links,
    }


def upsert_coaches(db, team_row: dict, team_data: dict[str, Any], snapshot_id) -> dict:
    detail = team_data.get("detail") or {}
    history_rows = detail.get("history_coach") or []
    member_groups = (((team_data.get("member") or {}).get("data") or {}).get("list") or [])
    source_url = team_data["source_urls"]["detail"]
    member_coaches = []
    for group in member_groups:
        if group.get("title") in {"教练", "工作人员"}:
            member_coaches.extend(group.get("data") or [])

    rows = []
    links = []
    seen = set()
    for item in history_rows:
        person = item.get("person") or {}
        name = person.get("name") or item.get("person_name")
        if not name:
            continue
        wins, draws, losses = to_int(item.get("win")) or 0, to_int(item.get("draw")) or 0, to_int(item.get("loss")) or 0
        matches_count = wins + draws + losses
        rows.append(
            {
                "team_id": team_row["id"],
                "name_zh": name,
                "name_en": person.get("en_name") or person.get("full_name"),
                "started_at": parse_date(item.get("start_date")),
                "matches_count": matches_count or None,
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "win_rate": Decimal(str(item.get("win_rate"))) if item.get("win_rate") else None,
                "major_tournament_record": {
                    "source_person_id": str(item.get("person_id") or person.get("id") or ""),
                    "end_date": item.get("end_date"),
                    "tenure": item.get("time"),
                    "source": "dongqiudi_history_coach",
                },
                "source_confidence": 0.86,
                "quality_status": "source",
            }
        )
        seen.add(name)
        links.append(
            source_link(
                "coach",
                f"{team_row['code']}:{name}",
                "team_history_coach",
                source_url,
                snapshot_id,
                str(item.get("person_id") or person.get("id") or name),
                0.86,
                {"team_code": team_row["code"], "source_team_id": team_row["source_team_id"], "record": item},
            )
        )

    member_url = team_data["source_urls"]["member"]
    for item in member_coaches:
        if item.get("person_name") in seen:
            continue
        name = item.get("person_name")
        rows.append(
            {
                "team_id": team_row["id"],
                "name_zh": name,
                "name_en": None,
                "started_at": None,
                "matches_count": None,
                "wins": None,
                "draws": None,
                "losses": None,
                "win_rate": None,
                "major_tournament_record": {
                    "source_person_id": str(item.get("person_id") or ""),
                    "role": item.get("type"),
                    "nationality": item.get("nationality_name"),
                    "source": "dongqiudi_team_member_v2",
                },
                "source_confidence": 0.82,
                "quality_status": "source",
            }
        )
        links.append(
            source_link(
                "coach",
                f"{team_row['code']}:{name}",
                "team_member_v2_coach",
                member_url,
                snapshot_id,
                str(item.get("person_id") or name),
                0.82,
                {"team_code": team_row["code"], "source_team_id": team_row["source_team_id"], "coach": item},
            )
        )

    if rows:
        deduped_rows = {}
        for row in rows:
            key = (row["team_id"], row["name_zh"])
            current = deduped_rows.get(key)
            if current is None:
                deduped_rows[key] = row
                continue
            current_date = str(current.get("started_at") or "")
            row_date = str(row.get("started_at") or "")
            if row_date >= current_date:
                deduped_rows[key] = row
        rows = list(deduped_rows.values())
        db.execute(
            pg_insert(coaches)
            .values(rows)
            .on_conflict_do_update(
                index_elements=["team_id", "name_zh"],
                set_={
                    "name_en": func.coalesce(pg_insert(coaches).excluded.name_en, coaches.c.name_en),
                    "started_at": func.coalesce(pg_insert(coaches).excluded.started_at, coaches.c.started_at),
                    "matches_count": func.coalesce(pg_insert(coaches).excluded.matches_count, coaches.c.matches_count),
                    "wins": func.coalesce(pg_insert(coaches).excluded.wins, coaches.c.wins),
                    "draws": func.coalesce(pg_insert(coaches).excluded.draws, coaches.c.draws),
                    "losses": func.coalesce(pg_insert(coaches).excluded.losses, coaches.c.losses),
                    "win_rate": func.coalesce(pg_insert(coaches).excluded.win_rate, coaches.c.win_rate),
                    "major_tournament_record": pg_insert(coaches).excluded.major_tournament_record,
                    "source_confidence": pg_insert(coaches).excluded.source_confidence,
                    "quality_status": pg_insert(coaches).excluded.quality_status,
                    "updated_at": text("now()"),
                },
            )
        )
    return {"coaches": len(rows), "links": links}


def update_team_ranking(db, team_row: dict, team_data: dict[str, Any], snapshot_id) -> list[dict]:
    detail = team_data.get("detail") or {}
    ranking = detail.get("nation_ranking") or {}
    latest = None
    for item in ranking.get("data") or []:
        if item.get("title") == "最近排名":
            latest = to_int(item.get("rank"))
            break
    if latest:
        db.execute(update(teams).where(teams.c.id == team_row["id"]).values(fifa_rank=latest, updated_at=text("now()")))
    return [
        source_link(
            "team",
            team_row["code"],
            "team_detail_profile",
            team_data["source_urls"]["detail"],
            snapshot_id,
            team_row["source_team_id"],
            0.84,
            {
                "source_team_id": team_row["source_team_id"],
                "team_name": team_row["name_zh"],
                "team_en_name": team_row["name_en"],
                "nation_ranking": ranking,
                "base_info": (detail.get("base_info") or {}),
            },
        )
    ]


def team_stat_source_links(team_rankings: dict[str, Any], team_code_by_source_id: dict[str, str], snapshot_id) -> list[dict]:
    links = []
    for metric in team_rankings.get("rankings") or []:
        metric_type = metric.get("type")
        metric_name = metric.get("name")
        source_url = metric.get("url") or TEAM_RANKING_TYPES_URL
        if not metric_type:
            continue
        for row in metric.get("rows") or []:
            source_team_id = str(row.get("team_id") or row.get("id") or "")
            team_code = team_code_by_source_id.get(source_team_id)
            if not team_code:
                continue
            links.append(
                source_link(
                    "team_stat",
                    f"{team_code}:{metric_type}",
                    "world_cup_team_ranking",
                    source_url,
                    snapshot_id,
                    f"{source_team_id}:{metric_type}",
                    0.86,
                    {
                        "team_code": team_code,
                        "source_team_id": source_team_id,
                        "metric_type": metric_type,
                        "metric_name": metric_name,
                        "rank": row.get("rank"),
                        "count": row.get("count"),
                        "team_name": row.get("team_name") or row.get("name"),
                    },
                )
            )
    return links


def team_stat_snapshot_rows(
    team_rankings: dict[str, Any],
    team_rows_by_source_id: dict[str, dict],
    snapshot_id,
) -> list[dict]:
    rows = []
    for metric in team_rankings.get("rankings") or []:
        metric_type = metric.get("type")
        metric_name = metric.get("name") or metric_type
        source_url = metric.get("url") or TEAM_RANKING_TYPES_URL
        if not metric_type:
            continue
        for item in metric.get("rows") or []:
            source_team_id = str(item.get("team_id") or item.get("id") or "")
            team_row = team_rows_by_source_id.get(source_team_id) or team_rows_by_source_id.get(short_team_id(source_team_id))
            if not team_row:
                continue
            raw_value = item.get("count")
            numeric_value, value_unit = parse_team_stat_numeric(raw_value, metric_type)
            rows.append(
                {
                    "team_id": team_row["id"],
                    "metric_type": metric_type,
                    "metric_name": metric_name,
                    "rank": to_int(item.get("rank")),
                    "raw_value": str(raw_value) if raw_value is not None else None,
                    "numeric_value": numeric_value,
                    "value_unit": value_unit,
                    "source": "dongqiudi",
                    "source_type": "world_cup_team_ranking",
                    "source_team_id": source_team_id,
                    "source_url": source_url,
                    "source_confidence": Decimal("0.86"),
                    "snapshot_id": snapshot_id,
                    "as_of_at": AS_OF_AT,
                    "metadata": {
                        "team_code": team_row["code"],
                        "team_name": item.get("team_name") or item.get("name"),
                        "metric_type": metric_type,
                        "metric_name": metric_name,
                        "raw_row": item,
                    },
                }
            )
    return rows


def upsert_team_stat_snapshots(db, rows: list[dict]) -> int:
    db.execute(
        delete(team_stat_snapshots).where(
            team_stat_snapshots.c.source == "dongqiudi",
            team_stat_snapshots.c.source_type == "world_cup_team_ranking",
            team_stat_snapshots.c.as_of_at == AS_OF_AT,
        )
    )
    if not rows:
        return 0
    statement = (
        pg_insert(team_stat_snapshots)
        .values(rows)
        .on_conflict_do_update(
            index_elements=["team_id", "metric_type", "as_of_at", "source"],
            set_={
                "metric_name": pg_insert(team_stat_snapshots).excluded.metric_name,
                "rank": pg_insert(team_stat_snapshots).excluded.rank,
                "raw_value": pg_insert(team_stat_snapshots).excluded.raw_value,
                "numeric_value": pg_insert(team_stat_snapshots).excluded.numeric_value,
                "value_unit": pg_insert(team_stat_snapshots).excluded.value_unit,
                "source_type": pg_insert(team_stat_snapshots).excluded.source_type,
                "source_team_id": pg_insert(team_stat_snapshots).excluded.source_team_id,
                "source_url": pg_insert(team_stat_snapshots).excluded.source_url,
                "source_confidence": pg_insert(team_stat_snapshots).excluded.source_confidence,
                "snapshot_id": pg_insert(team_stat_snapshots).excluded.snapshot_id,
                "metadata": pg_insert(team_stat_snapshots).excluded["metadata"],
                "updated_at": text("now()"),
            },
        )
    )
    db.execute(statement)
    return len(rows)


def cleanup_non_player_roster_records(db) -> int:
    invalid_codes = [
        row.code
        for row in db.execute(
            select(players.c.code).where(
                players.c.code.like("DQD-P%"),
                players.c.position.notin_(["FW", "MF", "DF", "GK"]),
            )
        ).mappings().all()
    ]
    for code in invalid_codes:
        db.execute(
            delete(data_source_links).where(
                data_source_links.c.entity_key == code,
                data_source_links.c.source == "dongqiudi",
                data_source_links.c.source_type.in_(["team_member_v2", "team_member_v2_market_value", "player_profile_market_value"]),
            )
        )
        db.execute(
            delete(data_source_links).where(
                data_source_links.c.entity_key.like(f"{code}:%"),
                data_source_links.c.source == "dongqiudi",
                data_source_links.c.source_type == "team_member_v2_statistic",
            )
        )
    if invalid_codes:
        db.execute(delete(players).where(players.c.code.in_(invalid_codes)))
    return len(invalid_codes)


def cleanup_non_dongqiudi_player_rows(db) -> int:
    fifa_codes = [
        row.code
        for row in db.execute(select(players.c.code).where(players.c.code.like("FIFA-%"))).mappings().all()
    ]
    if not fifa_codes:
        return 0
    db.execute(
        delete(data_source_links).where(
            data_source_links.c.entity_key.in_(fifa_codes),
            data_source_links.c.entity_type.in_(["player", "player_market_value"]),
        )
    )
    db.execute(delete(players).where(players.c.code.in_(fifa_codes)))
    return len(fifa_codes)


def cleanup_fifa_squad_only_coaches(db) -> int:
    coach_ids = [
        row.id
        for row in db.execute(
            text(
                """
                select c.id
                from coaches c
                join teams t on t.id = c.team_id
                where exists (
                    select 1
                    from data_source_links l
                    where l.entity_type = 'coach'
                      and l.entity_key = t.code || ':' || c.name_zh
                      and l.source = 'fifa'
                      and l.source_type = 'official_squad_list'
                )
                  and not exists (
                    select 1
                    from data_source_links l
                    where l.entity_type = 'coach'
                      and l.entity_key = t.code || ':' || c.name_zh
                      and not (l.source = 'fifa' and l.source_type = 'official_squad_list')
                )
                """
            )
        ).mappings().all()
    ]
    if coach_ids:
        db.execute(delete(coaches).where(coaches.c.id.in_(coach_ids)))
    db.execute(
        delete(data_source_links).where(
            data_source_links.c.source == "fifa",
            data_source_links.c.source_type == "official_squad_list",
        )
    )
    return len(coach_ids)


def run() -> dict:
    ranking_html = fetch_text(RANKING_TEAM_URL)
    team_refs = parse_world_cup_teams(ranking_html)
    team_payloads = collect_all_teams(team_refs)
    team_rankings = fetch_team_rankings()
    payload = {"ranking_url": RANKING_TEAM_URL, "teams": team_payloads}

    with SessionLocal() as db:
        snapshot_id = write_raw_snapshot(
            db,
            "world_cup_team_details",
            RANKING_TEAM_URL,
            payload,
            "dongqiudi_world_cup_team_details_v1",
        )
        team_ranking_snapshot_id = write_raw_snapshot(
            db,
            "world_cup_team_rankings",
            TEAM_RANKING_TYPES_URL,
            team_rankings,
            "dongqiudi_world_cup_team_rankings_v1",
        )
        index = team_index(db)
        links = []
        team_rows_by_source_id = {}
        team_code_by_source_id = {}
        teams_written = 0
        players_written = 0
        player_forms_written = 0
        coaches_written = 0
        team_market_values = 0
        team_stat_rows_written = 0
        errors = []

        for team_data in team_payloads:
            if team_data.get("error"):
                errors.append({"team_id": team_data["team_id"], "error": team_data["error"]})
                continue
            team_row = ensure_team(db, index, team_data)
            team_rows_by_source_id[team_row["source_team_id"]] = team_row
            team_rows_by_source_id[short_team_id(team_row["source_team_id"])] = team_row
            team_code_by_source_id[team_row["source_team_id"]] = team_row["code"]
            team_code_by_source_id[short_team_id(team_row["source_team_id"])] = team_row["code"]
            teams_written += 1
            links.extend(update_team_ranking(db, team_row, team_data, snapshot_id))
            if team_data.get("page_market_value_eur"):
                team_market_values += 1
                links.append(
                    source_link(
                        "team_market_value",
                        team_row["code"],
                        "team_profile_market_value",
                        team_data["source_urls"]["page"],
                        snapshot_id,
                        team_row["source_team_id"],
                        0.86,
                        {
                            "source_team_id": team_row["source_team_id"],
                            "team_name": team_row["name_zh"],
                            "team_en_name": team_row["name_en"],
                            "market_value_eur": team_data["page_market_value_eur"],
                        },
                    )
                )

        links.extend(team_stat_source_links(team_rankings, team_code_by_source_id, team_ranking_snapshot_id))
        team_stat_rows_written = upsert_team_stat_snapshots(
            db,
            team_stat_snapshot_rows(team_rankings, team_rows_by_source_id, team_ranking_snapshot_id),
        )

        for team_data in team_payloads:
            team_row = team_rows_by_source_id.get(str((team_data.get("detail") or {}).get("base_info", {}).get("team_id") or team_data.get("team_id")))
            if team_data.get("error") or not team_row:
                continue
            roster_result = upsert_roster_players(db, team_row, team_data, snapshot_id)
            players_written += roster_result["players"]
            player_forms_written += roster_result["player_forms"]
            links.extend(roster_result["links"])
            coach_result = upsert_coaches(db, team_row, team_data, snapshot_id)
            coaches_written += coach_result["coaches"]
            links.extend(coach_result["links"])

        links_written = write_source_links(db, links)
        avatar_cache_result = update_player_avatar_cache(team_payloads)
        non_player_roster_records_removed = cleanup_non_player_roster_records(db)
        non_dongqiudi_player_rows_removed = cleanup_non_dongqiudi_player_rows(db)
        fifa_squad_only_coaches_removed = cleanup_fifa_squad_only_coaches(db)
        counts = db.execute(
            select(
                func.count().label("players_total"),
                func.count(players.c.market_value_eur).label("players_with_market_value"),
            ).select_from(players)
        ).mappings().one()
        db.commit()

    return {
        "world_cup_teams_found": len(team_refs),
        "team_payloads_ok": len([team for team in team_payloads if not team.get("error")]),
        "teams_written": teams_written,
        "team_market_values": team_market_values,
        "roster_players_written": players_written,
        "player_form_rows_written": player_forms_written,
        "coaches_written": coaches_written,
        "team_ranking_metrics": len(team_rankings.get("rankings") or []),
        "team_stat_rows_written": team_stat_rows_written,
        **avatar_cache_result,
        "non_player_roster_records_removed": non_player_roster_records_removed,
        "non_dongqiudi_player_rows_removed": non_dongqiudi_player_rows_removed,
        "fifa_squad_only_coaches_removed": fifa_squad_only_coaches_removed,
        "source_links_written": links_written,
        "players_total": int(counts.players_total),
        "players_with_market_value": int(counts.players_with_market_value),
        "errors": errors,
    }


def main() -> None:
    print(json.dumps(run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
