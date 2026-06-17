from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import insert, or_, select, text

from app.db.schema import collector_runs, matches

API_TZ = ZoneInfo("Asia/Shanghai")
API_ROOT = Path(__file__).resolve().parents[2]

Cadence = str
EVENT_CADENCES = {"post_match", "pre_match_90m"}


def match_id_args(match_ids: tuple[str, ...]) -> tuple[str, ...]:
    args: list[str] = []
    for match_id in match_ids:
        args.extend(["--match-id", match_id])
    return tuple(args)


@dataclass(frozen=True)
class RefreshContext:
    cadence: Cadence
    evaluated_at: datetime
    is_due: bool = True
    reason: str | None = None
    lineup_match_ids: tuple[str, ...] = ()
    prediction_match_ids: tuple[str, ...] = ()
    feature_snapshot_at: datetime | None = None
    run_key: str | None = None

    def args_for(self, source: str) -> tuple[str, ...]:
        if source == "lineup_match_args":
            return match_id_args(self.lineup_match_ids)
        if source == "feature_match_args":
            args = list(match_id_args(self.prediction_match_ids))
            if args and self.feature_snapshot_at:
                args.extend(["--as-of-at", self.feature_snapshot_at.isoformat()])
            return tuple(args)
        if source == "prediction_match_args":
            return match_id_args(self.prediction_match_ids)
        return ()


def context_payload(context: RefreshContext) -> dict:
    return {
        "cadence": context.cadence,
        "is_due": context.is_due,
        "reason": context.reason,
        "lineup_match_ids": list(context.lineup_match_ids),
        "prediction_match_ids": list(context.prediction_match_ids),
        "feature_snapshot_at": context.feature_snapshot_at.isoformat() if context.feature_snapshot_at else None,
        "run_key": context.run_key,
    }


@dataclass(frozen=True)
class RefreshTask:
    task_id: str
    args: tuple[str, ...]
    description: str
    timeout_seconds: int = 900
    arg_sources: tuple[str, ...] = ()
    required_arg_sources: tuple[str, ...] = ()

    def resolved_args(self, context: RefreshContext | None = None) -> tuple[str, ...]:
        values = list(self.args)
        if context:
            for source in self.arg_sources:
                values.extend(context.args_for(source))
        return tuple(values)

    def command(self, context: RefreshContext | None = None) -> list[str]:
        return [sys.executable, *self.resolved_args(context)]

    def should_skip(self, context: RefreshContext | None = None) -> bool:
        if not context:
            return False
        return any(not context.args_for(source) for source in self.required_arg_sources)


REFRESH_PLANS: dict[Cadence, tuple[RefreshTask, ...]] = {
    "daily_00": (
        RefreshTask("world_cup_schedule_lineups", ("scripts/collect_dongqiudi_match_context.py",), "Schedule, scores and played lineups"),
        RefreshTask(
            "group_standings",
            ("scripts/run_collector.py", "--source", "dongqiudi", "--source-type", "world_cup_standings"),
            "World Cup group standings",
        ),
        RefreshTask(
            "player_recent_form",
            ("scripts/run_collector.py", "--source", "dongqiudi", "--source-type", "world_cup_player_rankings"),
            "Current tournament player ranking stats",
        ),
        RefreshTask("world_cup_team_details", ("scripts/collect_dongqiudi_team_details.py",), "Roster, market values, coaches and team ranking metrics", 1800),
        RefreshTask("fifa_mens_world_ranking", ("scripts/collect_fifa_rankings.py",), "FIFA rankings"),
        RefreshTask("verified_injuries", ("scripts/collect_verified_injuries.py",), "Verified injury and suspension signals"),
        RefreshTask("public_news_rss", ("scripts/collect_public_news.py", "--mode", "daily"), "Public news RSS with roster keyword matching"),
        RefreshTask("ai_news_insights", ("scripts/build_ai_news_insights.py",), "Structured AI news insights"),
        RefreshTask("identity_mapping_backfill", ("scripts/backfill_identity_mappings.py",), "Backfill canonical team and player identity mappings"),
        RefreshTask("identity_mapping_audit", ("scripts/audit_identity_mappings.py",), "Canonical identity mapping audit"),
        RefreshTask("match_features", ("scripts/build_match_features.py",), "Build model-ready match feature snapshots"),
        RefreshTask("prediction_recompute", ("scripts/recompute_predictions.py", "--scope", "matchday"), "Recompute matchday predictions"),
        RefreshTask("source_link_backfill", ("scripts/backfill_data_source_links.py",), "Backfill source links before real-data audit"),
        RefreshTask("real_data_audit", ("scripts/audit_real_data.py",), "Real-data source audit"),
    ),
    "daily_12": (
        RefreshTask("world_cup_schedule_lineups", ("scripts/collect_dongqiudi_match_context.py",), "Midday schedule, scores and played lineups"),
        RefreshTask(
            "group_standings",
            ("scripts/run_collector.py", "--source", "dongqiudi", "--source-type", "world_cup_standings"),
            "Midday World Cup group standings",
        ),
        RefreshTask(
            "player_recent_form",
            ("scripts/run_collector.py", "--source", "dongqiudi", "--source-type", "world_cup_player_rankings"),
            "Midday tournament player ranking stats",
        ),
        RefreshTask("venue_weather", ("scripts/enrich_foundation_data.py",), "Venue weather snapshots and foundation enrichment"),
        RefreshTask(
            "world_cup_48_national_team_matches",
            ("scripts/export_world_cup_48_national_team_matches.py", "--refresh-source"),
            "Refresh and export 48-team national-team match records",
            1800,
        ),
        RefreshTask("verified_injuries", ("scripts/collect_verified_injuries.py",), "Verified injury and suspension signals"),
        RefreshTask("public_news_rss", ("scripts/collect_public_news.py", "--mode", "daily"), "Public news RSS with roster keyword matching"),
        RefreshTask("ai_news_insights", ("scripts/build_ai_news_insights.py",), "Structured AI news insights"),
        RefreshTask("identity_mapping_backfill", ("scripts/backfill_identity_mappings.py",), "Backfill canonical team and player identity mappings"),
        RefreshTask("identity_mapping_audit", ("scripts/audit_identity_mappings.py",), "Canonical identity mapping audit"),
        RefreshTask("match_features", ("scripts/build_match_features.py",), "Build model-ready match feature snapshots"),
        RefreshTask("prediction_recompute", ("scripts/recompute_predictions.py", "--scope", "matchday"), "Recompute matchday predictions"),
        RefreshTask("source_link_backfill", ("scripts/backfill_data_source_links.py",), "Backfill source links before real-data audit"),
        RefreshTask("real_data_audit", ("scripts/audit_real_data.py",), "Real-data source audit"),
    ),
    "post_match": (
        RefreshTask(
            "world_cup_schedule_lineups",
            ("scripts/collect_dongqiudi_match_context.py",),
            "Post-match scores and played lineups for recently finished matches",
            arg_sources=("lineup_match_args",),
            required_arg_sources=("lineup_match_args",),
        ),
        RefreshTask(
            "group_standings",
            ("scripts/run_collector.py", "--source", "dongqiudi", "--source-type", "world_cup_standings"),
            "Post-match group standings",
        ),
        RefreshTask(
            "player_recent_form",
            ("scripts/run_collector.py", "--source", "dongqiudi", "--source-type", "world_cup_player_rankings"),
            "Post-match player ranking stats",
        ),
        RefreshTask("public_news_rss", ("scripts/collect_public_news.py", "--mode", "matchday"), "Matchday news refresh"),
        RefreshTask("ai_news_insights", ("scripts/build_ai_news_insights.py", "--limit", "120"), "Structured AI news insights"),
        RefreshTask("identity_mapping_backfill", ("scripts/backfill_identity_mappings.py",), "Backfill canonical team and player identity mappings"),
        RefreshTask("identity_mapping_audit", ("scripts/audit_identity_mappings.py",), "Canonical identity mapping audit"),
        RefreshTask(
            "match_features",
            ("scripts/build_match_features.py",),
            "Build scoped model-ready match feature snapshots",
            arg_sources=("feature_match_args",),
            required_arg_sources=("feature_match_args",),
        ),
        RefreshTask(
            "prediction_recompute",
            ("scripts/recompute_predictions.py", "--scope", "matchday"),
            "Recompute scoped matchday predictions",
            arg_sources=("prediction_match_args",),
            required_arg_sources=("prediction_match_args",),
        ),
        RefreshTask("source_link_backfill", ("scripts/backfill_data_source_links.py",), "Backfill source links before real-data audit"),
        RefreshTask("real_data_audit", ("scripts/audit_real_data.py",), "Real-data source audit"),
    ),
    "pre_match_90m": (
        RefreshTask(
            "world_cup_schedule_lineups",
            ("scripts/collect_dongqiudi_match_context.py", "--include-scheduled-lineups"),
            "T-90m schedule and final lineup refresh for due matches",
            arg_sources=("lineup_match_args",),
            required_arg_sources=("lineup_match_args",),
        ),
        RefreshTask("public_news_rss", ("scripts/collect_public_news.py", "--mode", "matchday"), "T-90m matchday news refresh"),
        RefreshTask("ai_news_insights", ("scripts/build_ai_news_insights.py", "--limit", "80"), "T-90m structured AI news insights"),
        RefreshTask("identity_mapping_backfill", ("scripts/backfill_identity_mappings.py",), "Backfill lineup player identity mappings"),
        RefreshTask("identity_mapping_audit", ("scripts/audit_identity_mappings.py",), "Canonical identity mapping audit"),
        RefreshTask(
            "match_features",
            ("scripts/build_match_features.py",),
            "Build T-90m feature snapshots for due matches",
            arg_sources=("feature_match_args",),
            required_arg_sources=("feature_match_args",),
        ),
        RefreshTask(
            "prediction_recompute",
            ("scripts/recompute_predictions.py", "--scope", "matchday"),
            "Recompute T-90m predictions for due matches",
            arg_sources=("prediction_match_args",),
            required_arg_sources=("prediction_match_args",),
        ),
        RefreshTask("source_link_backfill", ("scripts/backfill_data_source_links.py",), "Backfill source links before real-data audit"),
        RefreshTask("real_data_audit", ("scripts/audit_real_data.py",), "Real-data source audit"),
    ),
    "weekly": (
        RefreshTask("world_cup_team_details", ("scripts/collect_dongqiudi_team_details.py",), "Roster, market values, coaches and team ranking metrics", 1800),
        RefreshTask("fifa_mens_world_ranking", ("scripts/collect_fifa_rankings.py",), "FIFA rankings"),
        RefreshTask(
            "world_cup_48_national_team_matches",
            ("scripts/export_world_cup_48_national_team_matches.py", "--refresh-source"),
            "Refresh and export 48-team national-team match records",
            1800,
        ),
        RefreshTask("missing_market_values_export", ("scripts/export_missing_market_values.py",), "Market-value coverage export"),
        RefreshTask("identity_mapping_backfill", ("scripts/backfill_identity_mappings.py",), "Backfill canonical team and player identity mappings"),
        RefreshTask("identity_mapping_audit", ("scripts/audit_identity_mappings.py",), "Canonical identity mapping audit"),
        RefreshTask("match_features", ("scripts/build_match_features.py",), "Build model-ready match feature snapshots"),
        RefreshTask("prediction_recompute", ("scripts/recompute_predictions.py", "--scope", "matchday"), "Recompute matchday predictions"),
        RefreshTask("source_link_backfill", ("scripts/backfill_data_source_links.py",), "Backfill source links before real-data audit"),
        RefreshTask("real_data_audit", ("scripts/audit_real_data.py",), "Real-data source audit"),
    ),
}


def task_payload(task: RefreshTask, context: RefreshContext | None = None) -> dict:
    return {
        "task_id": task.task_id,
        "description": task.description,
        "command": " ".join(task.command(context)),
        "timeout_seconds": task.timeout_seconds,
    }


def plan_for_cadence(cadence: Cadence) -> tuple[RefreshTask, ...]:
    if cadence not in REFRESH_PLANS:
        raise ValueError(f"Unsupported refresh cadence: {cadence}")
    return REFRESH_PLANS[cadence]


def resolve_auto_cadence(db, now: datetime | None = None) -> Cadence | None:
    current = now or datetime.now(API_TZ)
    if current.hour == 0:
        return "daily_00"
    if current.hour == 12:
        return "daily_12"
    if pre_match_90m_matches(db, current):
        return "pre_match_90m"
    if recent_finished_matches(db, current) > 0:
        return "post_match"
    return None


def scoped_run_key(cadence: Cadence, match_ids: tuple[str, ...]) -> str:
    if not match_ids:
        return "none"
    return f"{cadence}:{','.join(sorted(match_ids))}"


def event_match_job_type(cadence: Cadence, match_id: str) -> str:
    return f"refresh:{cadence}:{match_id}"


def completed_event_match_ids(db, cadence: Cadence, match_ids: tuple[str, ...]) -> set[str]:
    if db is None or not match_ids:
        return set()
    job_types = [event_match_job_type(cadence, match_id) for match_id in match_ids]
    rows = db.execute(
        select(collector_runs.c.job_type)
        .where(
            collector_runs.c.source == "scheduler",
            collector_runs.c.status == "success",
            collector_runs.c.job_type.in_(job_types),
        )
    ).mappings().all()
    prefix = f"refresh:{cadence}:"
    return {str(row.job_type).removeprefix(prefix) for row in rows}


def pending_event_match_ids(db, cadence: Cadence, match_ids: tuple[str, ...]) -> tuple[str, ...]:
    completed = completed_event_match_ids(db, cadence, match_ids)
    return tuple(match_id for match_id in match_ids if match_id not in completed)


def pre_match_90m_matches(db, current: datetime) -> tuple[str, ...]:
    if db is None:
        return ()
    start_at = current + timedelta(minutes=75)
    end_at = current + timedelta(minutes=105)
    rows = db.execute(
        select(matches.c.public_id)
        .where(
            matches.c.public_id.like("dongqiudi-%"),
            matches.c.status.in_(("scheduled", "live")),
            matches.c.kickoff_at >= start_at,
            matches.c.kickoff_at < end_at,
        )
        .order_by(matches.c.kickoff_at.asc(), matches.c.public_id.asc())
    ).mappings().all()
    return pending_event_match_ids(db, "pre_match_90m", tuple(row.public_id for row in rows))


def recent_finished_match_rows(db, current: datetime) -> list[dict]:
    if db is None:
        return []
    previous_4h = current - timedelta(hours=4)
    rows = db.execute(
        select(matches.c.public_id, matches.c.home_team_id, matches.c.away_team_id)
        .where(
            matches.c.public_id.like("dongqiudi-%"),
            matches.c.status == "finished",
            matches.c.kickoff_at >= previous_4h,
            matches.c.kickoff_at < current,
        )
        .order_by(matches.c.kickoff_at.asc(), matches.c.public_id.asc())
    ).mappings().all()
    pending_ids = set(pending_event_match_ids(db, "post_match", tuple(row.public_id for row in rows)))
    return [dict(row) for row in rows if row.public_id in pending_ids]


def recent_finished_matches(db, current: datetime) -> int:
    return len(recent_finished_match_rows(db, current))


def future_matches_for_teams(db, team_ids: set[object], current: datetime) -> tuple[str, ...]:
    if db is None or not team_ids:
        return ()
    rows = db.execute(
        select(matches.c.public_id)
        .where(
            matches.c.public_id.like("dongqiudi-%"),
            matches.c.status.in_(("scheduled", "live")),
            or_(matches.c.status == "live", matches.c.kickoff_at >= current),
            or_(matches.c.home_team_id.in_(list(team_ids)), matches.c.away_team_id.in_(list(team_ids))),
        )
        .order_by(matches.c.kickoff_at.asc(), matches.c.public_id.asc())
        .limit(24)
    ).mappings().all()
    return tuple(row.public_id for row in rows)


def context_for_cadence(db, cadence: Cadence, current: datetime) -> RefreshContext:
    if cadence == "pre_match_90m":
        match_ids = pre_match_90m_matches(db, current)
        return RefreshContext(
            cadence=cadence,
            evaluated_at=current,
            is_due=bool(match_ids),
            reason=None if match_ids else "no_matches_in_t90_window",
            lineup_match_ids=match_ids,
            prediction_match_ids=match_ids,
            feature_snapshot_at=current,
            run_key=scoped_run_key(cadence, match_ids),
        )
    if cadence == "post_match":
        rows = recent_finished_match_rows(db, current)
        finished_match_ids = tuple(row["public_id"] for row in rows)
        team_ids = {row["home_team_id"] for row in rows} | {row["away_team_id"] for row in rows}
        prediction_match_ids = future_matches_for_teams(db, team_ids, current)
        return RefreshContext(
            cadence=cadence,
            evaluated_at=current,
            is_due=bool(finished_match_ids),
            reason=None if finished_match_ids else "no_recent_finished_matches",
            lineup_match_ids=finished_match_ids,
            prediction_match_ids=prediction_match_ids,
            feature_snapshot_at=current,
            run_key=scoped_run_key(cadence, finished_match_ids),
        )
    return RefreshContext(cadence=cadence, evaluated_at=current, run_key=cadence)


def slot_bounds(cadence: Cadence, current: datetime) -> tuple[datetime, datetime]:
    local_midnight = current.replace(hour=0, minute=0, second=0, microsecond=0)
    if cadence == "daily_00":
        return local_midnight, local_midnight + timedelta(days=1)
    if cadence == "daily_12":
        return local_midnight, local_midnight + timedelta(days=1)
    if cadence == "weekly":
        start = local_midnight - timedelta(days=current.weekday())
        return start, start + timedelta(days=7)
    if cadence == "post_match":
        return current - timedelta(hours=4), current
    if cadence == "pre_match_90m":
        slot_start = current.replace(minute=(current.minute // 30) * 30, second=0, microsecond=0)
        return slot_start, slot_start + timedelta(minutes=30)
    return local_midnight, local_midnight + timedelta(days=1)


def job_type_for(cadence: Cadence, context: RefreshContext | None = None) -> str:
    if cadence in EVENT_CADENCES and context and context.run_key:
        return f"refresh:{context.run_key}"
    return f"refresh:{cadence}"


def already_ran(db, cadence: Cadence, current: datetime, context: RefreshContext | None = None) -> bool:
    start, end = slot_bounds(cadence, current)
    return (
        db.execute(
            select(collector_runs.c.id)
            .where(
                collector_runs.c.source == "scheduler",
                collector_runs.c.job_type == job_type_for(cadence, context),
                collector_runs.c.status == "success",
                collector_runs.c.started_at >= start,
                collector_runs.c.started_at < end,
            )
            .limit(1)
        ).first()
        is not None
    )


class RefreshScheduler:
    def __init__(self, db):
        self.db = db

    def run(
        self,
        cadence: Cadence = "auto",
        dry_run: bool = False,
        force: bool = False,
        stop_on_error: bool = True,
        now: datetime | None = None,
    ) -> dict:
        current = now or datetime.now(API_TZ)
        resolved = resolve_auto_cadence(self.db, current) if cadence == "auto" else cadence
        if resolved is None:
            return {
                "status": "skipped",
                "cadence": cadence,
                "reason": "no_due_refresh_window",
                "evaluated_at": current.isoformat(),
            }

        tasks = plan_for_cadence(resolved)
        context = context_for_cadence(self.db, resolved, current)
        if resolved in EVENT_CADENCES and not context.is_due:
            return {
                "status": "skipped",
                "cadence": resolved,
                "reason": context.reason or "no_due_event_matches",
                "evaluated_at": current.isoformat(),
            }
        if dry_run:
            return {
                "status": "planned",
                "cadence": resolved,
                "dry_run": True,
                "scope": context_payload(context),
                "tasks": [task_payload(task, context) for task in tasks],
                "evaluated_at": current.isoformat(),
            }

        if not force and already_ran(self.db, resolved, current, context):
            return {
                "status": "skipped",
                "cadence": resolved,
                "reason": "cadence_already_completed_for_current_slot",
                "scope": context_payload(context),
                "evaluated_at": current.isoformat(),
            }

        if not self.acquire_lock(resolved):
            return {
                "status": "skipped",
                "cadence": resolved,
                "reason": "refresh_already_running",
                "evaluated_at": current.isoformat(),
            }

        started_at = current
        results: list[dict] = []
        status = "success"
        error_message = None
        try:
            for task in tasks:
                result = self.run_task(task, context)
                results.append(result)
                if result["status"] == "failed":
                    status = "failed"
                    error_message = result.get("stderr") or result.get("stdout") or f"{task.task_id} failed"
                    if stop_on_error:
                        break
            self.record_run(
                cadence=resolved,
                status=status,
                started_at=started_at,
                records_read=len(tasks),
                records_written=sum(1 for result in results if result["status"] == "success"),
                error_message=error_message,
                context=context,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        finally:
            self.release_lock(resolved)

        return {
            "status": status,
            "cadence": resolved,
            "scope": context_payload(context),
            "tasks": results,
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(API_TZ).isoformat(),
        }

    def run_task(self, task: RefreshTask, context: RefreshContext | None = None) -> dict:
        if task.should_skip(context):
            return {
                "task_id": task.task_id,
                "description": task.description,
                "status": "skipped",
                "reason": "empty_scoped_match_args",
            }
        env = os.environ.copy()
        env["PYTHONPATH"] = str(API_ROOT)
        try:
            process = subprocess.run(
                task.command(context),
                cwd=API_ROOT,
                env=env,
                text=True,
                capture_output=True,
                timeout=task.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "task_id": task.task_id,
                "description": task.description,
                "status": "failed",
                "returncode": None,
                "stdout": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
                "stderr": f"Timed out after {task.timeout_seconds} seconds",
            }
        return {
            "task_id": task.task_id,
            "description": task.description,
            "status": "success" if process.returncode == 0 else "failed",
            "returncode": process.returncode,
            "stdout": process.stdout[-4000:],
            "stderr": process.stderr[-4000:],
        }

    def acquire_lock(self, cadence: Cadence) -> bool:
        return bool(
            self.db.execute(
                text("select pg_try_advisory_lock(hashtext(:lock_key)::bigint)"),
                {"lock_key": f"scheduler:refresh:{cadence}"},
            ).scalar_one()
        )

    def release_lock(self, cadence: Cadence) -> None:
        self.db.execute(
            text("select pg_advisory_unlock(hashtext(:lock_key)::bigint)"),
            {"lock_key": f"scheduler:refresh:{cadence}"},
        )

    def record_run(
        self,
        cadence: Cadence,
        status: str,
        started_at: datetime,
        records_read: int,
        records_written: int,
        error_message: str | None = None,
        context: RefreshContext | None = None,
    ) -> None:
        finished_at = datetime.now(API_TZ)
        rows = [
            {
                "source": "scheduler",
                "job_type": job_type_for(cadence, context),
                "status": status,
                "started_at": started_at,
                "finished_at": finished_at,
                "records_read": records_read,
                "records_written": records_written,
                "error_message": error_message,
                "snapshot_ids": [],
            }
        ]
        if status == "success" and cadence in EVENT_CADENCES and context:
            existing_job_types = {row["job_type"] for row in rows}
            for match_id in context.lineup_match_ids:
                job_type = event_match_job_type(cadence, match_id)
                if job_type in existing_job_types:
                    continue
                rows.append(
                    {
                        "source": "scheduler",
                        "job_type": job_type,
                        "status": status,
                        "started_at": started_at,
                        "finished_at": finished_at,
                        "records_read": records_read,
                        "records_written": records_written,
                        "error_message": error_message,
                        "snapshot_ids": [],
                    }
                )
                existing_job_types.add(job_type)
        self.db.execute(insert(collector_runs), rows)
