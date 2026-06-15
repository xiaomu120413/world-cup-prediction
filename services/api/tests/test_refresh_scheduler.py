from datetime import datetime
from zoneinfo import ZoneInfo

from app.scheduler.refresh import RefreshScheduler, plan_for_cadence, resolve_auto_cadence


def task_ids(cadence: str) -> list[str]:
    return [task.task_id for task in plan_for_cadence(cadence)]


def test_daily_12_plan_keeps_weather_low_frequency():
    ids = task_ids("daily_12")
    tasks = plan_for_cadence("daily_12")

    assert "venue_weather" in ids
    assert "world_cup_48_national_team_matches" in ids
    assert ids.index("venue_weather") < ids.index("world_cup_48_national_team_matches")
    assert "world_cup_schedule_lineups" not in ids
    assert (
        ids.index("public_news_rss")
        < ids.index("ai_news_insights")
        < ids.index("identity_mapping_backfill")
        < ids.index("identity_mapping_audit")
        < ids.index("match_features")
        < ids.index("prediction_recompute")
    )
    assert "prediction_recompute" in ids
    assert "real_data_audit" in ids
    match_task = tasks[ids.index("world_cup_48_national_team_matches")]
    assert match_task.args == ("scripts/export_world_cup_48_national_team_matches.py", "--refresh-source")


def test_daily_00_plan_refreshes_core_match_data_and_news():
    ids = task_ids("daily_00")

    assert "world_cup_schedule_lineups" in ids
    assert "group_standings" in ids
    assert "player_recent_form" in ids
    assert "public_news_rss" in ids
    assert (
        ids.index("public_news_rss")
        < ids.index("ai_news_insights")
        < ids.index("identity_mapping_backfill")
        < ids.index("identity_mapping_audit")
        < ids.index("match_features")
        < ids.index("prediction_recompute")
    )
    assert "venue_weather" not in ids


def test_auto_cadence_selects_fixed_daily_windows_before_db_lookup():
    tz = ZoneInfo("Asia/Shanghai")

    assert resolve_auto_cadence(None, datetime(2026, 6, 15, 0, 5, tzinfo=tz)) == "daily_00"
    assert resolve_auto_cadence(None, datetime(2026, 6, 15, 12, 5, tzinfo=tz)) == "daily_12"


def test_scheduler_dry_run_returns_plan_without_db():
    result = RefreshScheduler(None).run("post_match", dry_run=True)

    assert result["status"] == "planned"
    assert result["cadence"] == "post_match"
    assert [task["task_id"] for task in result["tasks"]][:2] == ["world_cup_schedule_lineups", "group_standings"]
