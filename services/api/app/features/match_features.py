from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import log1p
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.schema import (
    ai_insights,
    injury_reports,
    matches,
    model_features,
    teams,
    venues,
    weather_snapshots,
)

FEATURE_SET = "match_pre_match_v1"
FEATURE_SCHEMA_VERSION = "2026-06-15.match-pre-v1"
API_TZ = ZoneInfo("Asia/Shanghai")
DONGQIUDI_MATCH_PUBLIC_ID_PREFIX = "dongqiudi-"
PREDICTION_MATCH_STATUSES = ("scheduled", "live")
STALE_SCHEDULE_GRACE_HOURS = 6

TEAM_STAT_METRICS = (
    "goals",
    "goal_against",
    "shots",
    "shots_on_target",
    "key_passes",
    "pass_accuracy",
    "rating",
    "market_value",
    "fouls",
    "big_chance_created",
    "big_chance_missed",
)

REQUIRED_DIFF_FEATURES = {
    "fifa_rank_diff",
    "market_value_log_diff",
    "history_last20_points_per_match_diff",
    "history_last20_goal_diff_per_match_diff",
    "history_vs_top30_points_per_match_diff",
    "player_avg_form_score_diff",
    "team_stat_goals_value_diff",
    "team_stat_goal_against_value_diff",
}


@dataclass(frozen=True)
class ResultRow:
    result: str
    goals_for: int | None
    goals_against: int | None
    opponent_rank: int | None
    opponent_rank_bucket: str
    competition_name: str
    played_at: datetime


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def result_points(result: str) -> int:
    if result == "win":
        return 3
    if result == "draw":
        return 1
    return 0


def aggregate_results(rows: list[ResultRow]) -> dict[str, float | int | None]:
    matches_count = len(rows)
    if matches_count == 0:
        return {
            "matches": 0,
            "win_rate": None,
            "draw_rate": None,
            "loss_rate": None,
            "points_per_match": None,
            "goals_for_per_match": None,
            "goals_against_per_match": None,
            "goal_diff_per_match": None,
        }

    wins = sum(1 for row in rows if row.result == "win")
    draws = sum(1 for row in rows if row.result == "draw")
    losses = sum(1 for row in rows if row.result == "loss")
    goals_for = sum(row.goals_for or 0 for row in rows)
    goals_against = sum(row.goals_against or 0 for row in rows)
    points = sum(result_points(row.result) for row in rows)
    return {
        "matches": matches_count,
        "win_rate": round(wins / matches_count, 4),
        "draw_rate": round(draws / matches_count, 4),
        "loss_rate": round(losses / matches_count, 4),
        "points_per_match": round(points / matches_count, 4),
        "goals_for_per_match": round(goals_for / matches_count, 4),
        "goals_against_per_match": round(goals_against / matches_count, 4),
        "goal_diff_per_match": round((goals_for - goals_against) / matches_count, 4),
    }


def aggregate_history_windows(rows: list[ResultRow], as_of_at: datetime) -> dict[str, dict[str, float | int | None]]:
    local_date = as_of_at.date()
    since_2024 = date(2024, 1, 1)
    since_2022 = date(2022, 1, 1)
    windows = {
        "last20": rows[:20],
        "since_2024": [row for row in rows if row.played_at.date() >= since_2024 and row.played_at.date() < local_date],
        "since_2022": [row for row in rows if row.played_at.date() >= since_2022 and row.played_at.date() < local_date],
        "world_cup_qualifying": [
            row
            for row in rows
            if "world cup qualification" in row.competition_name.lower() and row.played_at.date() < local_date
        ],
        "vs_top10": [row for row in rows if row.opponent_rank is not None and row.opponent_rank <= 10],
        "vs_top30": [row for row in rows if row.opponent_rank is not None and row.opponent_rank <= 30],
        "vs_top50": [row for row in rows if row.opponent_rank is not None and row.opponent_rank <= 50],
    }
    return {name: aggregate_results(window_rows) for name, window_rows in windows.items()}


def quality_status(missing_features: list[str]) -> str:
    missing_required = REQUIRED_DIFF_FEATURES.intersection(missing_features)
    if not missing_required:
        return "complete"
    if len(missing_required) <= 3:
        return "partial"
    return "insufficient"


def daily_snapshot_time(now: datetime | None = None) -> datetime:
    value = now or datetime.now(API_TZ)
    if value.tzinfo is None:
        value = value.replace(tzinfo=API_TZ)
    return value.astimezone(API_TZ).replace(hour=0, minute=0, second=0, microsecond=0)


def current_snapshot_time(now: datetime | None = None) -> datetime:
    value = now or datetime.now(API_TZ)
    if value.tzinfo is None:
        value = value.replace(tzinfo=API_TZ)
    return value.astimezone(API_TZ)


class MatchFeatureBuilder:
    def __init__(self, db: Session):
        self.db = db

    def build(
        self,
        public_ids: list[str] | None = None,
        dry_run: bool = False,
        roster_only: bool = True,
        snapshot_as_of_at: datetime | None = None,
        public_id_prefix: str | None = DONGQIUDI_MATCH_PUBLIC_ID_PREFIX,
        statuses: tuple[str, ...] | None = PREDICTION_MATCH_STATUSES,
        min_kickoff_at: datetime | None = None,
    ) -> dict[str, Any]:
        snapshot_time = snapshot_as_of_at or current_snapshot_time()
        rows = self.load_matches(
            public_ids,
            roster_only=roster_only,
            public_id_prefix=public_id_prefix,
            statuses=statuses,
            min_kickoff_at=min_kickoff_at,
        )
        feature_rows = [self.build_for_match(row, snapshot_time) for row in rows]
        if not dry_run and feature_rows:
            self.write_features(feature_rows)
            self.db.commit()
        quality_counts: dict[str, int] = {}
        for row in feature_rows:
            quality_counts[row["quality_status"]] = quality_counts.get(row["quality_status"], 0) + 1
        return {
            "status": "dry_run" if dry_run else "completed",
            "feature_set": FEATURE_SET,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "matches_read": len(rows),
            "features_written": 0 if dry_run else len(feature_rows),
            "roster_only": roster_only,
            "public_id_prefix": public_id_prefix,
            "statuses": list(statuses) if statuses else None,
            "min_kickoff_at": min_kickoff_at.isoformat() if min_kickoff_at else f"db_now_minus_{STALE_SCHEDULE_GRACE_HOURS}h",
            "snapshot_as_of_at": snapshot_time.isoformat(),
            "quality_counts": quality_counts,
        }

    def load_matches(
        self,
        public_ids: list[str] | None = None,
        roster_only: bool = True,
        public_id_prefix: str | None = DONGQIUDI_MATCH_PUBLIC_ID_PREFIX,
        statuses: tuple[str, ...] | None = PREDICTION_MATCH_STATUSES,
        min_kickoff_at: datetime | None = None,
    ) -> list[dict[str, Any]]:
        home = teams.alias("home_team")
        away = teams.alias("away_team")
        venue = venues.alias("venue")
        query = (
            select(
                matches.c.id.label("match_id"),
                matches.c.public_id,
                matches.c.kickoff_at,
                matches.c.status,
                matches.c.neutral_site,
                matches.c.source_confidence,
                matches.c.venue_id,
                venue.c.code.label("venue_code"),
                venue.c.name.label("venue_name"),
                venue.c.city.label("venue_city"),
                venue.c.country.label("venue_country"),
                venue.c.capacity.label("venue_capacity"),
                venue.c.altitude_m.label("venue_altitude_m"),
                venue.c.surface.label("venue_surface"),
                home.c.id.label("home_team_id"),
                home.c.code.label("home_code"),
                home.c.name_zh.label("home_name_zh"),
                home.c.name_en.label("home_name_en"),
                home.c.fifa_rank.label("home_fifa_rank"),
                home.c.elo_rating.label("home_elo_rating"),
                home.c.market_value_eur.label("home_market_value_eur"),
                away.c.id.label("away_team_id"),
                away.c.code.label("away_code"),
                away.c.name_zh.label("away_name_zh"),
                away.c.name_en.label("away_name_en"),
                away.c.fifa_rank.label("away_fifa_rank"),
                away.c.elo_rating.label("away_elo_rating"),
                away.c.market_value_eur.label("away_market_value_eur"),
            )
            .join(home, matches.c.home_team_id == home.c.id)
            .join(away, matches.c.away_team_id == away.c.id)
            .outerjoin(venue, matches.c.venue_id == venue.c.id)
            .order_by(matches.c.kickoff_at.asc(), matches.c.public_id.asc())
        )
        if public_ids:
            query = query.where(matches.c.public_id.in_(public_ids))
        else:
            if public_id_prefix:
                query = query.where(matches.c.public_id.like(f"{public_id_prefix}%"))
            if statuses:
                query = query.where(matches.c.status.in_(statuses))
                kickoff_cutoff = min_kickoff_at or text(f"now() - interval '{STALE_SCHEDULE_GRACE_HOURS} hours'")
                query = query.where(or_(matches.c.status == "live", matches.c.kickoff_at >= kickoff_cutoff))
        if roster_only:
            query = query.where(
                text("exists (select 1 from players hp where hp.team_id = matches.home_team_id and hp.code like 'DQD-P%')"),
                text("exists (select 1 from players ap where ap.team_id = matches.away_team_id and ap.code like 'DQD-P%')"),
            )
        return [dict(row) for row in self.db.execute(query).mappings().all()]

    def build_for_match(self, match_row: dict[str, Any], snapshot_as_of_at: datetime) -> dict[str, Any]:
        kickoff_at = match_row["kickoff_at"]
        feature_cutoff_at = min(snapshot_as_of_at, kickoff_at)
        home = self.team_profile(match_row, "home", feature_cutoff_at)
        away = self.team_profile(match_row, "away", feature_cutoff_at)
        weather = self.weather_features(match_row.get("venue_id"), feature_cutoff_at)
        numeric, missing = assemble_numeric_features(match_row, home, away, weather)
        source_summary = {
            "tables": [
                "matches",
                "teams",
                "team_match_results",
                "team_stat_snapshots",
                "players",
                "player_form_snapshots",
                "injury_reports",
                "ai_insights",
                "venues",
                "weather_snapshots",
            ],
            "sources": [
                "dongqiudi",
                "fifa",
                "martj42_international_results",
                "open_meteo",
                "manual_verified",
                "verified_public_news",
                "ai_news_extractor",
            ],
            "home": home["source_summary"],
            "away": away["source_summary"],
            "weather_available": weather is not None,
            "snapshot_as_of_at": snapshot_as_of_at.isoformat(),
            "feature_cutoff_at": feature_cutoff_at.isoformat(),
        }
        features = {
            "identity": {
                "match_id": match_row["public_id"],
                "home_team": match_row["home_code"],
                "away_team": match_row["away_code"],
                "kickoff_at": kickoff_at.isoformat(),
                "snapshot_as_of_at": snapshot_as_of_at.isoformat(),
                "feature_cutoff_at": feature_cutoff_at.isoformat(),
                "neutral_site": bool(match_row["neutral_site"]),
                "venue_code": match_row.get("venue_code"),
            },
            "numeric": numeric,
            "team_context": {
                "home": home["context"],
                "away": away["context"],
            },
            "weather": weather or {},
        }
        return {
            "entity_type": "match",
            "entity_key": match_row["public_id"],
            "feature_set": FEATURE_SET,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "as_of_at": snapshot_as_of_at,
            "features": features,
            "source_summary": source_summary,
            "missing_features": sorted(set(missing)),
            "quality_status": quality_status(missing),
        }

    def team_profile(self, match_row: dict[str, Any], side: str, as_of_at: datetime) -> dict[str, Any]:
        team_id = match_row[f"{side}_team_id"]
        history = self.history_features(team_id, as_of_at)
        team_stats = self.team_stat_features(team_id, as_of_at)
        player_form = self.player_form_features(team_id, as_of_at)
        availability = self.availability_features(team_id, as_of_at)
        context = {
            "code": match_row[f"{side}_code"],
            "name_zh": match_row[f"{side}_name_zh"],
            "name_en": match_row[f"{side}_name_en"],
            "fifa_rank": match_row[f"{side}_fifa_rank"],
            "elo_rating": safe_float(match_row[f"{side}_elo_rating"]),
            "market_value_eur": safe_float(match_row[f"{side}_market_value_eur"]),
            "history": history,
            "team_stats": team_stats,
            "player_form": player_form,
            "availability": availability,
        }
        source_summary = {
            "history_rows_loaded": history.pop("_rows_loaded", 0),
            "team_stat_metrics": len(team_stats),
            "player_form_rows": player_form.get("player_form_count", 0),
            "model_eligible_availability_signals": availability.get("signals", 0),
        }
        return {"context": context, "source_summary": source_summary}

    def history_features(self, team_id: Any, as_of_at: datetime) -> dict[str, Any]:
        rows = self.db.execute(
            text(
                """
                select result, goals_for, goals_against, opponent_rank, opponent_rank_bucket, competition_name, played_at
                from team_match_results
                where team_id = :team_id
                  and played_at < :as_of_at
                  and result in ('win', 'draw', 'loss')
                order by played_at desc
                limit 240
                """
            ),
            {"team_id": team_id, "as_of_at": as_of_at},
        ).mappings().all()
        result_rows = [
            ResultRow(
                result=row.result,
                goals_for=row.goals_for,
                goals_against=row.goals_against,
                opponent_rank=row.opponent_rank,
                opponent_rank_bucket=row.opponent_rank_bucket,
                competition_name=row.competition_name or "",
                played_at=row.played_at,
            )
            for row in rows
        ]
        return {**aggregate_history_windows(result_rows, as_of_at), "_rows_loaded": len(result_rows)}

    def team_stat_features(self, team_id: Any, as_of_at: datetime) -> dict[str, Any]:
        rows = self.db.execute(
            text(
                """
                select distinct on (metric_type)
                    metric_type, metric_name, rank, numeric_value, raw_value, value_unit, source_confidence, as_of_at
                from team_stat_snapshots
                where team_id = :team_id
                  and metric_type = any(:metric_types)
                  and as_of_at <= :as_of_at
                order by metric_type, as_of_at desc
                """
            ),
            {"team_id": team_id, "metric_types": list(TEAM_STAT_METRICS), "as_of_at": as_of_at},
        ).mappings().all()
        return {
            row.metric_type: {
                "name": row.metric_name,
                "rank": row.rank,
                "value": safe_float(row.numeric_value),
                "raw_value": row.raw_value,
                "unit": row.value_unit,
                "source_confidence": safe_float(row.source_confidence),
                "as_of_at": row.as_of_at.isoformat(),
            }
            for row in rows
        }

    def player_form_features(self, team_id: Any, as_of_at: datetime) -> dict[str, Any]:
        row = self.db.execute(
            text(
                """
                with latest_player_form as (
                    select distinct on (p.id)
                        p.id,
                        p.market_value_eur,
                        pf.form_score,
                        pf.goals,
                        pf.assists,
                        pf.shots,
                        pf.key_passes,
                        pf.minutes,
                        pf.availability_status
                    from players p
                    left join player_form_snapshots pf on pf.player_id = p.id and pf.as_of_at <= :as_of_at
                    where p.team_id = :team_id
                      and p.code like 'DQD-P%'
                    order by p.id, pf.as_of_at desc nulls last
                )
                select
                    count(*) as roster_count,
                    count(form_score) as player_form_count,
                    avg(form_score) as avg_form_score,
                    sum(coalesce(goals, 0)) as goals,
                    sum(coalesce(assists, 0)) as assists,
                    sum(coalesce(shots, 0)) as shots,
                    sum(coalesce(key_passes, 0)) as key_passes,
                    sum(coalesce(minutes, 0)) as minutes,
                    count(*) filter (where availability_status not in ('available', 'unknown')) as unavailable_count,
                    sum(coalesce(market_value_eur, 0)) as roster_market_value_eur
                from latest_player_form
                """
            ),
            {"team_id": team_id, "as_of_at": as_of_at},
        ).mappings().one()
        roster_count = int(row.roster_count or 0)
        return {
            "roster_count": roster_count,
            "player_form_count": int(row.player_form_count or 0),
            "avg_form_score": safe_float(row.avg_form_score),
            "goals_per_player": round(float(row.goals or 0) / roster_count, 4) if roster_count else None,
            "assists_per_player": round(float(row.assists or 0) / roster_count, 4) if roster_count else None,
            "shots_per_player": round(float(row.shots or 0) / roster_count, 4) if roster_count else None,
            "key_passes_per_player": round(float(row.key_passes or 0) / roster_count, 4) if roster_count else None,
            "minutes_per_player": round(float(row.minutes or 0) / roster_count, 4) if roster_count else None,
            "unavailable_count": int(row.unavailable_count or 0),
            "roster_market_value_eur": safe_float(row.roster_market_value_eur),
        }

    def availability_features(self, team_id: Any, as_of_at: datetime) -> dict[str, Any]:
        injury_row = self.db.execute(
            select(
                text("count(*) filter (where is_model_eligible) as signals"),
                text("coalesce(sum(impact_score * confidence) filter (where is_model_eligible), 0) as impact"),
            )
            .select_from(injury_reports)
            .where(injury_reports.c.team_id == team_id)
            .where(injury_reports.c.updated_at <= as_of_at)
        ).mappings().one()
        ai_row = self.db.execute(
            select(
                text("count(*) filter (where is_model_eligible) as signals"),
                text("coalesce(sum(impact_score * confidence) filter (where is_model_eligible), 0) as impact"),
            )
            .select_from(ai_insights)
            .where(ai_insights.c.team_id == team_id)
            .where(ai_insights.c.created_at <= as_of_at)
        ).mappings().one()
        return {
            "signals": int(injury_row.signals or 0) + int(ai_row.signals or 0),
            "injury_impact": round(float(injury_row.impact or 0), 4),
            "ai_impact": round(float(ai_row.impact or 0), 4),
            "availability_impact": round(float(injury_row.impact or 0) + float(ai_row.impact or 0), 4),
        }

    def weather_features(self, venue_id: Any | None, as_of_at: datetime) -> dict[str, Any] | None:
        if venue_id is None:
            return None
        row = self.db.execute(
            select(
                weather_snapshots.c.provider,
                weather_snapshots.c.observed_at,
                weather_snapshots.c.temperature_c,
                weather_snapshots.c.humidity_pct,
                weather_snapshots.c.precipitation_mm,
                weather_snapshots.c.wind_speed_kph,
                weather_snapshots.c.wind_direction_deg,
                weather_snapshots.c.weather_code,
                weather_snapshots.c.data_quality,
            )
            .where(weather_snapshots.c.venue_id == venue_id)
            .where(weather_snapshots.c.observed_at <= as_of_at)
            .order_by(weather_snapshots.c.observed_at.desc())
            .limit(1)
        ).mappings().first()
        if not row:
            return None
        return {
            "provider": row.provider,
            "observed_at": row.observed_at.isoformat(),
            "temperature_c": safe_float(row.temperature_c),
            "humidity_pct": row.humidity_pct,
            "precipitation_mm": safe_float(row.precipitation_mm),
            "wind_speed_kph": safe_float(row.wind_speed_kph),
            "wind_direction_deg": row.wind_direction_deg,
            "weather_code": row.weather_code,
            "data_quality": row.data_quality,
        }

    def write_features(self, rows: list[dict[str, Any]]) -> None:
        statement = pg_insert(model_features).values(rows)
        self.db.execute(
            statement.on_conflict_do_update(
                constraint="uq_model_features_entity_feature_set_as_of",
                set_={
                    "feature_schema_version": statement.excluded.feature_schema_version,
                    "as_of_at": statement.excluded.as_of_at,
                    "features": statement.excluded.features,
                    "source_summary": statement.excluded.source_summary,
                    "missing_features": statement.excluded.missing_features,
                    "quality_status": statement.excluded.quality_status,
                    "generated_at": text("now()"),
                },
            )
        )


def put_numeric(target: dict[str, float | int | None], missing: list[str], key: str, value: Any) -> None:
    numeric_value = safe_float(value)
    if numeric_value is None:
        missing.append(key)
        target[key] = None
    else:
        target[key] = round(numeric_value, 6)


def put_diff(target: dict[str, float | int | None], missing: list[str], key: str, home_value: Any, away_value: Any) -> None:
    home_numeric = safe_float(home_value)
    away_numeric = safe_float(away_value)
    if home_numeric is None or away_numeric is None:
        missing.append(key)
        target[key] = None
    else:
        target[key] = round(home_numeric - away_numeric, 6)


def assemble_numeric_features(
    match_row: dict[str, Any],
    home: dict[str, Any],
    away: dict[str, Any],
    weather: dict[str, Any] | None,
) -> tuple[dict[str, float | int | None], list[str]]:
    numeric: dict[str, float | int | None] = {}
    missing: list[str] = []
    home_context = home["context"]
    away_context = away["context"]

    put_numeric(numeric, missing, "home_fifa_rank", home_context["fifa_rank"])
    put_numeric(numeric, missing, "away_fifa_rank", away_context["fifa_rank"])
    put_diff(numeric, missing, "fifa_rank_diff", away_context["fifa_rank"], home_context["fifa_rank"])
    put_numeric(numeric, missing, "home_elo_rating", home_context["elo_rating"])
    put_numeric(numeric, missing, "away_elo_rating", away_context["elo_rating"])
    put_diff(numeric, missing, "elo_diff", home_context["elo_rating"], away_context["elo_rating"])

    home_market = safe_float(home_context["market_value_eur"])
    away_market = safe_float(away_context["market_value_eur"])
    put_numeric(numeric, missing, "home_market_value_log", log1p(home_market) if home_market is not None else None)
    put_numeric(numeric, missing, "away_market_value_log", log1p(away_market) if away_market is not None else None)
    put_diff(
        numeric,
        missing,
        "market_value_log_diff",
        log1p(home_market) if home_market is not None else None,
        log1p(away_market) if away_market is not None else None,
    )

    for window in ("last20", "since_2024", "since_2022", "world_cup_qualifying", "vs_top10", "vs_top30", "vs_top50"):
        home_window = home_context["history"][window]
        away_window = away_context["history"][window]
        for metric in ("matches", "points_per_match", "win_rate", "goals_for_per_match", "goals_against_per_match", "goal_diff_per_match"):
            put_numeric(numeric, missing, f"home_history_{window}_{metric}", home_window[metric])
            put_numeric(numeric, missing, f"away_history_{window}_{metric}", away_window[metric])
            if metric != "matches":
                put_diff(numeric, missing, f"history_{window}_{metric}_diff", home_window[metric], away_window[metric])

    for metric in TEAM_STAT_METRICS:
        home_metric = home_context["team_stats"].get(metric, {})
        away_metric = away_context["team_stats"].get(metric, {})
        put_numeric(numeric, missing, f"home_team_stat_{metric}_value", home_metric.get("value"))
        put_numeric(numeric, missing, f"away_team_stat_{metric}_value", away_metric.get("value"))
        put_diff(numeric, missing, f"team_stat_{metric}_value_diff", home_metric.get("value"), away_metric.get("value"))
        put_numeric(numeric, missing, f"home_team_stat_{metric}_rank", home_metric.get("rank"))
        put_numeric(numeric, missing, f"away_team_stat_{metric}_rank", away_metric.get("rank"))

    for metric in (
        "avg_form_score",
        "goals_per_player",
        "assists_per_player",
        "shots_per_player",
        "key_passes_per_player",
        "minutes_per_player",
        "unavailable_count",
        "roster_market_value_eur",
    ):
        put_numeric(numeric, missing, f"home_player_{metric}", home_context["player_form"].get(metric))
        put_numeric(numeric, missing, f"away_player_{metric}", away_context["player_form"].get(metric))
        put_diff(numeric, missing, f"player_{metric}_diff", home_context["player_form"].get(metric), away_context["player_form"].get(metric))

    put_numeric(numeric, missing, "home_availability_impact", home_context["availability"]["availability_impact"])
    put_numeric(numeric, missing, "away_availability_impact", away_context["availability"]["availability_impact"])
    put_diff(
        numeric,
        missing,
        "availability_impact_diff",
        home_context["availability"]["availability_impact"],
        away_context["availability"]["availability_impact"],
    )

    put_numeric(numeric, missing, "neutral_site", 1 if match_row["neutral_site"] else 0)
    put_numeric(numeric, missing, "match_source_confidence", match_row["source_confidence"])
    if weather:
        for metric in ("temperature_c", "humidity_pct", "precipitation_mm", "wind_speed_kph", "wind_direction_deg", "weather_code"):
            put_numeric(numeric, missing, f"weather_{metric}", weather.get(metric))
    else:
        for metric in ("temperature_c", "humidity_pct", "precipitation_mm", "wind_speed_kph", "wind_direction_deg", "weather_code"):
            put_numeric(numeric, missing, f"weather_{metric}", None)

    return numeric, missing
