from __future__ import annotations

COLLECTOR_CATALOG = [
    {
        "job_id": "dongqiudi_homepage",
        "source": "dongqiudi",
        "source_type": "homepage",
        "domains": ["matches", "news"],
        "target_tables": ["raw_snapshots", "collector_runs", "data_source_links", "news_items", "teams", "team_aliases", "matches"],
        "status": "implemented_real_schedule_feed",
        "frequency": "manual_now_daily_later",
        "notes": "Low-frequency homepage extraction. Useful for Chinese match/news signals, not enough for full production data.",
    },
    {
        "job_id": "group_standings",
        "source": "dongqiudi",
        "source_type": "world_cup_standings",
        "domains": ["standings"],
        "target_tables": ["raw_snapshots", "collector_runs", "data_source_links", "group_standings"],
        "status": "implemented_complete_real",
        "frequency": "daily_and_post_match",
        "notes": "World Cup 2026 group standings from Dongqiudi sport-data API.",
    },
    {
        "job_id": "player_recent_form",
        "source": "dongqiudi",
        "source_type": "world_cup_player_rankings",
        "domains": ["players", "player_form"],
        "target_tables": ["raw_snapshots", "collector_runs", "data_source_links", "players", "player_form_snapshots"],
        "status": "implemented_real_coverage",
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
        "status": "implemented_complete_real",
        "frequency": "daily",
        "notes": "Current tournament team form derived from Dongqiudi World Cup standings. Lineup stability and injury impact still need dedicated sources.",
    },
    {
        "job_id": "world_cup_schedule_lineups",
        "source": "dongqiudi",
        "source_type": "world_cup_schedule_and_match_lineup",
        "domains": ["team_match_results", "lineups", "lineup_stability"],
        "target_tables": ["raw_snapshots", "data_source_links", "matches", "team_match_results", "lineup_snapshots", "team_form_snapshots"],
        "status": "implemented_live_partial_real",
        "frequency": "manual_now_post_match_later",
        "notes": "Full World Cup schedule plus match lineups for played matches. Lineup stability grows as played-match sample increases.",
    },
    {
        "job_id": "historical_international_results",
        "source": "martj42_international_results",
        "source_type": "historical_results",
        "domains": ["historical_international_matches", "historical_team_match_results", "team_form"],
        "target_tables": [
            "raw_snapshots",
            "collector_runs",
            "data_source_links",
            "teams",
            "team_aliases",
            "historical_international_matches",
            "team_match_results",
        ],
        "status": "implemented_public_dataset",
        "frequency": "manual_weekly_or_before_model_recompute",
        "notes": "Historical men's full international results. Writes one actual match row per source match, plus team-perspective rows for existing model compatibility. Defaults to GitHub raw CSV from martj42/international_results so the pipeline does not depend on Kaggle authentication.",
    },
    {
        "job_id": "world_cup_team_details",
        "source": "dongqiudi",
        "source_type": "world_cup_team_details",
        "domains": ["teams", "players", "player_form", "market_value", "coaches", "team_stats"],
        "target_tables": [
            "raw_snapshots",
            "data_source_links",
            "teams",
            "team_aliases",
            "players",
            "player_form_snapshots",
            "coaches",
            "team_stat_snapshots",
        ],
        "status": "implemented_real_roster_coverage",
        "frequency": "manual_low_frequency",
        "notes": "Dongqiudi national-team pages, member_v2 APIs and World Cup team ranking data page. Covers 48 team IDs, squad players, player market values, team market values, current staff, coach history and sourced team-stat ranking metrics.",
    },
    {
        "job_id": "official_squad_list",
        "source": "fifa",
        "source_type": "official_squad_list",
        "domains": ["reference_only"],
        "target_tables": ["raw_snapshots"],
        "status": "disabled_as_player_source",
        "frequency": "manual_low_frequency",
        "notes": "FIFA squad PDF is no longer written to players. Dongqiudi member_v2 is the single canonical player roster source.",
    },
    {
        "job_id": "coach_records",
        "source": "dongqiudi",
        "source_type": "coach_record",
        "domains": ["coaches"],
        "target_tables": ["raw_snapshots", "collector_runs", "data_source_links", "coaches"],
        "status": "implemented_real_coverage",
        "frequency": "weekly",
        "notes": "Head coach identity and history are implemented from Dongqiudi detail/team and team/member_v2. A dedicated source can still improve tenure and win-rate quality later.",
    },
    {
        "job_id": "venue_weather",
        "source": "venue_source_and_weather_api",
        "source_type": "weather",
        "domains": ["venues", "weather"],
        "target_tables": ["raw_snapshots", "collector_runs", "data_source_links", "venues", "weather_snapshots"],
        "status": "implemented_real_coverage",
        "frequency": "daily_00_12",
        "notes": "Venue enrichment and Open-Meteo current observations are implemented; weather is refreshed twice daily at 00:00 and 12:00 local time.",
    },
    {
        "job_id": "ai_news_insights",
        "source": "news_items",
        "source_type": "ai_insight",
        "domains": ["ai_insights"],
        "target_tables": ["ai_insights", "data_source_links"],
        "status": "implemented_rules_baseline",
        "frequency": "after_news_collection_00_12_post_match",
        "notes": "Rules-based AI insight baseline extracts injuries, suspensions, fitness, lineup, squad, coach, training and tactic signals from sourced news. Model eligibility requires confidence >= 0.65. LLM enrichment can replace the classifier later.",
    },
    {
        "job_id": "public_news_rss",
        "source": "guardian_bbc_espn_foxsports",
        "source_type": "football_rss",
        "domains": ["news"],
        "target_tables": ["raw_snapshots", "data_source_links", "news_items"],
        "status": "implemented_partial_real",
        "frequency": "daily_00_12_and_post_match",
        "notes": "Public English football RSS feeds plus dynamic Dongqiudi roster team keywords. Matchday means at least one kickoff on the Asia/Shanghai local date; it raises news priority but does not trigger all-day high-frequency collection.",
    },
]


def collection_catalog_summary(table_counts: dict[str, int] | None = None) -> dict:
    counts = table_counts or {}
    dongqiudi_matches = counts.get("dongqiudi_matches", 0)
    players = counts.get("players", 0)
    player_forms = counts.get("player_form_snapshots", 0)
    player_market_values = counts.get("player_market_values", 0)
    dongqiudi_roster_players = counts.get("dongqiudi_roster_players", 0)
    dongqiudi_roster_player_market_values = counts.get("dongqiudi_roster_player_market_values", 0)
    team_market_values = counts.get("team_market_values", 0)
    standings = counts.get("group_standings", 0)
    team_forms = counts.get("team_form_snapshots", 0)
    weather = counts.get("weather_snapshots", 0)
    venue_enriched = counts.get("venue_enriched", 0)
    coaches = counts.get("coaches", 0)
    injuries = counts.get("injury_reports", 0)
    lineups = counts.get("lineup_snapshots", 0)
    team_match_results = counts.get("team_match_results", 0)
    historical_international_matches = counts.get("historical_international_matches", 0)
    historical_team_match_results = counts.get("historical_team_match_results", 0)
    dongqiudi_team_stats = counts.get("team_stat_snapshots", counts.get("dongqiudi_team_stat_links", 0))
    dongqiudi_team_stat_links = counts.get("dongqiudi_team_stat_links", 0)
    team_stat_metrics = counts.get("team_stat_metrics", 0)
    news = counts.get("news_items", 0)
    ai_news_insights = counts.get("ai_insights", 0)
    dongqiudi_standings = counts.get("dongqiudi_standings_snapshots", 0)
    dongqiudi_player_rankings = counts.get("dongqiudi_player_ranking_snapshots", 0)
    fifa_ranking_source_links = counts.get("fifa_ranking_source_links", 0)

    return {
        "domains": [
            {
                "domain": "matches",
                "status": "complete_real_group_schedule" if dongqiudi_matches >= 72 else ("partial_real" if dongqiudi_matches > 0 else "missing_real_source"),
                "current_source": "dongqiudi/homepage" if dongqiudi_matches > 0 else None,
                "target_tables": ["matches", "teams", "team_aliases"],
            },
            {
                "domain": "news",
                "status": "partial_real" if news > 0 else "missing_real_source",
                "current_source": "dongqiudi/homepage_links + guardian/bbc/espn/foxsports rss" if news > 0 else None,
                "target_tables": ["news_items", "ai_insights"],
            },
            {
                "domain": "standings",
                "status": "complete_real" if standings >= 48 and dongqiudi_standings > 0 else ("partial_real" if dongqiudi_standings > 0 else ("unverified_records" if standings > 0 else "missing_real_source")),
                "current_source": "dongqiudi/world_cup_standings"
                if dongqiudi_standings > 0
                else ("unverified_database_records" if standings > 0 else None),
                "target_tables": ["group_standings"],
            },
            {
                "domain": "player_form",
                "status": "complete_real"
                if dongqiudi_roster_players >= 1248 and player_forms >= 1248
                else (
                    "partial_real"
                    if dongqiudi_player_rankings > 0 or dongqiudi_roster_players > 0
                    else ("unverified_records" if players > 0 and player_forms > 0 else "missing_real_source")
                ),
                "current_source": ", ".join(
                    value
                    for value in [
                        "dongqiudi/world_cup_player_rankings" if dongqiudi_player_rankings > 0 else "",
                        "dongqiudi/world_cup_team_details" if dongqiudi_roster_players > 0 else "",
                    ]
                    if value
                )
                if dongqiudi_player_rankings > 0 or dongqiudi_roster_players > 0
                else ("unverified_database_records" if players > 0 and player_forms > 0 else None),
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
                "status": "complete_real"
                if dongqiudi_roster_player_market_values >= 1248 and team_market_values >= 48
                else ("partial_real" if player_market_values > 0 or team_market_values > 0 else "missing_real_source"),
                "current_source": ", ".join(
                    value
                    for value in [
                        "dongqiudi/world_cup_team_details" if dongqiudi_roster_player_market_values > 0 or team_market_values > 0 else "",
                        "dongqiudi/market_value_ranking" if player_market_values > 0 else "",
                    ]
                    if value
                )
                or None,
                "target_tables": ["players.market_value_eur", "teams.market_value_eur"],
            },
            {
                "domain": "team_form",
                "status": "complete_real" if team_forms >= 48 and dongqiudi_standings > 0 else ("partial_real" if team_forms > 0 and dongqiudi_standings > 0 else "missing_real_source"),
                "current_source": "dongqiudi/world_cup_standings" if team_forms > 0 and dongqiudi_standings > 0 else None,
                "target_tables": ["team_form_snapshots"],
            },
            {
                "domain": "historical_international_matches",
                "status": "complete_real_dataset" if historical_international_matches >= 1000 else ("partial_real" if historical_international_matches > 0 else "missing_real_source"),
                "current_source": "martj42_international_results/historical_results"
                if historical_international_matches > 0
                else None,
                "target_tables": ["historical_international_matches"],
            },
            {
                "domain": "team_match_results",
                "status": "complete_real_dataset" if team_match_results >= 1000 and historical_team_match_results >= 1000 else ("partial_real" if team_match_results > 0 else "missing_real_source"),
                "current_source": ", ".join(
                    value
                    for value in [
                        "dongqiudi/world_cup_schedule" if team_match_results > 0 else "",
                        "martj42_international_results/historical_results" if historical_team_match_results > 0 else "",
                    ]
                    if value
                )
                or None,
                "target_tables": ["team_match_results"],
            },
            {
                "domain": "team_stats",
                "status": "complete_real" if dongqiudi_team_stat_links >= 2160 and team_stat_metrics >= 45 else ("partial_real" if dongqiudi_team_stats > 0 else "schema_ready_missing_source"),
                "current_source": "dongqiudi/world_cup_team_ranking" if dongqiudi_team_stats > 0 else None,
                "target_tables": ["team_stat_snapshots", "data_source_links.team_stat"],
            },
            {
                "domain": "lineups",
                "status": "partial_real" if lineups > 0 else "schema_ready_missing_source",
                "current_source": "dongqiudi/match_lineup" if lineups > 0 else None,
                "target_tables": ["lineup_snapshots", "team_form_snapshots.lineup_stability_score"],
            },
            {
                "domain": "venues_weather",
                "status": "complete_real" if venue_enriched >= 16 and weather > 0 else ("partial_real" if venue_enriched > 0 and weather > 0 else ("partial_real" if counts.get("venues", 0) > 0 else "missing_real_source")),
                "current_source": ", ".join(
                    value
                    for value in [
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
                "status": "complete_real" if coaches >= 48 else ("partial_real" if coaches > 0 else "schema_ready_missing_source"),
                "current_source": "dongqiudi/world_cup_team_details" if coaches > 0 else None,
                "target_tables": ["coaches"],
            },
            {
                "domain": "injuries",
                "status": "partial_real" if injuries > 0 else "schema_ready_missing_source",
                "current_source": "fifa/verified_injury_news" if injuries > 0 else None,
                "target_tables": ["injury_reports", "ai_insights"],
            },
            {
                "domain": "ai_insights",
                "status": "partial_real" if ai_news_insights > 0 else "schema_ready_missing_source",
                "current_source": "ai_news_extractor/news_insight_v1" if ai_news_insights > 0 else None,
                "target_tables": ["ai_insights", "data_source_links.ai_insight"],
            },
        ],
        "jobs": COLLECTOR_CATALOG,
    }
