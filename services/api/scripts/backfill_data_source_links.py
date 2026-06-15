from __future__ import annotations

from pathlib import Path
import sys

from sqlalchemy import text

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal


BACKFILL_SQL = """
delete from data_source_links
where entity_type = 'news_item'
  and source in ('bbc', 'espn', 'foxsports', 'guardian')
  and source_type = 'homepage';

insert into data_source_links (
    entity_type,
    entity_key,
    source,
    source_type,
    source_url,
    raw_snapshot_id,
    source_record_id,
    confidence,
    metadata
)
select
    'news_item',
    n.source_url,
    n.source,
    n.source_type,
    n.source_url,
    (
        select r.id
        from raw_snapshots r
        where r.source = n.source and r.source_type = n.source_type
        order by r.fetched_at desc
        limit 1
    ),
    left(n.source_url, 128),
    1.0,
    jsonb_build_object('title', n.title, 'backfilled', true)
from (
    select
        n.*,
        case n.source
            when 'bbc' then 'football_rss'
            when 'guardian' then 'football_rss'
            when 'espn' then 'soccer_rss'
            when 'foxsports' then 'world_cup_rss'
            else 'homepage'
        end as source_type
    from news_items n
) n
on conflict (entity_type, entity_key, source, source_type) do update set
    source_url = excluded.source_url,
    raw_snapshot_id = excluded.raw_snapshot_id,
    source_record_id = excluded.source_record_id,
    confidence = excluded.confidence,
    fetched_at = now(),
    metadata = excluded.metadata;

insert into data_source_links (
    entity_type,
    entity_key,
    source,
    source_type,
    source_url,
    raw_snapshot_id,
    source_record_id,
    confidence,
    metadata
)
select
    'match',
    m.public_id,
    case when m.public_id like 'dongqiudi-%' then 'dongqiudi' else 'thestatsapi' end,
    case when m.public_id like 'dongqiudi-%' then 'homepage' else 'fixtures' end,
    r.source_url,
    r.id,
    m.public_id,
    m.source_confidence,
    jsonb_build_object('backfilled', true)
from matches m
join lateral (
    select id, source_url
    from raw_snapshots r
    where r.source = case when m.public_id like 'dongqiudi-%' then 'dongqiudi' else 'thestatsapi' end
      and r.source_type = case when m.public_id like 'dongqiudi-%' then 'homepage' else 'fixtures' end
    order by fetched_at desc
    limit 1
) r on true
where m.public_id like 'dongqiudi-%' or m.public_id like 'thestatsapi-%'
on conflict (entity_type, entity_key, source, source_type) do update set
    source_url = excluded.source_url,
    raw_snapshot_id = excluded.raw_snapshot_id,
    source_record_id = excluded.source_record_id,
    confidence = excluded.confidence,
    fetched_at = now(),
    metadata = excluded.metadata;

insert into data_source_links (
    entity_type,
    entity_key,
    source,
    source_type,
    source_url,
    raw_snapshot_id,
    source_record_id,
    confidence,
    metadata
)
select
    'venue',
    v.code,
    'thestatsapi',
    'fixtures',
    r.source_url,
    r.id,
    v.code,
    1.0,
    jsonb_build_object('name', v.name, 'city', v.city, 'country', v.country, 'backfilled', true)
from venues v
join lateral (
    select id, source_url
    from raw_snapshots r
    where r.source = 'thestatsapi' and r.source_type = 'fixtures'
    order by fetched_at desc
    limit 1
) r on true
on conflict (entity_type, entity_key, source, source_type) do update set
    source_url = excluded.source_url,
    raw_snapshot_id = excluded.raw_snapshot_id,
    source_record_id = excluded.source_record_id,
    confidence = excluded.confidence,
    fetched_at = now(),
    metadata = excluded.metadata;

insert into data_source_links (
    entity_type,
    entity_key,
    source,
    source_type,
    source_url,
    raw_snapshot_id,
    source_record_id,
    confidence,
    metadata
)
select
    'team',
    t.code,
    src.source,
    src.source_type,
    r.source_url,
    r.id,
    t.code,
    src.confidence,
    jsonb_build_object('name_zh', t.name_zh, 'name_en', t.name_en, 'backfilled', true)
from teams t
join lateral (
    select
        case
            when exists (
                select 1 from matches m
                where (m.home_team_id = t.id or m.away_team_id = t.id)
                  and m.public_id like 'dongqiudi-%'
            )
            then 'dongqiudi'
            else 'thestatsapi'
        end as source,
        case
            when exists (
                select 1 from matches m
                where (m.home_team_id = t.id or m.away_team_id = t.id)
                  and m.public_id like 'dongqiudi-%'
            )
            then 'world_cup_schedule'
            else 'fixtures'
        end as source_type,
        0.95::numeric as confidence
) src on true
join lateral (
    select id, source_url
    from raw_snapshots r
    where r.source = src.source and r.source_type = src.source_type
    order by fetched_at desc
    limit 1
) r on true
where not exists (
    select 1 from data_source_links l
    where l.entity_type = 'team' and l.entity_key = t.code
)
on conflict (entity_type, entity_key, source, source_type) do update set
    source_url = excluded.source_url,
    raw_snapshot_id = excluded.raw_snapshot_id,
    source_record_id = excluded.source_record_id,
    confidence = excluded.confidence,
    fetched_at = now(),
    metadata = excluded.metadata;

insert into data_source_links (
    entity_type,
    entity_key,
    source,
    source_type,
    source_url,
    raw_snapshot_id,
    source_record_id,
    confidence,
    metadata
)
select
    'group_standing',
    s.code || ':' || t.code,
    'dongqiudi',
    'world_cup_standings',
    coalesce(snapshot.source_url, latest.source_url),
    coalesce(snapshot.id, latest.id),
    s.code || ':' || t.code,
    1.0,
    jsonb_build_object('rank', gs.rank, 'points', gs.points, 'backfilled', true)
from group_standings gs
join competition_stages s on s.id = gs.stage_id
join teams t on t.id = gs.team_id
left join raw_snapshots snapshot on snapshot.id = gs.snapshot_id
join lateral (
    select id, source_url
    from raw_snapshots r
    where r.source = 'dongqiudi' and r.source_type = 'world_cup_standings'
    order by fetched_at desc
    limit 1
) latest on true
on conflict (entity_type, entity_key, source, source_type) do update set
    source_url = excluded.source_url,
    raw_snapshot_id = excluded.raw_snapshot_id,
    source_record_id = excluded.source_record_id,
    confidence = excluded.confidence,
    fetched_at = now(),
    metadata = excluded.metadata;

insert into data_source_links (
    entity_type,
    entity_key,
    source,
    source_type,
    source_url,
    raw_snapshot_id,
    source_record_id,
    confidence,
    metadata
)
select
    'team_form',
    t.code || ':' || to_char(tf.as_of_at at time zone 'Asia/Shanghai', 'YYYY-MM-DD"T"HH24:MI:SS') || '+08:00',
    'dongqiudi',
    'world_cup_schedule',
    latest.source_url,
    latest.id,
    t.code,
    0.95,
    jsonb_build_object(
        'recent_matches', tf.recent_matches,
        'data_quality', tf.data_quality,
        'backfilled', true
    )
from team_form_snapshots tf
join teams t on t.id = tf.team_id
join lateral (
    select id, source_url
    from raw_snapshots r
    where r.source = 'dongqiudi' and r.source_type = 'world_cup_schedule'
    order by fetched_at desc
    limit 1
) latest on true
on conflict (entity_type, entity_key, source, source_type) do update set
    source_url = excluded.source_url,
    raw_snapshot_id = excluded.raw_snapshot_id,
    source_record_id = excluded.source_record_id,
    confidence = excluded.confidence,
    fetched_at = now(),
    metadata = excluded.metadata;
"""

AUDIT_SQL = """
select 'matches_without_source' as check_name, count(*) as missing_count
from matches m
where not exists (
    select 1 from data_source_links l where l.entity_type = 'match' and l.entity_key = m.public_id
)
union all
select 'venues_without_source', count(*)
from venues v
where not exists (
    select 1 from data_source_links l where l.entity_type = 'venue' and l.entity_key = v.code
)
union all
select 'teams_without_source', count(*)
from teams t
where not exists (
    select 1 from data_source_links l where l.entity_type = 'team' and l.entity_key = t.code
)
union all
select 'players_without_source', count(*)
from players p
where not exists (
    select 1 from data_source_links l where l.entity_type = 'player' and l.entity_key = p.code
)
union all
select 'news_without_source', count(*)
from news_items n
where not exists (
    select 1 from data_source_links l where l.entity_type = 'news_item' and l.entity_key = n.source_url
)
union all
select 'group_standings_without_source', count(*)
from group_standings gs
join competition_stages s on s.id = gs.stage_id
join teams t on t.id = gs.team_id
where not exists (
    select 1 from data_source_links l
    where l.entity_type = 'group_standing' and l.entity_key = s.code || ':' || t.code
)
union all
select 'team_forms_without_source', count(*)
from team_form_snapshots tf
join teams t on t.id = tf.team_id
where not exists (
    select 1 from data_source_links l
    where l.entity_type = 'team_form'
      and l.entity_key = t.code || ':' || to_char(tf.as_of_at at time zone 'Asia/Shanghai', 'YYYY-MM-DD"T"HH24:MI:SS') || '+08:00'
)
union all
select 'player_forms_without_source', count(*)
from player_form_snapshots pf
join players p on p.id = pf.player_id
where not exists (
    select 1 from data_source_links l
    where l.entity_type = 'player_form'
      and l.entity_key = p.code || ':' || to_char(pf.as_of_at at time zone 'Asia/Shanghai', 'YYYY-MM-DD"T"HH24:MI:SS') || '+08:00'
)
union all
select 'team_market_values_without_source', count(*)
from teams t
where t.market_value_eur is not null
  and not exists (
    select 1 from data_source_links l
    where l.entity_type = 'team_market_value' and l.entity_key = t.code
  )
union all
select 'weather_snapshots_without_source', count(*)
from weather_snapshots ws
join venues v on v.id = ws.venue_id
where not exists (
    select 1 from data_source_links l
    where l.entity_type = 'weather_snapshot'
      and l.entity_key = v.code || ':' || to_char(ws.observed_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS') || '+00:00'
)
union all
select 'coaches_without_source', count(*)
from coaches c
join teams t on t.id = c.team_id
where not exists (
    select 1 from data_source_links l
    where l.entity_type = 'coach' and l.entity_key = t.code || ':' || c.name_zh
)
union all
select 'injury_reports_without_source', count(*)
from injury_reports ir
where not exists (
    select 1 from data_source_links l
    where l.entity_type = 'injury_report' and l.entity_key = ir.id::text
)
order by check_name;
"""


def main() -> None:
    with SessionLocal() as db:
        db.execute(text(BACKFILL_SQL))
        rows = db.execute(text(AUDIT_SQL)).mappings().all()
        db.commit()

    for row in rows:
        print(f"{row['check_name']}: {row['missing_count']}")


if __name__ == "__main__":
    main()
