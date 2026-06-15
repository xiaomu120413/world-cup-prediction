from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import date, datetime, time, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import and_, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.collectors.normalizers import normalize_team_ref, slugify
from app.db.schema import (
    collector_runs,
    data_source_links,
    historical_international_matches,
    raw_snapshots,
    team_aliases,
    team_match_results,
    teams,
)
from app.db.session import SessionLocal

SOURCE = "martj42_international_results"
SOURCE_TYPE = "historical_results"
DEFAULT_RESULTS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
BATCH_SIZE = 2000


def checksum(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def source_headers() -> dict[str, str]:
    return {
        "User-Agent": "world-cup-prediction-bot/0.1 (+historical-results-import)",
        "Accept": "text/csv,text/plain;q=0.9,*/*;q=0.8",
    }


def read_csv_text(args: argparse.Namespace) -> tuple[str, str]:
    if args.csv_path:
        path = args.csv_path.resolve()
        return str(path), path.read_text(encoding="utf-8-sig")

    response = httpx.get(args.csv_url, headers=source_headers(), timeout=60.0, follow_redirects=True)
    response.raise_for_status()
    return args.csv_url, response.text


def parse_rows(csv_text: str, since: date | None = None, until: date | None = None) -> list[dict]:
    rows: list[dict] = []
    reader = csv.DictReader(csv_text.splitlines())
    required = {"date", "home_team", "away_team", "home_score", "away_score", "tournament", "city", "country", "neutral"}
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")

    for line_number, row in enumerate(reader, start=2):
        match_date = date.fromisoformat(row["date"])
        if since and match_date < since:
            continue
        if until and match_date > until:
            continue
        try:
            home_score = int(row["home_score"])
            away_score = int(row["away_score"])
        except ValueError:
            continue
        rows.append(
            {
                "line_number": line_number,
                "date": match_date.isoformat(),
                "home_team": row["home_team"].strip(),
                "away_team": row["away_team"].strip(),
                "home_score": home_score,
                "away_score": away_score,
                "tournament": row["tournament"].strip(),
                "city": row["city"].strip(),
                "country": row["country"].strip(),
                "neutral": row["neutral"].strip().lower() == "true",
            }
        )
    return rows


def source_match_base(row: dict) -> str:
    value = "|".join(
        str(row[key])
        for key in ("date", "home_team", "away_team", "home_score", "away_score", "tournament", "city", "country", "neutral")
    )
    return f"martj42-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:24]}"


def played_at(row: dict) -> datetime:
    return datetime.combine(date.fromisoformat(row["date"]), time(hour=12), tzinfo=timezone.utc)


def normalize_alias(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def team_code_from_name(name: str) -> str:
    normalized = normalize_team_ref(name)
    if normalized:
        return normalized["code"]
    return slugify(name).upper()[:32] or hashlib.sha256(name.encode("utf-8")).hexdigest()[:12].upper()


def load_team_index(db) -> dict[str, Any]:
    by_alias: dict[str, Any] = {}
    for row in db.execute(select(teams.c.id, teams.c.code, teams.c.name_zh, teams.c.name_en)).mappings().all():
        for value in (row.code, row.name_zh, row.name_en):
            key = normalize_alias(value)
            if key:
                by_alias[key] = row
    alias_rows = db.execute(
        select(team_aliases.c.alias, teams.c.id, teams.c.code)
        .select_from(team_aliases.join(teams, team_aliases.c.team_id == teams.c.id))
    ).mappings().all()
    for row in alias_rows:
        key = normalize_alias(row.alias)
        if key:
            by_alias[key] = row
    return {"by_alias": by_alias}


def ensure_team(db, index: dict[str, Any], name: str) -> dict:
    key = normalize_alias(name)
    existing = index["by_alias"].get(key)
    if existing:
        return {"id": existing.id, "code": existing.code}

    normalized = normalize_team_ref(name) or {
        "code": team_code_from_name(name),
        "name_zh": name,
        "name_en": name,
        "aliases": [name],
    }
    team_id = db.execute(
        pg_insert(teams)
        .values(
            code=normalized["code"],
            name_zh=normalized["name_zh"],
            name_en=normalized["name_en"],
            quality_status="source",
        )
        .on_conflict_do_update(
            index_elements=["code"],
            set_={
                "name_zh": func.coalesce(teams.c.name_zh, pg_insert(teams).excluded.name_zh),
                "name_en": func.coalesce(teams.c.name_en, pg_insert(teams).excluded.name_en),
                "quality_status": "source",
                "updated_at": text("now()"),
            },
        )
        .returning(teams.c.id)
    ).scalar_one()
    aliases = {name, normalized["code"], *(normalized.get("aliases") or [])}
    for alias in {item.strip() for item in aliases if item and item.strip()}:
        db.execute(
            pg_insert(team_aliases)
            .values(
                team_id=team_id,
                source=SOURCE,
                source_team_id=f"{normalized['code']}:{alias}",
                alias=alias,
                confidence=0.95,
                is_primary=alias == name,
            )
            .on_conflict_do_nothing()
        )
    row = {"id": team_id, "code": normalized["code"]}
    for alias in aliases:
        alias_key = normalize_alias(alias)
        if alias_key:
            index["by_alias"][alias_key] = SimpleNamespace(**row)
    return row


def result_for(goals_for: int, goals_against: int) -> str:
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


def write_raw_snapshot(db, source_url: str, rows: list[dict]):
    payload = {
        "source_url": source_url,
        "row_count": len(rows),
        "min_date": min((row["date"] for row in rows), default=None),
        "max_date": max((row["date"] for row in rows), default=None),
        "rows": rows,
    }
    digest = checksum(payload)
    statement = (
        pg_insert(raw_snapshots)
        .values(
            source=SOURCE,
            source_type=SOURCE_TYPE,
            source_url=source_url,
            checksum=digest,
            payload=payload,
            parser_version="martj42_international_results_v1",
        )
        .on_conflict_do_nothing(index_elements=["source", "source_type", "checksum"])
        .returning(raw_snapshots.c.id)
    )
    inserted = db.execute(statement).scalar_one_or_none()
    if inserted:
        return inserted
    return db.execute(
        select(raw_snapshots.c.id).where(
            raw_snapshots.c.source == SOURCE,
            raw_snapshots.c.source_type == SOURCE_TYPE,
            raw_snapshots.c.checksum == digest,
        )
    ).scalar_one()


def write_batches(db, table, rows: list[dict], conflict_columns: list[str], update_set: dict) -> int:
    written = 0
    for offset in range(0, len(rows), BATCH_SIZE):
        batch = rows[offset : offset + BATCH_SIZE]
        if not batch:
            continue
        db.execute(
            pg_insert(table)
            .values(batch)
            .on_conflict_do_update(index_elements=conflict_columns, set_=update_set)
        )
        written += len(batch)
    return written


def write_source_links(db, rows: list[dict]) -> int:
    written = 0
    for offset in range(0, len(rows), BATCH_SIZE):
        batch = rows[offset : offset + BATCH_SIZE]
        if not batch:
            continue
        db.execute(
            pg_insert(data_source_links)
            .values(batch)
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
        written += len(batch)
    return written


def import_rows(db, rows: list[dict], source_url: str) -> dict:
    snapshot_id = write_raw_snapshot(db, source_url, rows)
    index = load_team_index(db)
    historical_rows = []
    result_rows = []
    links = []
    team_pairs: dict[str, dict] = {}

    for row in rows:
        home = ensure_team(db, index, row["home_team"])
        away = ensure_team(db, index, row["away_team"])
        match_base = source_match_base(row)
        played = played_at(row)
        team_pairs[home["code"]] = {"id": home["id"], "name": row["home_team"]}
        team_pairs[away["code"]] = {"id": away["id"], "name": row["away_team"]}
        historical_rows.append(
            {
                "source_match_id": match_base,
                "match_date": date.fromisoformat(row["date"]),
                "played_at": played,
                "home_team_id": home["id"],
                "away_team_id": away["id"],
                "home_team_name": row["home_team"],
                "away_team_name": row["away_team"],
                "home_score": row["home_score"],
                "away_score": row["away_score"],
                "tournament": row["tournament"],
                "city": row["city"],
                "country": row["country"],
                "neutral": row["neutral"],
                "source": SOURCE,
                "source_type": SOURCE_TYPE,
                "source_url": source_url,
                "source_line_number": row["line_number"],
                "source_confidence": 0.9,
                "snapshot_id": snapshot_id,
                "metadata": {
                    "source_dataset": "martj42/international_results",
                    "line_number": row["line_number"],
                },
            }
        )
        links.append(
            {
                "entity_type": "historical_international_match",
                "entity_key": match_base,
                "source": SOURCE,
                "source_type": SOURCE_TYPE,
                "source_url": source_url,
                "raw_snapshot_id": snapshot_id,
                "source_record_id": match_base,
                "confidence": 0.9,
                "metadata": {
                    "line_number": row["line_number"],
                    "date": row["date"],
                    "home_team": row["home_team"],
                    "away_team": row["away_team"],
                    "home_score": row["home_score"],
                    "away_score": row["away_score"],
                    "tournament": row["tournament"],
                    "city": row["city"],
                    "country": row["country"],
                    "neutral": row["neutral"],
                },
            }
        )
        sides = (
            ("home", home, away, row["home_score"], row["away_score"]),
            ("away", away, home, row["away_score"], row["home_score"]),
        )
        for side, team, opponent, goals_for, goals_against in sides:
            opponent_rank = db.execute(select(teams.c.fifa_rank).where(teams.c.id == opponent["id"])).scalar_one_or_none()
            source_match_id = f"{match_base}:{side}"
            result_rows.append(
                {
                    "team_id": team["id"],
                    "opponent_team_id": opponent["id"],
                    "played_at": played,
                    "competition_name": row["tournament"],
                    "source_match_id": source_match_id,
                    "is_neutral": row["neutral"],
                    "goals_for": goals_for,
                    "goals_against": goals_against,
                    "result": result_for(goals_for, goals_against),
                    "opponent_rank": opponent_rank,
                    "opponent_rank_bucket": rank_bucket(opponent_rank),
                    "source_confidence": 0.9,
                    "snapshot_id": snapshot_id,
                }
            )
            links.append(
                {
                    "entity_type": "team_match_result",
                    "entity_key": f"{team['id']}:{source_match_id}",
                    "source": SOURCE,
                    "source_type": SOURCE_TYPE,
                    "source_url": source_url,
                    "raw_snapshot_id": snapshot_id,
                    "source_record_id": source_match_id,
                    "confidence": 0.9,
                    "metadata": {
                        "line_number": row["line_number"],
                        "date": row["date"],
                        "home_team": row["home_team"],
                        "away_team": row["away_team"],
                        "side": side,
                        "city": row["city"],
                        "country": row["country"],
                    },
                }
            )

    for code, team in team_pairs.items():
        links.append(
            {
                "entity_type": "team",
                "entity_key": code,
                "source": SOURCE,
                "source_type": SOURCE_TYPE,
                "source_url": source_url,
                "raw_snapshot_id": snapshot_id,
                "source_record_id": code,
                "confidence": 0.9,
                "metadata": {
                    "source_name": team["name"],
                    "import_role": "historical_results_team",
                },
            }
        )

    historical_update_set = {
        "match_date": pg_insert(historical_international_matches).excluded.match_date,
        "played_at": pg_insert(historical_international_matches).excluded.played_at,
        "home_team_id": pg_insert(historical_international_matches).excluded.home_team_id,
        "away_team_id": pg_insert(historical_international_matches).excluded.away_team_id,
        "home_team_name": pg_insert(historical_international_matches).excluded.home_team_name,
        "away_team_name": pg_insert(historical_international_matches).excluded.away_team_name,
        "home_score": pg_insert(historical_international_matches).excluded.home_score,
        "away_score": pg_insert(historical_international_matches).excluded.away_score,
        "tournament": pg_insert(historical_international_matches).excluded.tournament,
        "city": pg_insert(historical_international_matches).excluded.city,
        "country": pg_insert(historical_international_matches).excluded.country,
        "neutral": pg_insert(historical_international_matches).excluded.neutral,
        "source": pg_insert(historical_international_matches).excluded.source,
        "source_type": pg_insert(historical_international_matches).excluded.source_type,
        "source_url": pg_insert(historical_international_matches).excluded.source_url,
        "source_line_number": pg_insert(historical_international_matches).excluded.source_line_number,
        "source_confidence": pg_insert(historical_international_matches).excluded.source_confidence,
        "snapshot_id": pg_insert(historical_international_matches).excluded.snapshot_id,
        "metadata": pg_insert(historical_international_matches).excluded["metadata"],
        "updated_at": text("now()"),
    }
    result_update_set = {
        "opponent_team_id": pg_insert(team_match_results).excluded.opponent_team_id,
        "played_at": pg_insert(team_match_results).excluded.played_at,
        "competition_name": pg_insert(team_match_results).excluded.competition_name,
        "is_neutral": pg_insert(team_match_results).excluded.is_neutral,
        "goals_for": pg_insert(team_match_results).excluded.goals_for,
        "goals_against": pg_insert(team_match_results).excluded.goals_against,
        "result": pg_insert(team_match_results).excluded.result,
        "opponent_rank": pg_insert(team_match_results).excluded.opponent_rank,
        "opponent_rank_bucket": pg_insert(team_match_results).excluded.opponent_rank_bucket,
        "source_confidence": pg_insert(team_match_results).excluded.source_confidence,
        "snapshot_id": pg_insert(team_match_results).excluded.snapshot_id,
        "updated_at": text("now()"),
    }
    historical_written = write_batches(
        db,
        historical_international_matches,
        historical_rows,
        ["source_match_id"],
        historical_update_set,
    )
    results_written = write_batches(db, team_match_results, result_rows, ["team_id", "source_match_id"], result_update_set)
    links_written = write_source_links(db, links)
    return {
        "snapshot_id": str(snapshot_id),
        "matches_read": len(rows),
        "historical_matches_upserted": historical_written,
        "team_match_results_upserted": results_written,
        "source_links_upserted": links_written,
        "teams_touched": len(team_pairs),
        "min_date": min((row["date"] for row in rows), default=None),
        "max_date": max((row["date"] for row in rows), default=None),
    }


def record_collector_run(db, status: str, records_read: int, records_written: int, snapshot_ids: list[str] | None, error: str | None = None) -> None:
    parsed_snapshot_ids = [UUID(value) for value in snapshot_ids] if snapshot_ids else None
    db.execute(
        pg_insert(collector_runs).values(
            source=SOURCE,
            job_type=SOURCE_TYPE,
            status=status,
            records_read=records_read,
            records_written=records_written,
            error_message=error,
            snapshot_ids=parsed_snapshot_ids,
            finished_at=text("now()"),
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import historical men's international football results.")
    parser.add_argument("--csv-url", default=DEFAULT_RESULTS_URL)
    parser.add_argument("--csv-path", type=Path)
    parser.add_argument("--since", type=date.fromisoformat)
    parser.add_argument("--until", type=date.fromisoformat)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source_url, csv_text = read_csv_text(args)
    rows = parse_rows(csv_text, since=args.since, until=args.until)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "status": "dry_run_ok",
                    "source_url": source_url,
                    "matches_read": len(rows),
                    "historical_matches_to_write": len(rows),
                    "team_match_results_to_write": len(rows) * 2,
                    "min_date": min((row["date"] for row in rows), default=None),
                    "max_date": max((row["date"] for row in rows), default=None),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    with SessionLocal() as db:
        try:
            result = import_rows(db, rows, source_url)
            record_collector_run(
                db,
                "success",
                records_read=result["matches_read"],
                records_written=result["historical_matches_upserted"],
                snapshot_ids=[result["snapshot_id"]],
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            record_collector_run(db, "failed", records_read=len(rows), records_written=0, snapshot_ids=None, error=str(exc))
            db.commit()
            raise

    print(json.dumps({"status": "imported", **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
