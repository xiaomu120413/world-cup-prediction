from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal


COUNT_SQL = {
    "matches": "select count(*) from matches where public_id like 'thestatsapi-%'",
    "match_predictions": """
        select count(*)
        from match_predictions mp
        join matches m on m.id = mp.match_id
        where m.public_id like 'thestatsapi-%'
    """,
    "lineup_snapshots": """
        select count(*)
        from lineup_snapshots ls
        join matches m on m.id = ls.match_id
        where m.public_id like 'thestatsapi-%'
    """,
    "ai_insights_match_refs": """
        select count(*)
        from ai_insights ai
        join matches m on m.id = ai.match_id
        where m.public_id like 'thestatsapi-%'
    """,
    "raw_snapshots": "select count(*) from raw_snapshots where source = 'thestatsapi'",
    "collector_runs": "select count(*) from collector_runs where source = 'thestatsapi'",
    "data_source_links": """
        select count(*)
        from data_source_links
        where source = 'thestatsapi'
           or source_url ilike '%thestatsapi%'
           or entity_key like 'thestatsapi-%'
    """,
    "exclusive_venues": """
        select count(*)
        from venues v
        where exists (
            select 1 from data_source_links l
            where l.entity_type = 'venue'
              and l.entity_key = v.code
              and l.source = 'thestatsapi'
        )
          and not exists (
            select 1 from data_source_links l
            where l.entity_type = 'venue'
              and l.entity_key = v.code
              and l.source <> 'thestatsapi'
        )
    """,
}


def counts(db) -> dict[str, int]:
    return {key: int(db.execute(text(sql)).scalar_one()) for key, sql in COUNT_SQL.items()}


def scalar(db, sql: str) -> int:
    result = db.execute(text(sql))
    return int(result.rowcount or 0)


def purge(db) -> dict[str, int]:
    result: dict[str, int] = {}
    result["ai_insights_match_refs_cleared"] = scalar(
        db,
        """
        update ai_insights
        set match_id = null
        where match_id in (
            select id from matches where public_id like 'thestatsapi-%'
        )
        """,
    )
    result["matches_deleted"] = scalar(
        db,
        "delete from matches where public_id like 'thestatsapi-%'",
    )
    result["exclusive_venues_deleted"] = scalar(
        db,
        """
        delete from venues v
        where exists (
            select 1 from data_source_links l
            where l.entity_type = 'venue'
              and l.entity_key = v.code
              and l.source = 'thestatsapi'
        )
          and not exists (
            select 1 from data_source_links l
            where l.entity_type = 'venue'
              and l.entity_key = v.code
              and l.source <> 'thestatsapi'
        )
          and not exists (select 1 from matches m where m.venue_id = v.id)
          and not exists (select 1 from weather_snapshots ws where ws.venue_id = v.id)
        """,
    )
    result["data_source_links_deleted"] = scalar(
        db,
        """
        delete from data_source_links
        where source = 'thestatsapi'
           or source_url ilike '%thestatsapi%'
           or entity_key like 'thestatsapi-%'
        """,
    )
    result["collector_runs_deleted"] = scalar(
        db,
        "delete from collector_runs where source = 'thestatsapi'",
    )
    result["prediction_snapshots_detached"] = scalar(
        db,
        """
        update prediction_snapshots
        set data_snapshot_id = null
        where data_snapshot_id in (
            select id from raw_snapshots where source = 'thestatsapi'
        )
        """,
    )
    result["raw_snapshots_deleted"] = scalar(
        db,
        "delete from raw_snapshots where source = 'thestatsapi'",
    )
    return result


def run(apply: bool = False) -> dict:
    with SessionLocal() as db:
        before = counts(db)
        if not apply:
            return {"mode": "dry_run", "before": before}
        result = purge(db)
        db.commit()
        after = counts(db)
    return {"mode": "apply", "before": before, "result": result, "after": after}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Delete legacy TheStatsAPI rows.")
    args = parser.parse_args()
    print(json.dumps(run(apply=args.apply), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
