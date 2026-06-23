from datetime import date as date_cls, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.collectors.runner import CollectorRunner
from app.core.cache import cached_json
from app.core.config import Settings, get_settings
from app.core.responses import envelope, list_envelope, not_found, now_iso
from app.db.session import SessionLocal
from app.repositories.repository_provider import use_database, with_public_repository
from app.predictions.service import DEFAULT_PREDICTION_MODEL_VERSION, BaselinePredictionService
from app.scheduler.refresh import RefreshScheduler

router = APIRouter()
admin_router = APIRouter()
RANKING_ORDER_CACHE_VERSION = "probability-v3"
REAL_COLLECTOR_SOURCES = {"dongqiudi"}


def require_database_backend(settings: Settings) -> None:
    if not use_database(settings):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "DATABASE_BACKEND_REQUIRED",
                "message": "Public API requires database-backed real data.",
                "details": {"backend": settings.data_backend},
            },
        )


def resolve_match_date(value: str | None, timezone_name: str) -> str:
    if value:
        try:
            date_cls.fromisoformat(value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="date must use YYYY-MM-DD format") from exc
        return value
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=400, detail="timezone is not supported") from exc
    return datetime.now(zone).date().isoformat()


def require_admin(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    expected = f"Bearer {settings.admin_token}"
    if authorization != expected:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Missing or invalid token", "details": {}},
        )


@router.get("/version")
def version(settings: Settings = Depends(get_settings)):
    return envelope(
        {
            "api_version": settings.api_version,
            "build": "2026.06.13",
            "minimum_miniapp_version": "0.1.0",
        },
        updated_at=now_iso(),
        version=settings.api_version,
    )


@router.get("/data-status")
def data_status(settings: Settings = Depends(get_settings)):
    require_database_backend(settings)
    status = cached_json(
        settings,
        "public:data-status",
        lambda: with_public_repository(lambda repo: repo.get_data_status()),
    )
    return envelope({"backend": settings.data_backend, **status}, updated_at=now_iso())

@router.get("/home")
def home(
    date: str | None = Query(default=None),
    timezone: str = Query(default="Asia/Shanghai"),
    settings: Settings = Depends(get_settings),
):
    require_database_backend(settings)
    home_data = cached_json(
        settings,
        f"public:home:{RANKING_ORDER_CACHE_VERSION}:{date or 'default'}:{timezone}",
        lambda: with_public_repository(lambda repo: repo.get_home_data(date, timezone)),
    )
    if home_data and home_data["champion_rankings"]:
        return envelope(home_data, updated_at=now_iso())
    raise not_found("HOME_DATA_NOT_FOUND", "Home data not found")

@router.get("/matches/today")
def matches_today(
    date: str | None = None,
    timezone: str = Query(default="Asia/Shanghai"),
    include_prediction: bool = True,
    settings: Settings = Depends(get_settings),
):
    match_date = resolve_match_date(date, timezone)
    require_database_backend(settings)
    matches = cached_json(
        settings,
        f"public:matches:today:{match_date}:{timezone}:{include_prediction}",
        lambda: with_public_repository(
            lambda repo: repo.list_matches(
                include_prediction=include_prediction,
                real_only=repo.has_real_matches(),
                match_date=match_date,
                timezone=timezone,
            )
        ),
    )
    return list_envelope(matches, updated_at=now_iso(), date=match_date)

@router.get("/matches/{match_id}")
def match_detail(match_id: str, settings: Settings = Depends(get_settings)):
    require_database_backend(settings)
    match = cached_json(
        settings,
        f"public:matches:{match_id}",
        lambda: with_public_repository(lambda repo: repo.get_match(match_id)),
    )
    if not match:
        raise not_found("MATCH_NOT_FOUND", "Match not found")
    return envelope(match, updated_at=now_iso())

@router.get("/matches/{match_id}/prediction")
def match_prediction(match_id: str, settings: Settings = Depends(get_settings)):
    require_database_backend(settings)
    prediction = cached_json(
        settings,
        f"public:matches:{match_id}:prediction",
        lambda: with_public_repository(lambda repo: repo.get_match_prediction(match_id)),
    )
    if not prediction:
        raise not_found("PREDICTION_NOT_FOUND", "Prediction not found")
    return envelope(prediction, updated_at=prediction["generated_at"])

@router.get("/matches/{match_id}/ai-report")
def match_ai_report(match_id: str, settings: Settings = Depends(get_settings)):
    require_database_backend(settings)
    report = cached_json(
        settings,
        f"public:matches:{match_id}:ai-report",
        lambda: with_public_repository(lambda repo: repo.get_match_ai_report(match_id)),
    )
    if report:
        return envelope(report, updated_at=report.get("generated_at") or now_iso())
    raise not_found("AI_REPORT_NOT_FOUND", "AI report not found")

@router.get("/groups")
def groups(settings: Settings = Depends(get_settings)):
    require_database_backend(settings)
    values = cached_json(
        settings,
        "public:groups",
        lambda: with_public_repository(lambda repo: repo.list_groups()),
    )
    return list_envelope(values, updated_at=now_iso())

@router.get("/groups/{group_id}")
def group_detail(group_id: str, settings: Settings = Depends(get_settings)):
    require_database_backend(settings)
    group = cached_json(
        settings,
        f"public:groups:{group_id}",
        lambda: with_public_repository(lambda repo: repo.get_group_detail(group_id)),
    )
    if group:
        return envelope(group, updated_at=now_iso())
    raise not_found("GROUP_NOT_FOUND", "Group not found")

@router.get("/groups/{group_id}/simulation")
def group_simulation(group_id: str, settings: Settings = Depends(get_settings)):
    require_database_backend(settings)
    simulation = cached_json(
        settings,
        f"public:groups:{group_id}:simulation",
        lambda: with_public_repository(lambda repo: repo.get_group_simulation(group_id)),
    )
    if simulation:
        return envelope(simulation, updated_at=now_iso())
    raise not_found("SIMULATION_NOT_FOUND", "Simulation not found")

@router.get("/predictions/rankings")
def prediction_rankings(
    type: str = Query(default="champion"),
    limit: int = Query(default=20, ge=1, le=100),
    settings: Settings = Depends(get_settings),
):
    require_database_backend(settings)
    ranking = cached_json(
        settings,
        f"public:rankings:{RANKING_ORDER_CACHE_VERSION}:{type}:{limit}",
        lambda: with_public_repository(lambda repo: repo.list_rankings(type, limit)),
    )
    return envelope(ranking, ranking_type=type, updated_at=now_iso())

@router.get("/teams")
def teams(q: str | None = None, group_id: str | None = None, settings: Settings = Depends(get_settings)):
    require_database_backend(settings)
    values = cached_json(settings, "public:teams", lambda: with_public_repository(lambda repo: repo.list_teams()))
    if q:
        q_lower = q.lower()
        values = [
            team
            for team in values
            if q_lower in team["id"].lower()
            or q_lower in team["name"].lower()
            or q_lower in team["abbr"].lower()
        ]
    return list_envelope(values, updated_at=now_iso(), group_id=group_id)

@router.get("/teams/{team_id}")
def team_detail(team_id: str, settings: Settings = Depends(get_settings)):
    require_database_backend(settings)
    profile = cached_json(
        settings,
        f"public:teams:{team_id}:profile",
        lambda: with_public_repository(lambda repo: repo.get_team_profile(team_id)),
    )
    if not profile:
        raise not_found("TEAM_NOT_FOUND", "Team not found")
    team = profile["team"]
    return envelope(
        {
            **team,
            "subtitle": f"FIFA排名 {team.get('fifa_rank')} · Elo {team.get('elo_rating')}",
            "ratings": profile["ratings"],
            "form": profile["form"],
        },
        updated_at=now_iso(),
    )

@router.get("/teams/{team_id}/profile")
def team_profile(team_id: str, settings: Settings = Depends(get_settings)):
    require_database_backend(settings)
    database_profile = cached_json(
        settings,
        f"public:teams:{team_id}:profile",
        lambda: with_public_repository(lambda repo: repo.get_team_profile(team_id)),
    )
    if database_profile:
        return envelope(database_profile, updated_at=now_iso())
    raise not_found("TEAM_PROFILE_NOT_FOUND", "Team profile not found")

@router.get("/teams/{team_id}/matches")
def team_matches(team_id: str, settings: Settings = Depends(get_settings)):
    require_database_backend(settings)
    matches = cached_json(
        settings,
        f"public:teams:{team_id}:matches",
        lambda: with_public_repository(lambda repo: repo.list_team_matches(team_id)),
    )
    if matches is None:
        raise not_found("TEAM_NOT_FOUND", "Team not found")
    return list_envelope(matches, updated_at=now_iso(), team_id=team_id)

@router.get("/players/{player_id}")
def player_detail(player_id: str, settings: Settings = Depends(get_settings)):
    require_database_backend(settings)
    player = cached_json(
        settings,
        f"public:players:{player_id}",
        lambda: with_public_repository(lambda repo: repo.get_player_detail(player_id)),
    )
    if player:
        return envelope(player, updated_at=player.get("updated_at") or now_iso())
    raise not_found("PLAYER_NOT_FOUND", "Player not found")

@admin_router.post("/collectors/run", dependencies=[Depends(require_admin)])
def run_collector(payload: dict, settings: Settings = Depends(get_settings)):
    require_database_backend(settings)
    source = payload.get("source")
    if source not in REAL_COLLECTOR_SOURCES:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "REAL_SOURCE_REQUIRED",
                "message": "Collector source must be an approved real source.",
                "details": {"source": source, "allowed_sources": sorted(REAL_COLLECTOR_SOURCES)},
            },
        )
    with SessionLocal() as db:
        result = CollectorRunner(db).run(
            source=source,
            source_type=payload.get("source_type") or payload.get("job_type", "schedule"),
            dry_run=payload.get("dry_run", False),
        )
    return envelope(result)


@admin_router.post("/predictions/recompute", dependencies=[Depends(require_admin)])
def recompute_predictions(payload: dict, settings: Settings = Depends(get_settings)):
    require_database_backend(settings)
    model_version = payload.get("model_version", DEFAULT_PREDICTION_MODEL_VERSION)
    model_kind = payload.get("model_kind") or (
        "baseline" if model_version.startswith("baseline") else "scoreline" if model_version.startswith("scoreline") else "small_outcome"
    )
    if not payload.get("dry_run", False):
        with SessionLocal() as db:
            result = BaselinePredictionService(db).recompute(
                scope=payload.get("scope", "matchday"),
                match_ids=payload.get("match_ids") or None,
                model_version=model_version,
                model_kind=model_kind,
                seed=payload.get("seed"),
            )
        return envelope(result)

    return envelope(
        {
            "status": "accepted",
            "scope": payload.get("scope", "matchday"),
            "match_ids": payload.get("match_ids", []),
            "model_version": model_version,
            "model_kind": model_kind,
            "queued_at": now_iso(),
        }
    )


@admin_router.post("/refresh/run", dependencies=[Depends(require_admin)])
def run_refresh(payload: dict, settings: Settings = Depends(get_settings)):
    require_database_backend(settings)
    with SessionLocal() as db:
        result = RefreshScheduler(db).run(
            cadence=payload.get("cadence", "auto"),
            dry_run=payload.get("dry_run", False),
            force=payload.get("force", False),
            stop_on_error=not payload.get("continue_on_error", False),
        )
    return envelope(result)


@admin_router.post("/ai/rebuild", dependencies=[Depends(require_admin)])
def rebuild_ai(payload: dict):
    return envelope(
        {
            "status": "accepted",
            "target_type": payload.get("target_type"),
            "target_ids": payload.get("target_ids", []),
            "queued_at": now_iso(),
        }
    )
