from __future__ import annotations

COLLECTOR_CATALOG = [
    {
        "job_id": "dongqiudi_homepage",
        "source": "dongqiudi",
        "source_type": "homepage",
        "domains": ["matches", "news"],
        "target_tables": ["raw_snapshots", "collector_runs", "data_source_links", "news_items", "teams", "team_aliases", "matches"],
        "status": "implemented_partial_real",
        "frequency": "manual_now_daily_later",
        "notes": "Low-frequency homepage extraction. Useful for Chinese match/news signals, not enough for full production data.",
    },
    {
        "job_id": "official_schedule_venues",
        "source": "thestatsapi",
        "source_type": "fixtures",
        "domains": ["matches", "venues"],
        "target_tables": ["raw_snapshots", "collector_runs", "data_source_links", "venues", "matches"],
        "status": "implemented_real_schedule",
        "frequency": "daily_and_matchday",
        "notes": "Static 2026 World Cup fixtures and venues. Covers schedule only, not live scores or player stats.",
    },
    {
        "job_id": "group_standings",
        "source": "dongqiudi",
        "source_type": "world_cup_standings",
        "domains": ["standings"],
        "target_tables": ["raw_snapshots", "collector_runs", "data_source_links", "group_standings"],
        "status": "implemented_partial_real",
        "frequency": "daily_and_post_match",
        "notes": "World Cup 2026 group standings from Dongqiudi sport-data API.",
    },
    {
        "job_id": "player_recent_form",
        "source": "dongqiudi",
        "source_type": "world_cup_player_rankings",
        "domains": ["players", "player_form"],
        "target_tables": ["raw_snapshots", "collector_runs", "data_source_links", "players", "player_form_snapshots"],
        "status": "implemented_partial_real",
        "frequency": "daily",
        "notes": "World Cup 2026 player rankings from Dongqiudi sport-data API: goals, assists, shots, shots on target and key passes.",
    },
    {
        "job_id": "fifa_mens_world_ranking",
        "source": "fifa",
        "source_type": "mens_world_ranking",
        "domains": ["teams", "rankings"],
        "target_tables": ["raw_snapshots", "data_source_links", "teams.fifa_rank"],
        "status": "implemented_official",
        "frequency": "after_fifa_ranking_update",
        "notes": "FIFA official rankings from api.fifa.com. Used to populate FIFA rank for roster teams.",
    },
    {
        "job_id": "team_form",
        "source": "dongqiudi",
        "source_type": "team_form",
        "domains": ["team_form"],
        "target_tables": ["raw_snapshots", "collector_runs", "data_source_links", "team_form_snapshots"],
        "status": "implemented_partial_real",
        "frequency": "daily",
        "notes": "Current tournament team form derived from Dongqiudi World Cup standings. Lineup stability and injury impact still need dedicated sources.",
    },
    {
        "job_id": "world_cup_schedule_lineups",
        "source": "dongqiudi",
        "source_type": "world_cup_schedule_and_match_lineup",
        "domains": ["team_match_results", "lineups", "lineup_stability"],
        "target_tables": ["raw_snapshots", "data_source_links", "matches", "team_match_results", "lineup_snapshots", "team_form_snapshots"],
        "status": "implemented_partial_real",
        "frequency": "manual_now_post_match_later",
        "notes": "Full World Cup schedule plus match lineups for played matches. Lineup stability grows as played-match sample increases.",
    },
    {
        "job_id": "team_market_value",
        "source": "authorized_market_value_source",
        "source_type": "market_value",
        "domains": ["teams", "players"],
        "target_tables": ["raw_snapshots", "collector_runs", "data_source_links", "teams", "players"],
        "status": "planned_required",
        "frequency": "weekly",
        "notes": "Team and player market value. Needs licensing check before production use.",
    },
    {
        "job_id": "official_squad_list",
        "source": "fifa",
        "source_type": "official_squad_list",
        "domains": ["players", "coaches"],
        "target_tables": ["raw_snapshots", "collector_runs", "data_source_links", "players", "coaches"],
        "status": "implemented_official",
        "frequency": "manual_low_frequency",
        "notes": "FIFA official World Cup 2026 Squad List PDF. Normalizes 26-player squads and head coaches.",
    },
    {
        "job_id": "coach_records",
        "source": "authorized_or_manual_verified",
        "source_type": "coach_record",
        "domains": ["coaches"],
        "target_tables": ["raw_snapshots", "collector_runs", "data_source_links", "coaches"],
        "status": "schema_ready_partial_real",
        "frequency": "weekly",
        "notes": "Head coach identity is implemented from FIFA official squad list; tenure, win rate and tournament record still need a dedicated source.",
    },
    {
        "job_id": "venue_weather",
        "source": "venue_source_and_weather_api",
        "source_type": "weather",
        "domains": ["venues", "weather"],
        "target_tables": ["raw_snapshots", "collector_runs", "data_source_links", "venues", "weather_snapshots"],
        "status": "implemented_partial_real",
        "frequency": "matchday_minus_24h_and_minus_3h",
        "notes": "Venue enrichment and Open-Meteo current observations are implemented; matchday weather should be refreshed 24h/3h before kickoff.",
    },
    {
        "job_id": "ai_news_insights",
        "source": "news_items",
        "source_type": "ai_insight",
        "domains": ["ai_insights"],
        "target_tables": ["ai_insights", "ai_explanations"],
        "status": "planned_required",
        "frequency": "after_news_collection",
        "notes": "LLM extraction for injuries, suspensions, lineup, coach comments and tactical signals.",
    },
    {
        "job_id": "public_news_rss",
        "source": "guardian_bbc_espn",
        "source_type": "football_rss",
        "domains": ["news"],
        "target_tables": ["raw_snapshots", "data_source_links", "news_items"],
        "status": "implemented_partial_real",
        "frequency": "manual_now_hourly_later",
        "notes": "Public English football RSS feeds used to avoid Dongqiudi-only news coverage.",
    },
]


def collection_catalog_summary(table_counts: dict[str, int] | None = None) -> dict:
    counts = table_counts or {}
    dongqiudi_matches = counts.get("dongqiudi_matches", 0)
    thestatsapi_matches = counts.get("thestatsapi_matches", 0)
    players = counts.get("players", 0)
    fifa_official_players = counts.get("fifa_official_players", 0)
    player_forms = counts.get("player_form_snapshots", 0)
    player_market_values = counts.get("player_market_values", 0)
    team_market_values = counts.get("team_market_values", 0)
    standings = counts.get("group_standings", 0)
    team_forms = counts.get("team_form_snapshots", 0)
    weather = counts.get("weather_snapshots", 0)
    venue_enriched = counts.get("venue_enriched", 0)
    coaches = counts.get("coaches", 0)
    injuries = counts.get("injury_reports", 0)
    lineups = counts.get("lineup_snapshots", 0)
    team_match_results = counts.get("team_match_results", 0)
    news = counts.get("news_items", 0)
    dongqiudi_standings = counts.get("dongqiudi_standings_snapshots", 0)
    dongqiudi_player_rankings = counts.get("dongqiudi_player_ranking_snapshots", 0)
    fifa_ranking_source_links = counts.get("fifa_ranking_source_links", 0)

    return {
        "domains": [
            {
                "domain": "matches",
                "status": "partial_real" if dongqiudi_matches > 0 or thestatsapi_matches > 0 else "missing_real_source",
                "current_source": ", ".join(
                    value
                    for value in [
                        "thestatsapi/fixtures" if thestatsapi_matches > 0 else "",
                        "dongqiudi/homepage" if dongqiudi_matches > 0 else "",
                    ]
                    if value
                )
                or None,
                "target_tables": ["matches", "teams", "team_aliases"],
            },
            {
                "domain": "news",
                "status": "partial_real" if news > 0 else "missing_real_source",
                "current_source": "dongqiudi/homepage_links + guardian/bbc/espn rss" if news > 0 else None,
                "target_tables": ["news_items", "ai_insights"],
            },
            {
                "domain": "standings",
                "status": "partial_real" if dongqiudi_standings > 0 else ("sample_or_partial" if standings > 0 else "missing_real_source"),
                "current_source": "dongqiudi/world_cup_standings"
                if dongqiudi_standings > 0
                else ("local_sample_or_seed" if standings > 0 else None),
                "target_tables": ["group_standings"],
            },
            {
                "domain": "player_form",
                "status": "partial_real"
                if dongqiudi_player_rankings > 0 or fifa_official_players > 0
                else ("sample_or_partial" if players > 0 and player_forms > 0 else "missing_real_source"),
                "current_source": ", ".join(
                    value
                    for value in [
                        "fifa/official_squad_list" if fifa_official_players > 0 else "",
                        "dongqiudi/world_cup_player_rankings" if dongqiudi_player_rankings > 0 else "",
                    ]
                    if value
                )
                if dongqiudi_player_rankings > 0 or fifa_official_players > 0
                else ("local_sample_or_seed" if players > 0 and player_forms > 0 else None),
                "target_tables": ["players", "player_form_snapshots"],
            },
            {
                "domain": "fifa_rankings",
                "status": "official_real" if fifa_ranking_source_links > 0 else "missing_real_source",
                "current_source": "fifa/mens_world_ranking" if fifa_ranking_source_links > 0 else None,
                "target_tables": ["teams.fifa_rank"],
            },
            {
                "domain": "market_value",
                "status": "partial_real" if player_market_values > 0 or team_market_values > 0 else "missing_real_source",
                "current_source": "dongqiudi/market_value_ranking" if player_market_values > 0 or team_market_values > 0 else None,
                "target_tables": ["players.market_value_eur", "teams.market_value_eur"],
            },
            {
                "domain": "team_form",
                "status": "partial_real" if team_forms > 0 and dongqiudi_standings > 0 else "missing_real_source",
                "current_source": "dongqiudi/world_cup_standings" if team_forms > 0 and dongqiudi_standings > 0 else None,
                "target_tables": ["team_form_snapshots"],
            },
            {
                "domain": "team_match_results",
                "status": "partial_real" if team_match_results > 0 else "missing_real_source",
                "current_source": "dongqiudi/world_cup_schedule" if team_match_results > 0 else None,
                "target_tables": ["team_match_results"],
            },
            {
                "domain": "lineups",
                "status": "partial_real" if lineups > 0 else "schema_ready_missing_source",
                "current_source": "dongqiudi/match_lineup" if lineups > 0 else None,
                "target_tables": ["lineup_snapshots", "team_form_snapshots.lineup_stability_score"],
            },
            {
                "domain": "venues_weather",
                "status": "partial_real" if venue_enriched > 0 and weather > 0 else ("partial_real" if counts.get("venues", 0) > 0 else "missing_real_source"),
                "current_source": ", ".join(
                    value
                    for value in [
                        "thestatsapi/fixtures" if counts.get("venues", 0) > 0 else "",
                        "manual_verified/venue_enrichment" if venue_enriched > 0 else "",
                        "open_meteo/venue_current_weather" if weather > 0 else "",
                    ]
                    if value
                )
                or None,
                "target_tables": ["venues", "weather_snapshots"],
            },
            {
                "domain": "coaches",
                "status": "partial_real" if coaches > 0 else "schema_ready_missing_source",
                "current_source": "manual_verified_or_authorized" if coaches > 0 else None,
                "target_tables": ["coaches"],
            },
            {
                "domain": "injuries",
                "status": "partial_real" if injuries > 0 else "schema_ready_missing_source",
                "current_source": "verified_news_or_authorized" if injuries > 0 else None,
                "target_tables": ["injury_reports", "ai_insights"],
            },
        ],
        "jobs": COLLECTOR_CATALOG,
    }
