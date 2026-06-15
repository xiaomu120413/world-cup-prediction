from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import insert, select, text

from app.db.schema import collector_runs, matches

API_TZ = ZoneInfo("Asia/Shanghai")
API_ROOT = Path(__file__).resolve().parents[2]

Cadence = str


@dataclass(frozen=True)
class RefreshTask:
    task_id: str
    args: tuple[str, ...]
    description: str
    timeout_seconds: int = 900

    def command(self) -> list[str]:
        return [sys.executable, *self.args]


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
        RefreshTask("prediction_recompute", ("scripts/recompute_predictions.py", "--scope", "matchday"), "Recompute matchday predictions"),
        RefreshTask("real_data_audit", ("scripts/audit_real_data.py",), "Real-data source audit"),
    ),
    "daily_12": (
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
        RefreshTask("prediction_recompute", ("scripts/recompute_predictions.py", "--scope", "matchday"), "Recompute matchday predictions"),
        RefreshTask("real_data_audit", ("scripts/audit_real_data.py",), "Real-data source audit"),
    ),
    "post_match": (
        RefreshTask("world_cup_schedule_lineups", ("scripts/collect_dongqiudi_match_context.py",), "Post-match scores and played lineups"),
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
        RefreshTask("ai_news_insights", ("scripts/build_ai_news_insights.py",), "Structured AI news insights"),
        RefreshTask("prediction_recompute", ("scripts/recompute_predictions.py", "--scope", "matchday"), "Recompute matchday predictions"),
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
        RefreshTask("prediction_recompute", ("scripts/recompute_predictions.py", "--scope", "matchday"), "Recompute matchday predictions"),
        RefreshTask("real_data_audit", ("scripts/audit_real_data.py",), "Real-data source audit"),
    ),
}


def task_payload(task: RefreshTask) -> dict:
    return {
        "task_id": task.task_id,
        "description": task.description,
        "command": " ".join(task.command()),
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
    if recent_finished_matches(db, current) > 0:
        return "post_match"
    return None


def recent_finished_matches(db, current: datetime) -> int:
    previous_4h = current - timedelta(hours=4)
    return int(
        db.execute(
            select(matches.c.id)
            .where(matches.c.status == "finished", matches.c.kickoff_at >= previous_4h, matches.c.kickoff_at < current)
            .limit(1)
        ).first()
        is not None
    )


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
        return current - timedelta(hours=2), current
    return local_midnight, local_midnight + timedelta(days=1)


def already_ran(db, cadence: Cadence, current: datetime) -> bool:
    start, end = slot_bounds(cadence, current)
    return (
        db.execute(
            select(collector_runs.c.id)
            .where(
                collector_runs.c.source == "scheduler",
                collector_runs.c.job_type == f"refresh:{cadence}",
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
        if dry_run:
            return {
                "status": "planned",
                "cadence": resolved,
                "dry_run": True,
                "tasks": [task_payload(task) for task in tasks],
                "evaluated_at": current.isoformat(),
            }

        if not force and already_ran(self.db, resolved, current):
            return {
                "status": "skipped",
                "cadence": resolved,
                "reason": "cadence_already_completed_for_current_slot",
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
                result = self.run_task(task)
                results.append(result)
                if result["status"] != "success":
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
            "tasks": results,
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(API_TZ).isoformat(),
        }

    def run_task(self, task: RefreshTask) -> dict:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(API_ROOT)
        try:
            process = subprocess.run(
                task.command(),
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
    ) -> None:
        self.db.execute(
            insert(collector_runs).values(
                source="scheduler",
                job_type=f"refresh:{cadence}",
                status=status,
                started_at=started_at,
                finished_at=datetime.now(API_TZ),
                records_read=records_read,
                records_written=records_written,
                error_message=error_message,
                snapshot_ids=[],
            )
        )
