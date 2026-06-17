from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlalchemy import func, or_, select

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.schema import historical_international_matches, players, teams
from app.db.session import SessionLocal
from collect_historical_international_results import (
    DEFAULT_RESULTS_URL,
    import_rows,
    parse_rows,
    read_csv_text,
    record_collector_run,
)

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "exports"


def refresh_historical_results(args: argparse.Namespace) -> dict[str, Any]:
    source_args = SimpleNamespace(csv_path=args.csv_path, csv_url=args.csv_url)
    source_url, csv_text = read_csv_text(source_args)
    rows = parse_rows(csv_text, since=args.source_since, until=args.source_until)

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
            return result
        except Exception as exc:
            db.rollback()
            record_collector_run(
                db,
                "failed",
                records_read=len(rows),
                records_written=0,
                snapshot_ids=None,
                error=str(exc),
            )
            db.commit()
            raise


def use_existing_historical_results_after_refresh_error(exc: Exception) -> dict[str, Any]:
    with SessionLocal() as db:
        existing_count = int(db.scalar(select(func.count()).select_from(historical_international_matches)) or 0)
        if existing_count <= 0:
            raise exc

        error_message = f"{type(exc).__name__}: {exc}"
        record_collector_run(
            db,
            "partial",
            records_read=existing_count,
            records_written=0,
            snapshot_ids=None,
            error=f"Source refresh failed; continued with existing historical data. {error_message}",
        )
        db.commit()

    return {
        "status": "partial_existing_data",
        "historical_matches_existing": existing_count,
        "error": error_message,
    }


def result_label(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "home_win"
    if home_score < away_score:
        return "away_win"
    return "draw"


def export_matches(output_dir: Path, since: date | None = None, until: date | None = None) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    matches_csv = output_dir / "world_cup_48_national_team_matches_latest.csv"
    latest_by_team_csv = output_dir / "world_cup_48_national_team_latest_match_by_team.csv"
    summary_json = output_dir / "world_cup_48_national_team_matches_summary.json"

    with SessionLocal() as db:
        roster_team_ids_sq = select(players.c.team_id).where(players.c.code.like("DQD-P%")).distinct().subquery()
        roster_rows = (
            db.execute(
                select(teams.c.id, teams.c.code, teams.c.name_zh, teams.c.name_en, teams.c.fifa_rank)
                .select_from(teams.join(roster_team_ids_sq, teams.c.id == roster_team_ids_sq.c.team_id))
                .order_by(teams.c.code.asc())
            )
            .mappings()
            .all()
        )
        roster_ids = {row.id for row in roster_rows}
        roster_codes = {row.code for row in roster_rows}

        home = teams.alias("home")
        away = teams.alias("away")
        filters = [
            or_(
                historical_international_matches.c.home_team_id.in_(roster_ids),
                historical_international_matches.c.away_team_id.in_(roster_ids),
            )
        ]
        if since:
            filters.append(historical_international_matches.c.match_date >= since)
        if until:
            filters.append(historical_international_matches.c.match_date <= until)

        match_rows = (
            db.execute(
                select(
                    historical_international_matches.c.source_match_id,
                    historical_international_matches.c.match_date,
                    home.c.code.label("home_team_code"),
                    home.c.name_zh.label("home_team_name_zh"),
                    home.c.name_en.label("home_team_name_en"),
                    away.c.code.label("away_team_code"),
                    away.c.name_zh.label("away_team_name_zh"),
                    away.c.name_en.label("away_team_name_en"),
                    historical_international_matches.c.home_team_name.label("source_home_team_name"),
                    historical_international_matches.c.away_team_name.label("source_away_team_name"),
                    historical_international_matches.c.home_score,
                    historical_international_matches.c.away_score,
                    historical_international_matches.c.tournament,
                    historical_international_matches.c.city,
                    historical_international_matches.c.country,
                    historical_international_matches.c.neutral,
                    historical_international_matches.c.source,
                    historical_international_matches.c.source_type,
                    historical_international_matches.c.source_url,
                    historical_international_matches.c.source_line_number,
                    historical_international_matches.c.source_confidence,
                )
                .select_from(
                    historical_international_matches.join(
                        home, historical_international_matches.c.home_team_id == home.c.id
                    ).join(away, historical_international_matches.c.away_team_id == away.c.id)
                )
                .where(*filters)
                .order_by(
                    historical_international_matches.c.match_date.asc(),
                    historical_international_matches.c.source_line_number.asc(),
                )
            )
            .mappings()
            .all()
        )

    match_fieldnames = [
        "source_match_id",
        "match_date",
        "home_team_code",
        "home_team_name_zh",
        "home_team_name_en",
        "away_team_code",
        "away_team_name_zh",
        "away_team_name_en",
        "source_home_team_name",
        "source_away_team_name",
        "home_score",
        "away_score",
        "result_label",
        "tournament",
        "city",
        "country",
        "neutral",
        "home_is_world_cup_48",
        "away_is_world_cup_48",
        "world_cup_48_team_codes",
        "source",
        "source_type",
        "source_url",
        "source_line_number",
        "source_confidence",
    ]
    latest_by_team: dict[str, dict[str, Any]] = {}
    per_team_match_counts: dict[str, int] = {}

    with matches_csv.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=match_fieldnames)
        writer.writeheader()
        for row in match_rows:
            home_in = row.home_team_code in roster_codes
            away_in = row.away_team_code in roster_codes
            team_codes = [
                code
                for code, is_in in ((row.home_team_code, home_in), (row.away_team_code, away_in))
                if is_in
            ]
            export_row = {
                "source_match_id": row.source_match_id,
                "match_date": row.match_date.isoformat(),
                "home_team_code": row.home_team_code,
                "home_team_name_zh": row.home_team_name_zh,
                "home_team_name_en": row.home_team_name_en,
                "away_team_code": row.away_team_code,
                "away_team_name_zh": row.away_team_name_zh,
                "away_team_name_en": row.away_team_name_en,
                "source_home_team_name": row.source_home_team_name,
                "source_away_team_name": row.source_away_team_name,
                "home_score": row.home_score,
                "away_score": row.away_score,
                "result_label": result_label(row.home_score, row.away_score),
                "tournament": row.tournament,
                "city": row.city,
                "country": row.country,
                "neutral": row.neutral,
                "home_is_world_cup_48": home_in,
                "away_is_world_cup_48": away_in,
                "world_cup_48_team_codes": "|".join(team_codes),
                "source": row.source,
                "source_type": row.source_type,
                "source_url": row.source_url,
                "source_line_number": row.source_line_number,
                "source_confidence": row.source_confidence,
            }
            writer.writerow(export_row)
            for code in team_codes:
                per_team_match_counts[code] = per_team_match_counts.get(code, 0) + 1
                latest = latest_by_team.get(code)
                if latest is None or row.match_date > latest["match_date"]:
                    latest_by_team[code] = {**export_row, "team_code": code, "match_date": row.match_date}

    latest_fieldnames = [
        "team_code",
        "team_name_zh",
        "team_name_en",
        "fifa_rank",
        "latest_match_date",
        "home_team_code",
        "away_team_code",
        "home_score",
        "away_score",
        "tournament",
        "city",
        "country",
        "neutral",
        "source_home_team_name",
        "source_away_team_name",
        "source_match_id",
        "source_url",
    ]
    with latest_by_team_csv.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=latest_fieldnames)
        writer.writeheader()
        for team in sorted(roster_rows, key=lambda item: (item.fifa_rank is None, item.fifa_rank or 999, item.code)):
            latest = latest_by_team.get(team.code)
            writer.writerow(
                {
                    "team_code": team.code,
                    "team_name_zh": team.name_zh,
                    "team_name_en": team.name_en,
                    "fifa_rank": team.fifa_rank,
                    "latest_match_date": latest["match_date"].isoformat() if latest else None,
                    "home_team_code": latest["home_team_code"] if latest else None,
                    "away_team_code": latest["away_team_code"] if latest else None,
                    "home_score": latest["home_score"] if latest else None,
                    "away_score": latest["away_score"] if latest else None,
                    "tournament": latest["tournament"] if latest else None,
                    "city": latest["city"] if latest else None,
                    "country": latest["country"] if latest else None,
                    "neutral": latest["neutral"] if latest else None,
                    "source_home_team_name": latest["source_home_team_name"] if latest else None,
                    "source_away_team_name": latest["source_away_team_name"] if latest else None,
                    "source_match_id": latest["source_match_id"] if latest else None,
                    "source_url": latest["source_url"] if latest else None,
                }
            )

    summary = {
        "world_cup_teams": len(roster_rows),
        "teams_with_match_data": sum(1 for team in roster_rows if per_team_match_counts.get(team.code, 0) > 0),
        "actual_matches_involving_48_teams": len(match_rows),
        "min_match_date": match_rows[0].match_date.isoformat() if match_rows else None,
        "max_match_date": match_rows[-1].match_date.isoformat() if match_rows else None,
        "source_url": DEFAULT_RESULTS_URL,
        "per_team_match_counts": dict(sorted(per_team_match_counts.items())),
        "files": {
            "matches_csv": str(matches_csv.resolve()),
            "latest_by_team_csv": str(latest_by_team_csv.resolve()),
        },
    }
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**summary, "summary_json": str(summary_json.resolve())}


def main() -> None:
    parser = argparse.ArgumentParser(description="Export actual national-team match data for the 48 World Cup teams.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--since", type=date.fromisoformat, help="Only export matches on or after YYYY-MM-DD.")
    parser.add_argument("--until", type=date.fromisoformat, help="Only export matches on or before YYYY-MM-DD.")
    parser.add_argument("--refresh-source", action="store_true", help="Refresh historical match data before exporting.")
    parser.add_argument("--csv-url", default=DEFAULT_RESULTS_URL)
    parser.add_argument("--csv-path", type=Path)
    parser.add_argument("--source-since", type=date.fromisoformat)
    parser.add_argument("--source-until", type=date.fromisoformat)
    args = parser.parse_args()

    result: dict[str, Any] = {}
    if args.refresh_source:
        try:
            result["refresh"] = refresh_historical_results(args)
        except Exception as exc:
            result["refresh"] = use_existing_historical_results_after_refresh_error(exc)
    result["export"] = export_matches(args.output_dir, since=args.since, until=args.until)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
