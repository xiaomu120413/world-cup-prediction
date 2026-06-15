insert into competitions (code, name, host_countries, start_date, end_date)
values ('world_cup_2026', 'World Cup 2026', '["United States","Canada","Mexico"]', '2026-06-11', '2026-07-19')
on conflict (code) do nothing;

insert into competition_stages (competition_id, code, name, stage_type, sort_order)
select id, 'group-a', 'Group A', 'group', 1
from competitions
where code = 'world_cup_2026'
on conflict (competition_id, code) do nothing;

insert into teams (code, name_zh, name_en, confederation, fifa_rank, elo_rating, quality_status)
values
    ('USA', 'United States', 'United States', 'CONCACAF', 11, 1838, 'estimated'),
    ('PAR', 'Paraguay', 'Paraguay', 'CONMEBOL', 48, 1741, 'estimated'),
    ('FRA', 'France', 'France', 'UEFA', 2, 2104, 'estimated'),
    ('BRA', 'Brazil', 'Brazil', 'CONMEBOL', 5, 2078, 'estimated'),
    ('ENG', 'England', 'England', 'UEFA', 4, 2059, 'estimated')
on conflict (code) do update set
    name_zh = excluded.name_zh,
    name_en = excluded.name_en,
    confederation = excluded.confederation,
    fifa_rank = excluded.fifa_rank,
    elo_rating = excluded.elo_rating,
    quality_status = excluded.quality_status;

insert into venues (code, name, city, country, timezone)
values ('los-angeles', 'Los Angeles Stadium', 'Los Angeles', 'United States', 'America/Los_Angeles')
on conflict (code) do update set
    name = excluded.name,
    city = excluded.city,
    country = excluded.country,
    timezone = excluded.timezone;

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
    '[{"label":"lineup_stability","value":6,"note":"Recent starting XI repeat rate is higher"},{"label":"recent_attack","value":4,"note":"Slight creative edge in attack"}]'::jsonb
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

insert into ranking_predictions (prediction_snapshot_id, ranking_type, team_id, probability, delta, rank, reason)
select ps.id, x.ranking_type, t.id, x.probability, x.delta, x.rank, x.reason
from prediction_snapshots ps
join (
    values
        ('champion', 'FRA', 0.158, 0.012, 1, 'squad_depth'),
        ('champion', 'BRA', 0.136, 0.008, 2, 'attack_form'),
        ('champion', 'ENG', 0.129, -0.003, 3, 'path_difficulty'),
        ('semifinal', 'FRA', 0.426, 0.023, 1, 'squad_depth'),
        ('darkhorse', 'PAR', 0.184, 0.036, 1, 'defensive_resilience')
) as x(ranking_type, team_code, probability, delta, rank, reason) on true
join teams t on t.code = x.team_code
where ps.scope = 'matchday'
and ps.seed = 20260613
and not exists (
    select 1
    from ranking_predictions rp
    where rp.prediction_snapshot_id = ps.id
    and rp.ranking_type = x.ranking_type
    and rp.team_id = t.id
);

insert into group_standings (
    stage_id,
    team_id,
    played,
    wins,
    draws,
    losses,
    goals_for,
    goals_against,
    goal_diff,
    points,
    rank
)
select s.id, t.id, x.played, x.wins, x.draws, x.losses, x.goals_for, x.goals_against, x.goal_diff, x.points, x.rank
from competition_stages s
join (
    values
        ('FRA', 1, 1, 0, 0, 2, 0, 2, 3, 1),
        ('BRA', 1, 1, 0, 0, 2, 1, 1, 3, 2),
        ('USA', 1, 0, 0, 1, 1, 2, -1, 0, 3),
        ('PAR', 1, 0, 0, 1, 0, 2, -2, 0, 4)
) as x(team_code, played, wins, draws, losses, goals_for, goals_against, goal_diff, points, rank) on true
join teams t on t.code = x.team_code
where s.code = 'group-a'
and not exists (
    select 1
    from group_standings gs
    where gs.stage_id = s.id
    and gs.team_id = t.id
);

insert into group_simulations (
    stage_id,
    prediction_snapshot_id,
    team_id,
    rank_1_prob,
    rank_2_prob,
    qualify_prob,
    expected_points
)
select s.id, ps.id, t.id, x.rank_1_prob, x.rank_2_prob, x.qualify_prob, x.expected_points
from competition_stages s
join prediction_snapshots ps on ps.scope = 'matchday' and ps.seed = 20260613
join (
    values
        ('FRA', 0.612, 0.282, 0.894, 6.8),
        ('BRA', 0.584, 0.271, 0.855, 6.5),
        ('USA', 0.118, 0.336, 0.454, 4.2),
        ('PAR', 0.086, 0.211, 0.297, 3.3)
) as x(team_code, rank_1_prob, rank_2_prob, qualify_prob, expected_points) on true
join teams t on t.code = x.team_code
where s.code = 'group-a'
on conflict (stage_id, prediction_snapshot_id, team_id) do nothing;
