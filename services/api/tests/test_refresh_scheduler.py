from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.scheduler.refresh import (
    RefreshContext,
    RefreshScheduler,
    event_match_job_type,
    pending_event_match_ids,
    plan_for_cadence,
    resolve_auto_cadence,
)


def task_ids(cadence: str) -> list[str]:
    return [task.task_id for task in plan_for_cadence(cadence)]


def test_daily_12_plan_refreshes_live_inputs_before_predictions():
    ids = task_ids("daily_12")
    tasks = plan_for_cadence("daily_12")

    assert ids[:3] == ["world_cup_schedule_lineups", "group_standings", "player_recent_form"]
    assert "venue_weather" in ids
    assert "world_cup_48_national_team_matches" in ids
    assert ids.index("venue_weather") < ids.index("world_cup_48_national_team_matches")
    assert (
        ids.index("world_cup_schedule_lineups")
        < ids.index("group_standings")
        < ids.index("player_recent_form")
        < ids.index("prediction_review")
        < ids.index("public_news_rss")
        < ids.index("ai_news_insights")
        < ids.index("identity_mapping_backfill")
        < ids.index("identity_mapping_audit")
        < ids.index("team_elo_ratings")
        < ids.index("match_features")
        < ids.index("prediction_recompute")
        < ids.index("source_link_backfill")
        < ids.index("real_data_audit")
    )
    assert (
        ids.index("public_news_rss")
        < ids.index("ai_news_insights")
        < ids.index("identity_mapping_backfill")
        < ids.index("identity_mapping_audit")
        < ids.index("team_elo_ratings")
        < ids.index("match_features")
        < ids.index("prediction_recompute")
    )
    assert "prediction_recompute" in ids
    assert ids.index("source_link_backfill") < ids.index("real_data_audit")
    assert "real_data_audit" in ids
    match_task = tasks[ids.index("world_cup_48_national_team_matches")]
    assert match_task.args == ("scripts/export_world_cup_48_national_team_matches.py", "--refresh-source")


def test_daily_00_plan_refreshes_core_match_data_and_news():
    ids = task_ids("daily_00")

    assert "world_cup_schedule_lineups" in ids
    assert "group_standings" in ids
    assert "player_recent_form" in ids
    assert ids.index("player_recent_form") < ids.index("prediction_review")
    assert "public_news_rss" in ids
    assert (
        ids.index("public_news_rss")
        < ids.index("ai_news_insights")
        < ids.index("identity_mapping_backfill")
        < ids.index("identity_mapping_audit")
        < ids.index("match_features")
        < ids.index("prediction_recompute")
        < ids.index("source_link_backfill")
        < ids.index("real_data_audit")
    )
    assert "venue_weather" not in ids


def test_auto_cadence_selects_fixed_daily_windows_before_db_lookup():
    tz = ZoneInfo("Asia/Shanghai")

    assert resolve_auto_cadence(None, datetime(2026, 6, 15, 0, 5, tzinfo=tz)) == "daily_00"
    assert resolve_auto_cadence(None, datetime(2026, 6, 15, 12, 5, tzinfo=tz)) == "daily_12"


def test_scheduler_dry_run_returns_plan_without_db():
    result = RefreshScheduler(None).run("post_match", dry_run=True)

    assert result["status"] == "skipped"
    assert result["cadence"] == "post_match"
    assert result["reason"] == "no_recent_finished_matches"


def test_post_match_plan_reviews_predictions_before_recompute():
    ids = task_ids("post_match")

    assert ids.index("group_standings") < ids.index("prediction_review")
    assert ids.index("prediction_review") < ids.index("team_elo_ratings") < ids.index("match_features") < ids.index("prediction_recompute")


def test_pre_match_90m_plan_is_scoped_before_predictions():
    ids = task_ids("pre_match_90m")

    assert ids[:3] == ["world_cup_schedule_lineups", "public_news_rss", "ai_news_insights"]
    assert ids.index("world_cup_schedule_lineups") < ids.index("match_features") < ids.index("prediction_recompute")


def test_scoped_event_tasks_append_match_ids_and_snapshot_time():
    tz = ZoneInfo("Asia/Shanghai")
    context = RefreshContext(
        cadence="pre_match_90m",
        evaluated_at=datetime(2026, 6, 17, 18, 30, tzinfo=tz),
        lineup_match_ids=("dongqiudi-1",),
        prediction_match_ids=("dongqiudi-1",),
        feature_snapshot_at=datetime(2026, 6, 17, 18, 30, tzinfo=tz),
        run_key="pre_match_90m:dongqiudi-1",
    )
    tasks = {task.task_id: task for task in plan_for_cadence("pre_match_90m")}

    lineup_command = tasks["world_cup_schedule_lineups"].command(context)
    feature_command = tasks["match_features"].command(context)
    prediction_command = tasks["prediction_recompute"].command(context)

    assert "--include-scheduled-lineups" in lineup_command
    assert lineup_command[-2:] == ["--match-id", "dongqiudi-1"]
    assert feature_command[-4:] == ["--match-id", "dongqiudi-1", "--as-of-at", "2026-06-17T18:30:00+08:00"]
    assert prediction_command[-2:] == ["--match-id", "dongqiudi-1"]


def test_event_scope_filters_matches_that_already_completed_successfully():
    class FakeResult:
        def mappings(self):
            return self

        def all(self):
            return [SimpleNamespace(job_type=event_match_job_type("pre_match_90m", "dongqiudi-1"))]

    class FakeDb:
        def execute(self, _query):
            return FakeResult()

    assert pending_event_match_ids(
        FakeDb(),
        "pre_match_90m",
        ("dongqiudi-1", "dongqiudi-2"),
    ) == ("dongqiudi-2",)
