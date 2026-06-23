from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import asc, insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.schema import collector_runs, data_source_links, historical_international_matches, players, raw_snapshots, teams
from app.db.session import SessionLocal
from app.predictions.small_outcome_model import HistoricalMatch, TeamState, update_states

SOURCE = "internal_model"
SOURCE_TYPE = "elo_from_historical_results"
SOURCE_URL = "internal://historical_international_matches/elo"
PARSER_VERSION = "team_elo_from_results_v1"


def checksum(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_historical_matches(db) -> list[HistoricalMatch]:
    home_team = teams.alias("home_team")
    away_team = teams.alias("away_team")
    rows = db.execute(
        select(
            historical_international_matches.c.source_match_id,
            historical_international_matches.c.played_at,
            historical_international_matches.c.home_team_id,
            historical_international_matches.c.away_team_id,
            home_team.c.code.label("home_team_code"),
            away_team.c.code.label("away_team_code"),
            historical_international_matches.c.home_score,
            historical_international_matches.c.away_score,
            historical_international_matches.c.tournament,
            historical_international_matches.c.neutral,
        )
        .select_from(
            historical_international_matches.join(
                home_team, historical_international_matches.c.home_team_id == home_team.c.id
            ).join(away_team, historical_international_matches.c.away_team_id == away_team.c.id)
        )
        .order_by(asc(historical_international_matches.c.played_at), asc(historical_international_matches.c.source_match_id))
    ).mappings().all()
    return [
        HistoricalMatch(
            match_id=str(row.source_match_id),
            played_at=row.played_at,
            home_team_id=str(row.home_team_id),
            away_team_id=str(row.away_team_id),
            home_team_code=row.home_team_code,
            away_team_code=row.away_team_code,
            home_score=int(row.home_score),
            away_score=int(row.away_score),
            tournament=row.tournament or "",
            neutral=bool(row.neutral),
        )
        for row in rows
    ]


def compute_final_states(matches_: list[HistoricalMatch]) -> dict[str, TeamState]:
    states: dict[str, TeamState] = {}
    for match in sorted(matches_, key=lambda item: (item.played_at, item.match_id)):
        home = states.setdefault(match.home_team_id, TeamState())
        away = states.setdefault(match.away_team_id, TeamState())
        update_states(home, away, match)
    return states


def roster_team_ids(db) -> set[str]:
    rows = db.execute(
        select(teams.c.id)
        .select_from(teams.join(players, players.c.team_id == teams.c.id))
        .where(players.c.code.like("DQD-P%"))
        .distinct()
    ).mappings().all()
    return {str(row.id) for row in rows}


def write_raw_snapshot(db, payload: dict):
    digest = checksum(payload)
    statement = (
        pg_insert(raw_snapshots)
        .values(
            source=SOURCE,
            source_type=SOURCE_TYPE,
            source_url=SOURCE_URL,
            checksum=digest,
            payload=payload,
            parser_version=PARSER_VERSION,
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


def write_source_links(db, rows: list[dict]) -> int:
    if not rows:
        return 0
    db.execute(
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
    )
    return len(rows)


def update_team_elos(db, states: dict[str, TeamState], snapshot_id, roster_only: bool = False) -> dict:
    scoped_roster_team_ids = roster_team_ids(db)
    target_ids = set(states)
    if roster_only:
        target_ids &= scoped_roster_team_ids
    rows = db.execute(select(teams.c.id, teams.c.code).where(teams.c.id.in_([UUID(value) for value in target_ids]))).mappings().all()
    links = []
    updated = 0
    roster_updated = 0
    for row in rows:
        state = states[str(row.id)]
        rating = round(float(state.elo), 2)
        db.execute(update(teams).where(teams.c.id == row.id).values(elo_rating=rating, updated_at=text("now()")))
        links.append(
            {
                "entity_type": "team_elo_rating",
                "entity_key": row.code,
                "source": SOURCE,
                "source_type": SOURCE_TYPE,
                "source_url": SOURCE_URL,
                "raw_snapshot_id": snapshot_id,
                "source_record_id": row.code,
                "confidence": 0.9,
                "metadata": {
                    "elo_rating": rating,
                    "matches": state.matches,
                    "last_played_at": state.last_played_at.isoformat() if state.last_played_at else None,
                    "formula": "app.predictions.small_outcome_model.update_states",
                },
            }
        )
        updated += 1
        if str(row.id) in scoped_roster_team_ids:
            roster_updated += 1
    return {"teams_updated": updated, "roster_teams_updated": roster_updated, "source_links": write_source_links(db, links)}


def record_run(db, status: str, records_read: int, records_written: int, error: str | None = None) -> None:
    db.execute(
        insert(collector_runs).values(
            source=SOURCE,
            job_type=SOURCE_TYPE,
            status=status,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            records_read=records_read,
            records_written=records_written,
            error_message=error,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Update team Elo ratings from actual historical international results.")
    parser.add_argument("--roster-only", action="store_true", help="Only update teams with Dongqiudi World Cup roster coverage.")
    parser.add_argument("--dry-run", action="store_true", help="Compute ratings without writing teams.")
    args = parser.parse_args()

    with SessionLocal() as db:
        matches_ = load_historical_matches(db)
        states = compute_final_states(matches_)
        roster_ids = roster_team_ids(db)
        payload = {
            "computed_at": datetime.now(UTC).isoformat(),
            "historical_matches": len(matches_),
            "teams_with_state": len(states),
            "roster_teams_with_state": len(set(states) & roster_ids),
            "roster_only": args.roster_only,
            "latest_played_at": max((item.played_at.isoformat() for item in matches_), default=None),
            "ratings": {
                team_id: {
                    "elo_rating": round(float(state.elo), 2),
                    "matches": state.matches,
                    "last_played_at": state.last_played_at.isoformat() if state.last_played_at else None,
                }
                for team_id, state in sorted(states.items())
            },
        }
        if args.dry_run:
            result = {key: payload[key] for key in ("historical_matches", "teams_with_state", "roster_teams_with_state", "latest_played_at")}
        else:
            snapshot_id = write_raw_snapshot(db, payload)
            result = update_team_elos(db, states, snapshot_id, roster_only=args.roster_only)
            result.update(
                {
                    "historical_matches": len(matches_),
                    "teams_with_state": len(states),
                    "roster_teams_with_state": len(set(states) & roster_ids),
                    "latest_played_at": payload["latest_played_at"],
                    "snapshot_id": str(snapshot_id),
                }
            )
            record_run(db, "success", len(matches_), result["teams_updated"])
            db.commit()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
