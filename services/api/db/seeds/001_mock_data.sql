insert into competitions (code, name, host_countries, start_date, end_date)
values ('world_cup_2026', '世界杯 2026', '["United States","Canada","Mexico"]', '2026-06-11', '2026-07-19')
on conflict (code) do nothing;

insert into competition_stages (competition_id, code, name, stage_type, sort_order)
select id, 'group-a', 'A组', 'group', 1
from competitions
where code = 'world_cup_2026'
on conflict (competition_id, code) do nothing;

insert into teams (code, name_zh, name_en, confederation, fifa_rank, elo_rating, quality_status)
values
    ('USA', '美国', 'United States', 'CONCACAF', 11, 1838, 'estimated'),
    ('PAR', '巴拉圭', 'Paraguay', 'CONMEBOL', 48, 1741, 'estimated'),
    ('FRA', '法国', 'France', 'UEFA', 2, 2104, 'estimated'),
    ('BRA', '巴西', 'Brazil', 'CONMEBOL', 5, 2078, 'estimated'),
    ('ENG', '英格兰', 'England', 'UEFA', 4, 2059, 'estimated')
on conflict (code) do nothing;

insert into venues (code, name, city, country, timezone)
values ('los-angeles', '洛杉矶', 'Los Angeles', 'United States', 'America/Los_Angeles')
on conflict (code) do nothing;

insert into model_versions (name, version, model_type, feature_schema, is_active)
values (
    'baseline',
    'baseline_2026_06_13',
    'elo_poisson',
    '{"features":["elo_diff","fifa_rank_diff","recent_form","injury_impact","venue_advantage"]}',
    true
)
on conflict (name, version) do nothing;

insert into prediction_snapshots (model_version_id, scope, status, seed, notes)
select id, 'matchday', 'success', 20260613, 'Initial mock prediction snapshot'
from model_versions
where version = 'baseline_2026_06_13'
and not exists (
    select 1 from prediction_snapshots ps where ps.scope = 'matchday' and ps.seed = 20260613
);

insert into matches (
    public_id,
    competition_id,
    stage_id,
    home_team_id,
    away_team_id,
    venue_id,
    kickoff_at,
    status,
    neutral_site,
    source_confidence
)
select
    'usa-paraguay-2026-06-13',
    c.id,
    s.id,
    home_team.id,
    away_team.id,
    v.id,
    '2026-06-13T01:00:00+08:00',
    'scheduled',
    true,
    1.0
from competitions c
join competition_stages s on s.competition_id = c.id and s.code = 'group-a'
join teams home_team on home_team.code = 'USA'
join teams away_team on away_team.code = 'PAR'
left join venues v on v.code = 'los-angeles'
where c.code = 'world_cup_2026'
on conflict (public_id) do nothing;

insert into match_predictions (
    match_id,
    prediction_snapshot_id,
    model_version_id,
    home_win_prob,
    draw_prob,
    away_win_prob,
    home_expected_goals,
    away_expected_goals,
    confidence,
    key_factors
)
select
    m.id,
    ps.id,
    mv.id,
    0.44,
    0.27,
    0.29,
    1.42,
    1.18,
    'medium',
    '[{"label":"阵容稳定","value":6,"note":"近 5 场首发重复率更高"},{"label":"近期进攻","value":4,"note":"前场创造力略优"}]'::jsonb
from matches m
join prediction_snapshots ps on ps.scope = 'matchday' and ps.seed = 20260613
join model_versions mv on mv.version = 'baseline_2026_06_13'
where m.public_id = 'usa-paraguay-2026-06-13'
and not exists (select 1 from match_predictions mp where mp.match_id = m.id);

insert into scoreline_predictions (match_prediction_id, home_goals, away_goals, probability, rank)
select mp.id, x.home_goals, x.away_goals, x.probability, x.rank
from match_predictions mp
join matches m on m.id = mp.match_id
cross join (
    values
        (1, 1, 0.12, 1),
        (2, 1, 0.10, 2),
        (1, 0, 0.09, 3),
        (0, 0, 0.08, 4)
) as x(home_goals, away_goals, probability, rank)
where m.public_id = 'usa-paraguay-2026-06-13'
on conflict (match_prediction_id, home_goals, away_goals) do nothing;

