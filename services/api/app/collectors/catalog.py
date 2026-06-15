from __future__ import annotations

COLLECTOR_CATALOG = [
    {
        "job_id": "dongqiudi_homepage",
        "source": "dongqiudi",
        "source_type": "homepage",
        "domains": ["matches", "news"],
        "target_tables": ["raw_snapshots", "collector_runs", "news_items", "teams", "team_aliases", "matches"],
        "status": "implemented_partial_real",
        "frequency": "manual_now_daily_later",
        "notes": "Low-frequency homepage extraction. Useful for Chinese match/news signals, not enough for full production data.",
    },
    {
        "job_id": "official_schedule_venues",
        "source": "thestatsapi",
        "source_type": "fixtures",
        "domains": ["matches", "venues"],
        "target_tables": ["raw_snapshots", "collector_runs", "venues", "matches"],
        "status": "implemented_real_schedule",
        "frequency": "daily_and_matchday",
        "notes": "Static 2026 World Cup fixtures and venues. Covers schedule only, not live scores or player stats.",
    },
    {
        "job_id": "group_standings",
        "source": "dongqiudi",
        "source_type": "world_cup_standings",
        "domains": ["standings"],
        "target_tables": ["raw_snapshots", "collector_runs", "group_standings"],
        "status": "implemented_partial_real",
        "frequency": "daily_and_post_match",
        "notes": "World Cup 2026 group standings from Dongqiudi sport-data API.",
    },
    {
        "job_id": "player_recent_form",
        "source": "dongqiudi",
        "source_type": "world_cup_player_rankings",
        "domains": ["players", "player_form"],
        "target_tables": ["raw_snapshots", "collector_runs", "players", "player_form_snapshots"],
        "status": "implemented_partial_real",
        "frequency": "daily",
        "notes": "World Cup 2026 player rankings from Dongqiudi sport-data API: goals, assists, shots, shots on target and key passes.",
    },
    {
        "job_id": "team_form",
        "source": "historical_match_dataset_or_authorized_stats",
        "source_type": "team_form",
        "domains": ["team_form"],
        "target_tables": ["raw_snapshots", "collector_runs", "team_form_snapshots"],
        "status": "planned_required",
        "frequency": "daily",
        "notes": "Recent team form, records against ranked teams, lineup stability and injury impact.",
    },
    {
        "job_id": "team_market_value",
        "source": "authorized_market_value_source",
        "source_type": "market_value",
        "domains": ["teams", "players"],
        "target_tables": ["raw_snapshots", "collector_runs", "teams", "players"],
        "status": "planned_required",
        "frequency": "weekly",
        "notes": "Team and player market value. Needs licensing check before production use.",
    },
    {
        "job_id": "coach_records",
        "source": "authorized_or_manual_verified",
        "source_type": "coach_record",
        "domains": ["coaches"],
        "target_tables": ["raw_snapshots", "collector_runs", "coaches"],
        "status": "schema_gap",
        "frequency": "weekly",
        "notes": "Head coach tenure, win rate and tournament record. Schema still needs implementation.",
    },
    {
        "job_id": "venue_weather",
        "source": "venue_source_and_weather_api",
        "source_type": "weather",
        "domains": ["venues", "weather"],
        "target_tables": ["raw_snapshots", "collector_runs", "venues"],
        "status": "schema_gap",
        "frequency": "matchday_minus_24h_and_minus_3h",
        "notes": "Weather should be attached to match/venue features. Weather snapshot schema still needs implementation.",
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
]


def collection_catalog_summary(table_counts: dict[str, int] | None = None) -> dict:
    counts = table_counts or {}
    dongqiudi_matches = counts.get("dongqiudi_matches", 0)
    thestatsapi_matches = counts.get("thestatsapi_matches", 0)
    players = counts.get("players", 0)
    player_forms = counts.get("player_form_snapshots", 0)
    standings = counts.get("group_standings", 0)
    news = counts.get("news_items", 0)
    dongqiudi_standings = counts.get("dongqiudi_standings_snapshots", 0)
    dongqiudi_player_rankings = counts.get("dongqiudi_player_ranking_snapshots", 0)

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
                "current_source": "dongqiudi/homepage_links" if news > 0 else None,
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
                if dongqiudi_player_rankings > 0
                else ("sample_or_partial" if players > 0 and player_forms > 0 else "missing_real_source"),
                "current_source": "dongqiudi/world_cup_player_rankings"
                if dongqiudi_player_rankings > 0
                else ("local_sample_or_seed" if players > 0 and player_forms > 0 else None),
                "target_tables": ["players", "player_form_snapshots"],
            },
            {
                "domain": "team_form",
                "status": "missing_real_source",
                "current_source": None,
                "target_tables": ["team_form_snapshots"],
            },
            {
                "domain": "venues_weather",
                "status": "partial_real" if counts.get("venues", 0) > 0 else "missing_schema_or_source",
                "current_source": "thestatsapi/fixtures" if counts.get("venues", 0) > 0 else None,
                "target_tables": ["venues", "weather_snapshots"],
            },
            {
                "domain": "coaches",
                "status": "missing_schema_or_source",
                "current_source": None,
                "target_tables": ["coaches"],
            },
        ],
        "jobs": COLLECTOR_CATALOG,
    }
