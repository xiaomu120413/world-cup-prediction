from fastapi import APIRouter, Depends, Header, Query

from app.core.cache import cached_json
from app.core.config import Settings, get_settings
from app.core.responses import envelope, list_envelope, not_found, now_iso
from app.db.session import SessionLocal
from app.data.mock_store import (
    AI_REPORTS,
    GROUP_DETAILS,
    GROUP_SIMULATIONS,
    GROUPS,
    MATCH_ID,
    MATCH_PREDICTIONS,
    MATCHES,
    PLAYERS,
    RANKINGS,
    TEAM_PROFILES,
    TEAMS,
    UPCOMING_MATCHES,
    UPDATED_AT,
)
from app.repositories.repository_provider import use_database, with_public_repository
from app.predictions.service import BaselinePredictionService

router = APIRouter()
admin_router = APIRouter()


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
        updated_at=UPDATED_AT,
        version=settings.api_version,
    )


@router.get("/home")
def home(
    date: str | None = Query(default=None),
    timezone: str = Query(default="Asia/Shanghai"),
    settings: Settings = Depends(get_settings),
):
    if use_database(settings):
        home_data = cached_json(
            settings,
            f"public:home:{date or 'default'}:{timezone}",
            lambda: with_public_repository(lambda repo: repo.get_home_data(date, timezone)),
        )
        if home_data and home_data["champion_rankings"]:
            return envelope(home_data, updated_at=now_iso())

    match = MATCHES[MATCH_ID]
    prediction = MATCH_PREDICTIONS[MATCH_ID]
    featured_match = {
        **match,
        "prediction": {
            "home_win_prob": prediction["probabilities"]["home_win"],
            "draw_prob": prediction["probabilities"]["draw"],
            "away_win_prob": prediction["probabilities"]["away_win"],
            "confidence": prediction["confidence"],
            "tendency": "美国略占优",
        },
        "ai_summary": AI_REPORTS[MATCH_ID]["content"],
    }
    return envelope(
        {
            "featured_match": featured_match,
            "upcoming_matches": UPCOMING_MATCHES,
            "champion_rankings": RANKINGS["champion"][:3],
            "date": date,
            "timezone": timezone,
        },
        updated_at=UPDATED_AT,
    )


@router.get("/matches/today")
def matches_today(
    date: str | None = None,
    include_prediction: bool = True,
    settings: Settings = Depends(get_settings),
):
    if use_database(settings):
        matches = cached_json(
            settings,
            f"public:matches:today:{date or 'default'}:{include_prediction}",
            lambda: with_public_repository(lambda repo: repo.list_matches(include_prediction=include_prediction)),
        )
        if matches:
            return list_envelope(matches, updated_at=now_iso(), date=date)

    matches = [
        {
            **MATCHES[MATCH_ID],
            "prediction_summary": {
                "tendency": "美国略占优",
                "home_win_prob": 0.44,
                "draw_prob": 0.27,
                "away_win_prob": 0.29,
            }
            if include_prediction
            else None,
        },
        *UPCOMING_MATCHES,
    ]
    return list_envelope(matches, updated_at=UPDATED_AT, date=date)


@router.get("/matches/{match_id}")
def match_detail(match_id: str, settings: Settings = Depends(get_settings)):
    if use_database(settings):
        match = with_public_repository(lambda repo: repo.get_match(match_id))
        if not match:
            raise not_found("MATCH_NOT_FOUND", "Match not found")
        return envelope(match, updated_at=now_iso())

    match = MATCHES.get(match_id)
    if not match:
        raise not_found("MATCH_NOT_FOUND", "Match not found")
    return envelope(match, updated_at=UPDATED_AT)


@router.get("/matches/{match_id}/prediction")
def match_prediction(match_id: str, settings: Settings = Depends(get_settings)):
    if use_database(settings):
        prediction = with_public_repository(lambda repo: repo.get_match_prediction(match_id))
        if not prediction:
            raise not_found("PREDICTION_NOT_FOUND", "Prediction not found")
        return envelope(prediction, updated_at=prediction["generated_at"])

    prediction = MATCH_PREDICTIONS.get(match_id)
    if not prediction:
        raise not_found("PREDICTION_NOT_FOUND", "Prediction not found")
    return envelope(prediction, updated_at=UPDATED_AT)


@router.get("/matches/{match_id}/ai-report")
def match_ai_report(match_id: str):
    report = AI_REPORTS.get(match_id)
    if not report:
        raise not_found("AI_REPORT_NOT_FOUND", "AI report not found")
    return envelope(report, updated_at=UPDATED_AT)


@router.get("/groups")
def groups(settings: Settings = Depends(get_settings)):
    if use_database(settings):
        values = cached_json(
            settings,
            "public:groups",
            lambda: with_public_repository(lambda repo: repo.list_groups()),
        )
        if values:
            return list_envelope(values, updated_at=now_iso())

    return list_envelope(GROUPS, updated_at=UPDATED_AT)


@router.get("/groups/{group_id}")
def group_detail(group_id: str, settings: Settings = Depends(get_settings)):
    if use_database(settings):
        group = cached_json(
            settings,
            f"public:groups:{group_id}",
            lambda: with_public_repository(lambda repo: repo.get_group_detail(group_id)),
        )
        if group:
            return envelope(group, updated_at=now_iso())

    group = GROUP_DETAILS.get(group_id)
    if not group:
        raise not_found("GROUP_NOT_FOUND", "Group not found")
    return envelope(group, updated_at=UPDATED_AT)


@router.get("/groups/{group_id}/simulation")
def group_simulation(group_id: str, settings: Settings = Depends(get_settings)):
    if use_database(settings):
        simulation = cached_json(
            settings,
            f"public:groups:{group_id}:simulation",
            lambda: with_public_repository(lambda repo: repo.get_group_simulation(group_id)),
        )
        if simulation:
            return envelope(simulation, updated_at=now_iso())

    simulation = GROUP_SIMULATIONS.get(group_id)
    if not simulation:
        raise not_found("SIMULATION_NOT_FOUND", "Simulation not found")
    return envelope(simulation, updated_at=UPDATED_AT)


@router.get("/predictions/rankings")
def prediction_rankings(
    type: str = Query(default="champion"),
    limit: int = Query(default=20, ge=1, le=100),
    settings: Settings = Depends(get_settings),
):
    if use_database(settings):
        ranking = cached_json(
            settings,
            f"public:rankings:{type}:{limit}",
            lambda: with_public_repository(lambda repo: repo.list_rankings(type, limit)),
        )
        if ranking:
            return envelope(ranking, ranking_type=type, updated_at=now_iso())

    ranking = RANKINGS.get(type)
    if ranking is None:
        raise not_found("RANKING_NOT_FOUND", "Ranking not found")
    return envelope(ranking[:limit], ranking_type=type, updated_at=UPDATED_AT)


@router.get("/teams")
def teams(q: str | None = None, group_id: str | None = None, settings: Settings = Depends(get_settings)):
    values = (
        cached_json(settings, "public:teams", lambda: with_public_repository(lambda repo: repo.list_teams()))
        if use_database(settings)
        else list(TEAMS.values())
    )
    if q:
        q_lower = q.lower()
        values = [
            team
            for team in values
            if q_lower in team["id"].lower()
            or q_lower in team["name"].lower()
            or q_lower in team["abbr"].lower()
        ]
    return list_envelope(values, updated_at=UPDATED_AT, group_id=group_id)


@router.get("/teams/{team_id}")
def team_detail(team_id: str, settings: Settings = Depends(get_settings)):
    team = with_public_repository(lambda repo: repo.get_team(team_id)) if use_database(settings) else TEAMS.get(team_id)
    if not team:
        raise not_found("TEAM_NOT_FOUND", "Team not found")
    return envelope(
        {
            **team,
            "subtitle": f"FIFA排名 {team.get('fifa_rank')} · Elo {team.get('elo_rating')}",
            "ratings": TEAM_PROFILES.get(team_id, {}).get("ratings", []),
            "form": TEAM_PROFILES.get(team_id, {}).get("form", {}),
        },
        updated_at=UPDATED_AT,
    )


@router.get("/teams/{team_id}/profile")
def team_profile(team_id: str, settings: Settings = Depends(get_settings)):
    profile = TEAM_PROFILES.get(team_id)
    if use_database(settings):
        team = with_public_repository(lambda repo: repo.get_team(team_id))
        if team and profile:
            return envelope({**profile, "team": team}, updated_at=now_iso())
        if team:
            return envelope(
                {
                    "team": team,
                    "summary": "Team profile generated from current database baseline.",
                    "probabilities": [],
                    "ratings": [],
                    "form": {"headline": "Database profile pending", "stats": []},
                    "key_players": [],
                    "risks": [],
                },
                updated_at=now_iso(),
            )
    if not profile:
        raise not_found("TEAM_PROFILE_NOT_FOUND", "Team profile not found")
    return envelope(profile, updated_at=UPDATED_AT)


@router.get("/teams/{team_id}/matches")
def team_matches(team_id: str, settings: Settings = Depends(get_settings)):
    if use_database(settings):
        matches = with_public_repository(lambda repo: repo.list_team_matches(team_id))
        if matches is None:
            raise not_found("TEAM_NOT_FOUND", "Team not found")
        return list_envelope(matches, updated_at=now_iso(), team_id=team_id)

    team = TEAMS.get(team_id)
    if not team:
        raise not_found("TEAM_NOT_FOUND", "Team not found")
    matches = [
        match
        for match in MATCHES.values()
        if match["home_team"]["id"] == team_id or match["away_team"]["id"] == team_id
    ]
    return list_envelope(matches, updated_at=UPDATED_AT, team_id=team_id)


@router.get("/players/{player_id}")
def player_detail(player_id: str):
    player = PLAYERS.get(player_id)
    if not player:
        raise not_found("PLAYER_NOT_FOUND", "Player not found")
    return envelope(player, updated_at=UPDATED_AT)


@admin_router.post("/collectors/run", dependencies=[Depends(require_admin)])
def run_collector(payload: dict):
    return envelope(
        {
            "status": "accepted",
            "job_type": payload.get("job_type"),
            "source": payload.get("source"),
            "dry_run": payload.get("dry_run", False),
            "queued_at": now_iso(),
        }
    )


@admin_router.post("/predictions/recompute", dependencies=[Depends(require_admin)])
def recompute_predictions(payload: dict, settings: Settings = Depends(get_settings)):
    if use_database(settings) and not payload.get("dry_run", False):
        with SessionLocal() as db:
            result = BaselinePredictionService(db).recompute(
                scope=payload.get("scope", "matchday"),
                match_ids=payload.get("match_ids") or None,
                model_version=payload.get("model_version", "baseline_2026_06_13"),
                seed=payload.get("seed"),
            )
        return envelope(result)

    return envelope(
        {
            "status": "accepted",
            "scope": payload.get("scope", "matchday"),
            "match_ids": payload.get("match_ids", []),
            "model_version": payload.get("model_version", "baseline_2026_06_13"),
            "queued_at": now_iso(),
        }
    )


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
