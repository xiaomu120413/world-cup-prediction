from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import select, text

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.collectors.runner import CollectorRunner
from app.db.schema import players, teams
from app.db.session import SessionLocal


def rowcount(result) -> int:
    return max(result.rowcount or 0, 0)


def execute_count(db, statement: str, params: dict) -> int:
    return rowcount(db.execute(text(statement), params))


def duplicate_team_rows(db) -> list[dict]:
    roster_team_ids = select(players.c.team_id).where(players.c.code.like("DQD-P%")).distinct().subquery()
    rows = db.execute(
        select(teams.c.id, teams.c.code, teams.c.name_zh, teams.c.name_en)
        .where(teams.c.code.like("DQD%"))
        .where(teams.c.id.not_in(select(roster_team_ids.c.team_id)))
        .order_by(teams.c.name_zh)
    ).mappings().all()

    runner = CollectorRunner(db)
    values = [
        {
            "code": row["code"],
            "name_zh": row["name_zh"],
            "name_en": row["name_en"],
            "quality_status": "source",
        }
        for row in rows
    ]
    canonical_ids = runner.resolve_roster_team_ids(values)
    canonical_codes = {
        row["id"]: row["code"]
        for row in db.execute(select(teams.c.id, teams.c.code).where(teams.c.id.in_(canonical_ids.values()))).mappings()
    }

    duplicates = []
    for row in rows:
        canonical_id = canonical_ids.get(row["code"])
        if canonical_id is None:
            continue
        duplicates.append(
            {
                "duplicate_id": row["id"],
                "duplicate_code": row["code"],
                "duplicate_name": row["name_zh"],
                "canonical_id": canonical_id,
                "canonical_code": canonical_codes[canonical_id],
            }
        )
    return duplicates


def merge_one_team(db, duplicate: dict) -> dict:
    params = {"from_team_id": duplicate["duplicate_id"], "to_team_id": duplicate["canonical_id"]}
    counts = {}

    counts["team_alias_conflicts_deleted"] = execute_count(
        db,
        """
        delete from team_aliases duplicate
        using team_aliases target
        where duplicate.team_id = :from_team_id
          and target.team_id = :to_team_id
          and duplicate.id <> target.id
          and duplicate.source = target.source
          and (
            duplicate.alias = target.alias
            or duplicate.source_team_id is not distinct from target.source_team_id
          )
        """,
        params,
    )
    counts["team_aliases_updated"] = execute_count(
        db,
        "update team_aliases set team_id = :to_team_id where team_id = :from_team_id",
        params,
    )

    counts["team_match_result_conflicts_deleted"] = execute_count(
        db,
        """
        delete from team_match_results duplicate
        using team_match_results target
        where duplicate.team_id = :from_team_id
          and target.team_id = :to_team_id
          and duplicate.id <> target.id
          and duplicate.source_match_id = target.source_match_id
        """,
        params,
    )
    counts["team_match_results_updated"] = execute_count(
        db,
        "update team_match_results set team_id = :to_team_id where team_id = :from_team_id",
        params,
    )
    counts["team_match_result_opponents_updated"] = execute_count(
        db,
        "update team_match_results set opponent_team_id = :to_team_id where opponent_team_id = :from_team_id",
        params,
    )

    counts["team_stat_conflicts_deleted"] = execute_count(
        db,
        """
        delete from team_stat_snapshots duplicate
        using team_stat_snapshots target
        where duplicate.team_id = :from_team_id
          and target.team_id = :to_team_id
          and duplicate.id <> target.id
          and duplicate.metric_type = target.metric_type
          and duplicate.as_of_at = target.as_of_at
          and duplicate.source = target.source
        """,
        params,
    )
    counts["team_stats_updated"] = execute_count(
        db,
        "update team_stat_snapshots set team_id = :to_team_id where team_id = :from_team_id",
        params,
    )

    counts["coach_conflicts_deleted"] = execute_count(
        db,
        """
        delete from coaches duplicate
        using coaches target
        where duplicate.team_id = :from_team_id
          and target.team_id = :to_team_id
          and duplicate.id <> target.id
          and duplicate.name_zh = target.name_zh
        """,
        params,
    )
    counts["coaches_updated"] = execute_count(
        db,
        "update coaches set team_id = :to_team_id where team_id = :from_team_id",
        params,
    )

    counts["lineup_conflicts_deleted"] = execute_count(
        db,
        """
        delete from lineup_snapshots duplicate
        using lineup_snapshots target
        where duplicate.team_id = :from_team_id
          and target.team_id = :to_team_id
          and duplicate.id <> target.id
          and duplicate.match_id = target.match_id
          and duplicate.source_player_id is not distinct from target.source_player_id
          and duplicate.player_name = target.player_name
        """,
        params,
    )
    counts["lineups_updated"] = execute_count(
        db,
        "update lineup_snapshots set team_id = :to_team_id where team_id = :from_team_id",
        params,
    )

    counts["group_standing_conflicts_deleted"] = execute_count(
        db,
        """
        delete from group_standings duplicate
        using group_standings target
        where duplicate.team_id = :from_team_id
          and target.team_id = :to_team_id
          and duplicate.id <> target.id
          and duplicate.stage_id = target.stage_id
        """,
        params,
    )
    counts["group_standings_updated"] = execute_count(
        db,
        "update group_standings set team_id = :to_team_id where team_id = :from_team_id",
        params,
    )

    counts["group_simulation_conflicts_deleted"] = execute_count(
        db,
        """
        delete from group_simulations duplicate
        using group_simulations target
        where duplicate.team_id = :from_team_id
          and target.team_id = :to_team_id
          and duplicate.id <> target.id
          and duplicate.stage_id = target.stage_id
          and duplicate.prediction_snapshot_id = target.prediction_snapshot_id
        """,
        params,
    )
    counts["group_simulations_updated"] = execute_count(
        db,
        "update group_simulations set team_id = :to_team_id where team_id = :from_team_id",
        params,
    )

    counts["team_form_duplicates_deleted"] = execute_count(
        db,
        """
        delete from team_form_snapshots duplicate
        using team_form_snapshots target
        where duplicate.team_id = :from_team_id
          and target.team_id = :to_team_id
          and duplicate.id <> target.id
          and duplicate.as_of_at = target.as_of_at
        """,
        params,
    )

    simple_updates = {
        "players_updated": "update players set team_id = :to_team_id where team_id = :from_team_id",
        "team_forms_updated": "update team_form_snapshots set team_id = :to_team_id where team_id = :from_team_id",
        "player_forms_updated": "update player_form_snapshots set team_id = :to_team_id where team_id = :from_team_id",
        "injuries_updated": "update injury_reports set team_id = :to_team_id where team_id = :from_team_id",
        "ranking_predictions_updated": "update ranking_predictions set team_id = :to_team_id where team_id = :from_team_id",
        "matches_home_updated": "update matches set home_team_id = :to_team_id where home_team_id = :from_team_id",
        "matches_away_updated": "update matches set away_team_id = :to_team_id where away_team_id = :from_team_id",
        "historical_home_updated": (
            "update historical_international_matches set home_team_id = :to_team_id where home_team_id = :from_team_id"
        ),
        "historical_away_updated": (
            "update historical_international_matches set away_team_id = :to_team_id where away_team_id = :from_team_id"
        ),
    }
    for key, statement in simple_updates.items():
        counts[key] = execute_count(db, statement, params)

    counts["teams_deleted"] = execute_count(db, "delete from teams where id = :from_team_id", params)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge generated DQD teams into canonical roster teams by name.")
    parser.add_argument("--dry-run", action="store_true", help="Show planned merges without changing the database.")
    args = parser.parse_args()

    with SessionLocal() as db:
        duplicates = duplicate_team_rows(db)
        result = {
            "dry_run": args.dry_run,
            "teams_to_merge": len(duplicates),
            "teams": [
                {
                    "from": item["duplicate_code"],
                    "name": item["duplicate_name"],
                    "to": item["canonical_code"],
                }
                for item in duplicates
            ],
        }
        if args.dry_run:
            print(result)
            return

        totals: dict[str, int] = {}
        for duplicate in duplicates:
            for key, value in merge_one_team(db, duplicate).items():
                totals[key] = totals.get(key, 0) + value
        db.commit()
        result["totals"] = totals
        print(result)


if __name__ == "__main__":
    main()
