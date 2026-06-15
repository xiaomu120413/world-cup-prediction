from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import func, select, text

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.collectors.runner import CollectorRunner
from app.db.schema import (
    data_source_links,
    historical_international_matches,
    injury_reports,
    lineup_snapshots,
    player_aliases,
    player_form_snapshots,
    players,
    team_aliases,
    teams,
)
from app.db.session import SessionLocal


def generated_duplicate_roster_teams(db) -> list[dict]:
    roster_team_ids = select(players.c.team_id).where(players.c.code.like("DQD-P%")).distinct().subquery()
    rows = db.execute(
        select(teams.c.id, teams.c.code, teams.c.name_zh, teams.c.name_en)
        .where(teams.c.code.like("DQD%"))
        .where(teams.c.id.not_in(select(roster_team_ids.c.team_id)))
        .order_by(teams.c.name_zh)
    ).mappings().all()
    values = [
        {"code": row["code"], "name_zh": row["name_zh"], "name_en": row["name_en"], "quality_status": "source"}
        for row in rows
    ]
    canonical_ids = CollectorRunner(db).resolve_roster_team_ids(values)
    return [
        {"code": row["code"], "name": row["name_zh"], "canonical_team_id": str(canonical_ids[row["code"]])}
        for row in rows
        if row["code"] in canonical_ids
    ]


def scalar(db, sql: str) -> int:
    return int(db.execute(text(sql)).scalar_one() or 0)


def sample_rows(db, sql: str, limit: int = 10) -> list[dict]:
    return [dict(row) for row in db.execute(text(sql), {"limit": limit}).mappings().all()]


def main() -> None:
    with SessionLocal() as db:
        duplicate_teams = generated_duplicate_roster_teams(db)
        checks = {
            "generated_duplicate_roster_teams": len(duplicate_teams),
            "historical_team_names_without_source_alias": scalar(
                db,
                """
                select count(*)
                from (
                    select source, home_team_id as team_id, home_team_name as alias
                    from historical_international_matches
                    union all
                    select source, away_team_id as team_id, away_team_name as alias
                    from historical_international_matches
                ) names
                where not exists (
                    select 1
                    from team_aliases ta
                    where ta.source = names.source
                      and ta.team_id = names.team_id
                      and ta.alias = names.alias
                )
                """,
            ),
            "ambiguous_historical_team_aliases": scalar(
                db,
                """
                select count(*)
                from (
                    select source, alias
                    from (
                        select source, home_team_id as team_id, home_team_name as alias
                        from historical_international_matches
                        union all
                        select source, away_team_id as team_id, away_team_name as alias
                        from historical_international_matches
                    ) names
                    group by source, alias
                    having count(distinct team_id) > 1
                ) conflicts
                """,
            ),
            "dqd_players_without_primary_alias": scalar(
                db,
                """
                select count(*)
                from players p
                where p.code like 'DQD-P%'
                  and not exists (
                    select 1
                    from player_aliases pa
                    where pa.source = 'dongqiudi'
                      and pa.player_id = p.id
                      and pa.source_player_id = substring(p.code from 6)
                  )
                """,
            ),
            "lineups_with_source_player_without_alias": scalar(
                db,
                """
                select count(*)
                from lineup_snapshots ls
                where ls.source_player_id is not null
                  and not exists (
                    select 1
                    from player_aliases pa
                    where pa.source = 'dongqiudi'
                      and pa.source_player_id = ls.source_player_id
                  )
                """,
            ),
            "lineup_player_id_mismatches": scalar(
                db,
                """
                select count(*)
                from lineup_snapshots ls
                join player_aliases pa
                  on pa.source = 'dongqiudi'
                 and pa.source_player_id = ls.source_player_id
                where ls.source_player_id is not null
                  and ls.player_id is distinct from pa.player_id
                """,
            ),
            "player_forms_team_mismatches": scalar(
                db,
                """
                select count(*)
                from player_form_snapshots pf
                join players p on p.id = pf.player_id
                where pf.team_id <> p.team_id
                """,
            ),
            "ambiguous_player_name_aliases": scalar(
                db,
                """
                select count(*)
                from (
                    select source, team_id, lower(regexp_replace(alias, '[^[:alnum:]]+', '', 'g')) as alias_key
                    from player_aliases
                    group by source, team_id, lower(regexp_replace(alias, '[^[:alnum:]]+', '', 'g'))
                    having count(distinct player_id) > 1
                ) conflicts
                """,
            ),
            "model_eligible_injuries_without_player_mapping": scalar(
                db,
                """
                select count(*)
                from injury_reports ir
                join data_source_links dsl
                  on dsl.entity_type = 'injury_report'
                 and dsl.entity_key = ir.id::text
                where ir.is_model_eligible = true
                  and ir.player_id is null
                  and dsl.metadata ? 'player_name'
                """,
            ),
        }

        samples = {
            "generated_duplicate_roster_teams": duplicate_teams[:10],
            "historical_team_names_without_source_alias": sample_rows(
                db,
                """
                select names.source, t.code as team_code, names.alias
                from (
                    select source, home_team_id as team_id, home_team_name as alias
                    from historical_international_matches
                    union all
                    select source, away_team_id as team_id, away_team_name as alias
                    from historical_international_matches
                ) names
                join teams t on t.id = names.team_id
                where not exists (
                    select 1
                    from team_aliases ta
                    where ta.source = names.source
                      and ta.team_id = names.team_id
                      and ta.alias = names.alias
                )
                limit :limit
                """,
            ),
            "lineup_player_id_mismatches": sample_rows(
                db,
                """
                select ls.source_player_id, ls.player_name, ls.player_id::text as lineup_player_id, pa.player_id::text as alias_player_id
                from lineup_snapshots ls
                join player_aliases pa
                  on pa.source = 'dongqiudi'
                 and pa.source_player_id = ls.source_player_id
                where ls.source_player_id is not null
                  and ls.player_id is distinct from pa.player_id
                limit :limit
                """,
            ),
            "ambiguous_player_name_aliases": sample_rows(
                db,
                """
                select pa.source, t.code as team_code, pa.alias,
                       count(distinct pa.player_id) as player_count,
                       string_agg(distinct p.code || ':' || p.name_zh, ' | ' order by p.code || ':' || p.name_zh) as players
                from player_aliases pa
                join players p on p.id = pa.player_id
                join teams t on t.id = pa.team_id
                group by pa.source, t.code, pa.alias, lower(regexp_replace(pa.alias, '[^[:alnum:]]+', '', 'g'))
                having count(distinct pa.player_id) > 1
                order by t.code, pa.alias
                limit :limit
                """,
            ),
        }

    warning_checks = {"ambiguous_player_name_aliases"}
    hard_checks = {key: value for key, value in checks.items() if key not in warning_checks}
    status = "pass" if all(value == 0 for value in hard_checks.values()) else "needs_attention"
    print(
        json.dumps(
            {
                "status": status,
                "checks": checks,
                "warning_checks": sorted(warning_checks),
                "samples": samples,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if status != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
