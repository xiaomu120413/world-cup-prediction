import json
import re
from datetime import date as date_cls, datetime, time, timedelta, timezone as utc_timezone
from functools import lru_cache
from pathlib import Path
from uuid import UUID as ParsedUUID
from zoneinfo import ZoneInfo

from sqlalchemy import Select, and_, bindparam, case, desc, func, literal, or_, select, text
from sqlalchemy.orm import Session

from app.collectors.catalog import collection_catalog_summary
from app.db.schema import (
    ai_explanations,
    ai_insights,
    competition_stages,
    collector_runs,
    coaches,
    data_source_links,
    group_simulations,
    group_standings,
    historical_international_matches,
    injury_reports,
    lineup_snapshots,
    match_predictions,
    matches,
    news_items,
    player_aliases,
    player_form_snapshots,
    players,
    prediction_snapshots,
    ranking_predictions,
    raw_snapshots,
    scoreline_predictions,
    team_form_snapshots,
    team_match_results,
    team_stat_snapshots,
    teams,
    venues,
    weather_snapshots,
)

TEAM_PUBLIC_IDS = {
    "USA": "usa",
    "PAR": "paraguay",
    "FRA": "france",
    "BRA": "brazil",
    "ENG": "england",
}

SOURCE_TRUST_POLICY = {
    "fifa": {
        "trust_level": "official",
        "default_confidence": 0.95,
        "label": "FIFA official source",
    },
    "dongqiudi": {
        "trust_level": "public_source",
        "default_confidence": 0.8,
        "label": "Dongqiudi public data/source pages",
    },
    "open_meteo": {
        "trust_level": "public_api",
        "default_confidence": 0.85,
        "label": "Open-Meteo weather API",
    },
    "manual_verified": {
        "trust_level": "manual_verified",
        "default_confidence": 0.9,
        "label": "Manually verified public venue facts",
    },
    "guardian": {
        "trust_level": "public_news",
        "default_confidence": 0.82,
        "label": "The Guardian football RSS",
    },
    "bbc": {
        "trust_level": "public_news",
        "default_confidence": 0.84,
        "label": "BBC football RSS",
    },
    "espn": {
        "trust_level": "public_news",
        "default_confidence": 0.82,
        "label": "ESPN soccer RSS",
    },
    "ai_news_extractor": {
        "trust_level": "internal_derived",
        "default_confidence": 0.65,
        "label": "Internal AI news insight extractor",
    },
    "internal_model": {
        "trust_level": "internal_derived",
        "default_confidence": 0.9,
        "label": "Internal derived model values from sourced match results",
    },
    "foxsports": {
        "trust_level": "public_news",
        "default_confidence": 0.82,
        "label": "FOX Sports World Cup RSS",
    },
    "martj42_international_results": {
        "trust_level": "public_dataset",
        "default_confidence": 0.9,
        "label": "Mart Jürisoo international football results dataset",
    },
}

BLOCKED_DATA_SOURCES = {"local_sample"}

APPROVED_REAL_SOURCES = {
    "fifa",
    "dongqiudi",
    "open_meteo",
    "manual_verified",
    "guardian",
    "bbc",
    "espn",
    "ai_news_extractor",
    "internal_model",
    "foxsports",
    "martj42_international_results",
}

WORLD_CUP_GROUP_CODES = tuple(f"group-{letter}" for letter in "abcdefghijkl")
DONGQIUDI_PLAYER_PAGE_URL = "https://www.dongqiudi.com/player/{person_id}.html"
DONGQIUDI_PLAYER_AVATAR_CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "dongqiudi_player_avatars.json"
DONGQIUDI_PLAYER_CODE_PREFIX = "DQD-P"


def safe_float(value) -> float | None:
    return float(value) if value is not None else None


def clamp_score(value: float, minimum: float = 5.0, maximum: float = 9.6) -> float:
    return round(max(minimum, min(maximum, value)), 1)


def source_player_id_from_code(code: str | None) -> str | None:
    if not code or not code.startswith(DONGQIUDI_PLAYER_CODE_PREFIX):
        return None
    return code[len(DONGQIUDI_PLAYER_CODE_PREFIX) :]


@lru_cache(maxsize=1)
def dongqiudi_player_avatar_cache() -> dict[str, str]:
    try:
        raw_value = json.loads(DONGQIUDI_PLAYER_AVATAR_CACHE_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw_value, dict):
        return {}
    return {
        str(key): value
        for key, value in raw_value.items()
        if isinstance(value, str) and value.startswith("http")
    }


def dongqiudi_player_avatar_url(person_id: str | None) -> str | None:
    if not person_id:
        return None
    return dongqiudi_player_avatar_cache().get(str(person_id))


def team_public_id(code: str, name_en: str | None = None) -> str:
    if code in TEAM_PUBLIC_IDS:
        return TEAM_PUBLIC_IDS[code]
    if name_en:
        return name_en.lower().replace(" ", "-")
    return code.lower()


def has_cjk_text(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def display_text(value: str | None, fallback: str | None = None) -> str | None:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    if "?" in text and not has_cjk_text(text):
        return fallback or text.replace("?", "").strip() or text
    return text


def group_display_name(code: str | None, fallback: str | None = None) -> str | None:
    match = re.fullmatch(r"group-([a-l])", code or "")
    if match:
        return f"{match.group(1).upper()}组"
    return display_text(fallback, code)


def team_payload(row) -> dict:
    return {
        "id": team_public_id(row.code, row.name_en),
        "code": row.code,
        "abbr": row.code,
        "name": display_text(row.name_zh, row.name_en or row.code),
        "name_en": display_text(row.name_en, row.code),
        "confederation": row.confederation,
        "fifa_rank": row.fifa_rank,
        "elo_rating": float(row.elo_rating) if row.elo_rating is not None else None,
        "market_value_eur": float(row.market_value_eur) if row.market_value_eur is not None else None,
        "quality_status": row.quality_status,
    }


def match_payload(row) -> dict:
    return {
        "id": row.public_id,
        "stage": row.stage_name,
        "status": row.status,
        "kickoff_at": row.kickoff_at.isoformat(),
        "home_score": row.home_score,
        "away_score": row.away_score,
        "neutral_site": row.neutral_site,
        "source_confidence": float(row.source_confidence),
        "home_team": {
            "id": team_public_id(row.home_code, row.home_name_en),
            "abbr": row.home_code,
            "name": display_text(row.home_name, row.home_name_en or row.home_code),
            "name_en": display_text(row.home_name_en, row.home_code),
            "fifa_rank": row.home_fifa_rank,
            "elo_rating": float(row.home_elo_rating) if row.home_elo_rating is not None else None,
        },
        "away_team": {
            "id": team_public_id(row.away_code, row.away_name_en),
            "abbr": row.away_code,
            "name": display_text(row.away_name, row.away_name_en or row.away_code),
            "name_en": display_text(row.away_name_en, row.away_code),
            "fifa_rank": row.away_fifa_rank,
            "elo_rating": float(row.away_elo_rating) if row.away_elo_rating is not None else None,
        },
        "venue": {
            "name": row.venue_name,
            "city": row.venue_city,
            "country": row.venue_country,
            "timezone": row.venue_timezone,
        }
        if row.venue_name
        else None,
    }


def news_payload(row, relevance: str = "team") -> dict:
    policy = SOURCE_TRUST_POLICY.get(row.source, {})
    return {
        "id": str(row.id),
        "source": row.source,
        "source_label": policy.get("label", row.source),
        "trust_level": policy.get("trust_level"),
        "source_url": row.source_url,
        "title": row.title,
        "summary": row.summary,
        "language": row.language,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
        "related_team_ids": [str(value) for value in (row.related_team_ids or [])],
        "relevance": relevance,
    }


def matchday_bounds_utc(match_date: str, timezone_name: str = "Asia/Shanghai") -> tuple[datetime, datetime]:
    local_date = date_cls.fromisoformat(match_date)
    local_zone = ZoneInfo(timezone_name)
    start_local = datetime.combine(local_date, time.min, tzinfo=local_zone)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(utc_timezone.utc), end_local.astimezone(utc_timezone.utc)


class PublicDataRepository:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def teams_query() -> Select:
        roster_exists = (
            select(players.c.id)
            .where(players.c.team_id == teams.c.id, players.c.code.like("DQD-P%"))
            .exists()
        )
        return (
            select(teams)
            .where(roster_exists)
            .order_by(teams.c.fifa_rank.asc().nulls_last(), teams.c.code.asc())
        )

    @staticmethod
    def team_news_query(team_uuid, team_name_zh: str | None = None, team_name_en: str | None = None, limit: int = 5) -> Select:
        filters = [news_items.c.related_team_ids.any(team_uuid)]
        for value in (team_name_zh, team_name_en):
            if value and value.strip():
                pattern = f"%{value.strip()}%"
                filters.append(news_items.c.title.ilike(pattern))
                filters.append(news_items.c.summary.ilike(pattern))
        return (
            select(news_items)
            .where(or_(*filters))
            .order_by(desc(func.coalesce(news_items.c.published_at, news_items.c.fetched_at)))
            .limit(limit)
        )

    @staticmethod
    def latest_news_query(limit: int = 5) -> Select:
        return (
            select(news_items)
            .order_by(desc(func.coalesce(news_items.c.published_at, news_items.c.fetched_at)))
            .limit(limit)
        )

    @staticmethod
    def team_group_profile_query(team_uuid) -> Select:
        return (
            select(
                competition_stages.c.id.label("stage_uuid"),
                competition_stages.c.code.label("group_id"),
                competition_stages.c.name.label("group_name"),
                group_standings.c.rank,
                group_standings.c.played,
                group_standings.c.wins,
                group_standings.c.draws,
                group_standings.c.losses,
                group_standings.c.goals_for,
                group_standings.c.goals_against,
                group_standings.c.goal_diff,
                group_standings.c.points,
            )
            .join(competition_stages, group_standings.c.stage_id == competition_stages.c.id)
            .where(group_standings.c.team_id == team_uuid)
            .order_by(competition_stages.c.sort_order.asc(), competition_stages.c.code.asc())
            .limit(1)
        )

    @staticmethod
    def latest_team_group_simulation_query(team_uuid, stage_uuid) -> Select:
        return (
            select(
                group_simulations.c.rank_1_prob,
                group_simulations.c.rank_2_prob,
                group_simulations.c.qualify_prob,
                group_simulations.c.expected_points,
            )
            .join(prediction_snapshots, group_simulations.c.prediction_snapshot_id == prediction_snapshots.c.id)
            .where(group_simulations.c.team_id == team_uuid, group_simulations.c.stage_id == stage_uuid)
            .order_by(desc(prediction_snapshots.c.generated_at))
            .limit(1)
        )

    @staticmethod
    def latest_team_form_query(team_uuid) -> Select:
        return (
            select(team_form_snapshots)
            .where(team_form_snapshots.c.team_id == team_uuid)
            .order_by(desc(team_form_snapshots.c.as_of_at))
            .limit(1)
        )

    @staticmethod
    def team_match_results_query(team_uuid, limit: int = 10) -> Select:
        opponent = teams.alias("opponent_team")
        return (
            select(
                team_match_results.c.played_at,
                team_match_results.c.competition_name,
                team_match_results.c.goals_for,
                team_match_results.c.goals_against,
                team_match_results.c.result,
                team_match_results.c.opponent_rank,
                team_match_results.c.opponent_rank_bucket,
                opponent.c.name_zh.label("opponent_name"),
                opponent.c.name_en.label("opponent_name_en"),
            )
            .select_from(team_match_results.outerjoin(opponent, team_match_results.c.opponent_team_id == opponent.c.id))
            .where(team_match_results.c.team_id == team_uuid, team_match_results.c.result != "scheduled")
            .order_by(desc(team_match_results.c.played_at))
            .limit(limit)
        )

    @staticmethod
    def coach_query(team_uuid) -> Select:
        return (
            select(coaches)
            .where(coaches.c.team_id == team_uuid)
            .order_by(coaches.c.started_at.desc().nulls_last(), coaches.c.updated_at.desc())
            .limit(1)
        )

    @staticmethod
    def team_matches_query(team_uuid, limit: int = 4) -> Select:
        home = teams.alias("home_team")
        away = teams.alias("away_team")
        status_rank = case(
            (matches.c.status == "live", 0),
            (matches.c.status == "scheduled", 1),
            (matches.c.status == "finished", 2),
            else_=3,
        )
        return (
            select(
                matches.c.public_id,
                matches.c.kickoff_at,
                matches.c.status,
                matches.c.home_score,
                matches.c.away_score,
                matches.c.neutral_site,
                matches.c.source_confidence,
                competition_stages.c.name.label("stage_name"),
                home.c.code.label("home_code"),
                home.c.name_zh.label("home_name"),
                home.c.name_en.label("home_name_en"),
                home.c.fifa_rank.label("home_fifa_rank"),
                home.c.elo_rating.label("home_elo_rating"),
                away.c.code.label("away_code"),
                away.c.name_zh.label("away_name"),
                away.c.name_en.label("away_name_en"),
                away.c.fifa_rank.label("away_fifa_rank"),
                away.c.elo_rating.label("away_elo_rating"),
                venues.c.name.label("venue_name"),
                venues.c.city.label("venue_city"),
                venues.c.country.label("venue_country"),
                venues.c.timezone.label("venue_timezone"),
            )
            .join(competition_stages, matches.c.stage_id == competition_stages.c.id)
            .join(home, matches.c.home_team_id == home.c.id)
            .join(away, matches.c.away_team_id == away.c.id)
            .outerjoin(venues, matches.c.venue_id == venues.c.id)
            .where(or_(matches.c.home_team_id == team_uuid, matches.c.away_team_id == team_uuid))
            .order_by(status_rank.asc(), matches.c.kickoff_at.asc(), matches.c.public_id.asc())
            .limit(limit)
        )

    @staticmethod
    def match_query(public_id: str) -> Select:
        return PublicDataRepository.matches_query().where(matches.c.public_id == public_id)

    @staticmethod
    def matches_query(
        limit: int | None = None,
        real_only: bool = False,
        match_date: str | None = None,
        timezone_name: str = "Asia/Shanghai",
        min_kickoff_at: datetime | None = None,
    ) -> Select:
        home = teams.alias("home_team")
        away = teams.alias("away_team")
        real_source_rank = case((matches.c.public_id.like("dongqiudi-%"), 0), else_=1)
        status_rank = case(
            (matches.c.status == "live", 0),
            (matches.c.status == "scheduled", 1),
            (matches.c.status == "finished", 2),
            else_=3,
        )
        query = (
            select(
                matches.c.public_id,
                matches.c.kickoff_at,
                matches.c.status,
                matches.c.home_score,
                matches.c.away_score,
                matches.c.neutral_site,
                matches.c.source_confidence,
                competition_stages.c.name.label("stage_name"),
                home.c.code.label("home_code"),
                home.c.name_zh.label("home_name"),
                home.c.name_en.label("home_name_en"),
                home.c.fifa_rank.label("home_fifa_rank"),
                home.c.elo_rating.label("home_elo_rating"),
                away.c.code.label("away_code"),
                away.c.name_zh.label("away_name"),
                away.c.name_en.label("away_name_en"),
                away.c.fifa_rank.label("away_fifa_rank"),
                away.c.elo_rating.label("away_elo_rating"),
                venues.c.name.label("venue_name"),
                venues.c.city.label("venue_city"),
                venues.c.country.label("venue_country"),
                venues.c.timezone.label("venue_timezone"),
            )
            .join(competition_stages, matches.c.stage_id == competition_stages.c.id)
            .join(home, matches.c.home_team_id == home.c.id)
            .join(away, matches.c.away_team_id == away.c.id)
            .outerjoin(venues, matches.c.venue_id == venues.c.id)
            .order_by(real_source_rank.asc(), status_rank.asc(), matches.c.kickoff_at.asc(), matches.c.public_id.asc())
        )
        if real_only:
            query = query.where(matches.c.public_id.like("dongqiudi-%"))
        if match_date:
            start_utc, end_utc = matchday_bounds_utc(match_date, timezone_name)
            query = query.where(matches.c.kickoff_at >= start_utc, matches.c.kickoff_at < end_utc)
        if min_kickoff_at is not None:
            query = query.where(or_(matches.c.status == "live", matches.c.kickoff_at >= min_kickoff_at))
        if limit is not None:
            query = query.limit(limit)
        return query

    @staticmethod
    def latest_prediction_query(public_id: str) -> Select:
        return (
            select(match_predictions)
            .join(matches, match_predictions.c.match_id == matches.c.id)
            .where(matches.c.public_id == public_id)
            .order_by(desc(match_predictions.c.generated_at))
            .limit(1)
        )

    @staticmethod
    def scorelines_query(match_prediction_id) -> Select:
        return (
            select(scoreline_predictions)
            .where(scoreline_predictions.c.match_prediction_id == match_prediction_id)
            .order_by(scoreline_predictions.c.probability.desc(), scoreline_predictions.c.rank.asc())
        )

    @staticmethod
    def match_identity_query(public_id: str) -> Select:
        home = teams.alias("home_team")
        away = teams.alias("away_team")
        return (
            select(
                matches.c.id.label("match_uuid"),
                matches.c.public_id,
                matches.c.home_team_id,
                matches.c.away_team_id,
                home.c.name_zh.label("home_name"),
                home.c.name_en.label("home_name_en"),
                away.c.name_zh.label("away_name"),
                away.c.name_en.label("away_name_en"),
            )
            .join(home, matches.c.home_team_id == home.c.id)
            .join(away, matches.c.away_team_id == away.c.id)
            .where(matches.c.public_id == public_id)
            .limit(1)
        )

    @staticmethod
    def latest_match_explanation_query(match_uuid) -> Select:
        return (
            select(ai_explanations)
            .where(ai_explanations.c.target_type == "match", ai_explanations.c.target_id == match_uuid)
            .order_by(desc(ai_explanations.c.generated_at))
            .limit(1)
        )

    @staticmethod
    def match_ai_insights_query(match_uuid, home_team_uuid, away_team_uuid, limit: int = 6) -> Select:
        return (
            select(ai_insights)
            .where(
                or_(
                    ai_insights.c.match_id == match_uuid,
                    ai_insights.c.team_id.in_([home_team_uuid, away_team_uuid]),
                )
            )
            .order_by(desc(ai_insights.c.created_at))
            .limit(limit)
        )

    @staticmethod
    def player_detail_query(player_id: str) -> Select:
        team = teams.alias("player_team")
        normalized = player_id.strip().lower()
        filters = [
            func.lower(players.c.code) == normalized,
            func.lower(players.c.name_zh) == normalized,
            func.lower(players.c.name_en) == normalized,
            select(player_aliases.c.id)
            .where(
                player_aliases.c.player_id == players.c.id,
                or_(
                    func.lower(player_aliases.c.alias) == normalized,
                    func.lower(player_aliases.c.source_player_id) == normalized,
                ),
            )
            .exists(),
        ]
        if normalized and not normalized.startswith(DONGQIUDI_PLAYER_CODE_PREFIX.lower()):
            filters.append(func.lower(players.c.code) == f"{DONGQIUDI_PLAYER_CODE_PREFIX.lower()}{normalized}")
        if len(normalized) >= 3:
            pattern = f"%{player_id.strip()}%"
            normalized_pattern = f"%{normalized}%"
            accented_chars = "áàäâãåéèëêíìïîóòöôõúùüûçñ"
            plain_chars = "aaaaaaeeeeiiiiooooouuuucn"
            normalized_player_name_en = func.translate(
                func.lower(players.c.name_en),
                accented_chars,
                plain_chars,
            )
            normalized_player_alias = func.translate(
                func.lower(player_aliases.c.alias),
                accented_chars,
                plain_chars,
            )
            filters.extend(
                [
                    players.c.name_zh.ilike(pattern),
                    players.c.name_en.ilike(pattern),
                    normalized_player_name_en.like(normalized_pattern),
                    select(player_aliases.c.id)
                    .where(
                        player_aliases.c.player_id == players.c.id,
                        or_(
                            player_aliases.c.alias.ilike(pattern),
                            normalized_player_alias.like(normalized_pattern),
                        ),
                    )
                    .exists(),
                ]
            )
        try:
            filters.append(players.c.id == ParsedUUID(player_id))
        except (ValueError, TypeError):
            pass
        return (
            select(
                players.c.id.label("player_id"),
                players.c.code.label("player_code"),
                players.c.name_zh,
                players.c.name_en,
                players.c.position,
                players.c.shirt_number,
                players.c.birth_date,
                players.c.club_name,
                players.c.market_value_eur,
                players.c.is_key_player,
                players.c.quality_status.label("player_quality_status"),
                players.c.updated_at.label("player_updated_at"),
                team.c.id.label("team_uuid"),
                team.c.code.label("team_code"),
                team.c.name_zh.label("team_name_zh"),
                team.c.name_en.label("team_name_en"),
                team.c.confederation.label("team_confederation"),
                team.c.fifa_rank.label("team_fifa_rank"),
                team.c.elo_rating.label("team_elo_rating"),
                team.c.market_value_eur.label("team_market_value_eur"),
                team.c.quality_status.label("team_quality_status"),
            )
            .select_from(players.join(team, players.c.team_id == team.c.id))
            .where(or_(*filters))
            .order_by(
                players.c.is_key_player.desc(),
                players.c.market_value_eur.desc().nulls_last(),
                players.c.updated_at.desc(),
            )
            .limit(1)
        )

    @staticmethod
    def latest_player_form_query(player_uuid) -> Select:
        return (
            select(player_form_snapshots)
            .where(player_form_snapshots.c.player_id == player_uuid)
            .order_by(desc(player_form_snapshots.c.as_of_at))
            .limit(1)
        )

    @staticmethod
    def player_injuries_query(player_uuid, limit: int = 5) -> Select:
        return (
            select(injury_reports)
            .where(injury_reports.c.player_id == player_uuid)
            .order_by(desc(injury_reports.c.updated_at))
            .limit(limit)
        )

    @staticmethod
    def player_ai_insights_query(player_uuid, limit: int = 5) -> Select:
        return (
            select(ai_insights)
            .where(ai_insights.c.player_id == player_uuid)
            .order_by(desc(ai_insights.c.created_at))
            .limit(limit)
        )

    @staticmethod
    def rankings_query(ranking_type: str, limit: int) -> Select:
        latest_snapshot = (
            select(prediction_snapshots.c.id.label("snapshot_id"))
            .join(ranking_predictions, ranking_predictions.c.prediction_snapshot_id == prediction_snapshots.c.id)
            .where(ranking_predictions.c.ranking_type == ranking_type)
            .order_by(desc(prediction_snapshots.c.generated_at))
            .limit(1)
            .subquery()
        )
        return (
            select(ranking_predictions, teams)
            .join(teams, ranking_predictions.c.team_id == teams.c.id)
            .join(latest_snapshot, ranking_predictions.c.prediction_snapshot_id == latest_snapshot.c.snapshot_id)
            .where(and_(ranking_predictions.c.ranking_type == ranking_type))
            .order_by(ranking_predictions.c.probability.desc(), ranking_predictions.c.rank.asc())
            .limit(limit)
        )

    @staticmethod
    def groups_query() -> Select:
        standings_progress = (
            select(
                group_standings.c.stage_id.label("stage_id"),
                (func.coalesce(func.sum(group_standings.c.played), 0) / 2).label("matches_finished"),
            )
            .group_by(group_standings.c.stage_id)
            .subquery()
        )
        return (
            select(
                competition_stages.c.code,
                competition_stages.c.name,
                literal(6).label("matches_total"),
                func.coalesce(standings_progress.c.matches_finished, 0).label("matches_finished"),
            )
            .outerjoin(standings_progress, standings_progress.c.stage_id == competition_stages.c.id)
            .where(
                competition_stages.c.stage_type == "group",
                competition_stages.c.code.in_(WORLD_CUP_GROUP_CODES),
            )
            .order_by(competition_stages.c.sort_order.asc(), competition_stages.c.code.asc())
        )

    @staticmethod
    def group_standings_query(group_id: str) -> Select:
        return (
            select(
                competition_stages.c.code.label("group_id"),
                competition_stages.c.name.label("group_name"),
                group_standings.c.rank,
                group_standings.c.played,
                group_standings.c.wins,
                group_standings.c.draws,
                group_standings.c.losses,
                group_standings.c.goals_for,
                group_standings.c.goals_against,
                group_standings.c.goal_diff,
                group_standings.c.points,
                teams.c.code,
                teams.c.name_zh,
                teams.c.name_en,
                teams.c.confederation,
                teams.c.fifa_rank,
                teams.c.elo_rating,
                teams.c.market_value_eur,
                teams.c.quality_status,
            )
            .join(competition_stages, group_standings.c.stage_id == competition_stages.c.id)
            .join(teams, group_standings.c.team_id == teams.c.id)
            .where(competition_stages.c.code == group_id)
            .order_by(group_standings.c.rank.asc())
        )

    @staticmethod
    def group_simulation_query(group_id: str) -> Select:
        latest_snapshot = (
            select(prediction_snapshots.c.id.label("snapshot_id"))
            .join(group_simulations, group_simulations.c.prediction_snapshot_id == prediction_snapshots.c.id)
            .join(competition_stages, group_simulations.c.stage_id == competition_stages.c.id)
            .where(competition_stages.c.code == group_id)
            .order_by(desc(prediction_snapshots.c.generated_at))
            .limit(1)
            .subquery()
        )
        return (
            select(
                group_simulations.c.qualify_prob,
                group_simulations.c.rank_1_prob,
                group_simulations.c.rank_2_prob,
                group_simulations.c.expected_points,
                teams.c.code,
                teams.c.name_zh,
                teams.c.name_en,
                teams.c.confederation,
                teams.c.fifa_rank,
                teams.c.elo_rating,
                teams.c.market_value_eur,
                teams.c.quality_status,
            )
            .join(competition_stages, group_simulations.c.stage_id == competition_stages.c.id)
            .join(teams, group_simulations.c.team_id == teams.c.id)
            .join(latest_snapshot, group_simulations.c.prediction_snapshot_id == latest_snapshot.c.snapshot_id)
            .where(competition_stages.c.code == group_id)
            .order_by(group_simulations.c.qualify_prob.desc())
        )

    def list_teams(self) -> list[dict]:
        rows = self.db.execute(self.teams_query()).mappings().all()
        return [team_payload(row) for row in rows]

    def get_team_row(self, team_id: str):
        rows = self.db.execute(select(teams)).mappings().all()
        return next((row for row in rows if team_public_id(row.code, row.name_en) == team_id), None)

    def get_team(self, team_id: str) -> dict | None:
        row = self.get_team_row(team_id)
        return team_payload(row) if row else None

    def get_data_status(self) -> dict:
        table_counts = {
            "teams": self.count_rows(teams),
            "matches": self.count_rows(matches),
            "dongqiudi_matches": self.count_real_matches(),
            "venues": self.count_rows(venues),
            "venue_enriched": self.count_enriched_venues(),
            "players": self.count_rows(players),
            "player_market_values": self.count_player_market_values(),
            "dongqiudi_roster_players": self.count_dongqiudi_roster_players(),
            "dongqiudi_roster_player_market_values": self.count_dongqiudi_roster_player_market_values(),
            "dongqiudi_roster_teams": self.count_dongqiudi_roster_teams(),
            "ranked_dongqiudi_roster_teams": self.count_ranked_dongqiudi_roster_teams(),
            "team_market_values": self.count_team_market_values(),
            "player_form_snapshots": self.count_rows(player_form_snapshots),
            "team_form_snapshots": self.count_rows(team_form_snapshots),
            "weather_snapshots": self.count_rows(weather_snapshots),
            "coaches": self.count_rows(coaches),
            "injury_reports": self.count_rows(injury_reports),
            "ai_insights": self.count_rows(ai_insights),
            "lineup_snapshots": self.count_rows(lineup_snapshots),
            "historical_international_matches": self.count_rows(historical_international_matches),
            "team_match_results": self.count_rows(team_match_results),
            "historical_team_match_results": self.count_historical_team_match_results(),
            "team_stat_snapshots": self.count_rows(team_stat_snapshots),
            "team_stat_metrics": self.count_team_stat_metrics(),
            "dongqiudi_team_stat_links": self.count_source_links("dongqiudi", "world_cup_team_ranking"),
            "group_standings": self.count_rows(group_standings),
            "raw_snapshots": self.count_rows(raw_snapshots),
            "data_source_links": self.count_rows(data_source_links),
            "dongqiudi_standings_snapshots": self.count_raw_snapshots("dongqiudi", "world_cup_standings"),
            "dongqiudi_player_ranking_snapshots": self.count_raw_snapshots("dongqiudi", "world_cup_player_rankings"),
            "fifa_ranking_source_links": self.count_source_links("fifa", "mens_world_ranking"),
            "collector_runs": self.count_rows(collector_runs),
            "news_items": self.count_rows(news_items),
            "match_predictions": self.count_rows(match_predictions),
            "scoreline_predictions": self.count_rows(scoreline_predictions),
            "ranking_predictions": self.count_rows(ranking_predictions),
        }
        latest_runs = self.db.execute(
            select(
                collector_runs.c.source,
                collector_runs.c.job_type,
                collector_runs.c.status,
                collector_runs.c.records_read,
                collector_runs.c.records_written,
                collector_runs.c.started_at,
                collector_runs.c.finished_at,
                collector_runs.c.error_message,
            )
            .order_by(desc(collector_runs.c.started_at))
            .limit(5)
        ).mappings().all()
        return {
            "mode": "database",
            "canonical_ready": table_counts["teams"] > 0 and table_counts["matches"] > 0,
            "player_form_ready": table_counts["players"] > 0 and table_counts["player_form_snapshots"] > 0,
            "primary_source": "dongqiudi" if table_counts["dongqiudi_matches"] > 0 else "database",
            "table_counts": table_counts,
            "collection_catalog": collection_catalog_summary(table_counts),
            "real_data_audit": self.get_real_data_audit(),
            "coverage_audit": self.get_coverage_audit(table_counts),
            "latest_collector_runs": [
                {
                    "source": row.source,
                    "job_type": row.job_type,
                    "status": row.status,
                    "records_read": row.records_read,
                    "records_written": row.records_written,
                    "started_at": row.started_at.isoformat() if row.started_at else None,
                    "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                    "error_message": row.error_message,
                }
                for row in latest_runs
            ],
        }

    def count_rows(self, table) -> int:
        return int(self.db.execute(select(func.count()).select_from(table)).scalar_one())

    def get_real_data_audit(self) -> dict:
        missing_source_checks = self.missing_source_checks()
        source_quality = self.source_quality_summary()
        blocked_source_records = self.count_blocked_source_records()
        unapproved_source_links = sum(
            item["records"] for item in source_quality if item["source"] not in APPROVED_REAL_SOURCES
        )
        missing_source_total = sum(missing_source_checks.values())
        min_confidence = min((item["min_confidence"] for item in source_quality), default=None)

        return {
            "status": "pass"
            if blocked_source_records == 0 and missing_source_total == 0 and unapproved_source_links == 0
            else "needs_attention",
            "no_sample_data": blocked_source_records == 0,
            "blocked_source_records": blocked_source_records,
            "blocked_sources": sorted(BLOCKED_DATA_SOURCES),
            "all_canonical_data_has_source": missing_source_total == 0,
            "missing_source_checks": missing_source_checks,
            "approved_real_sources": sorted(APPROVED_REAL_SOURCES),
            "unapproved_source_links": unapproved_source_links,
            "min_source_confidence": min_confidence,
            "source_quality": source_quality,
            "policy": SOURCE_TRUST_POLICY,
        }

    def get_coverage_audit(self, table_counts: dict[str, int]) -> dict:
        player_total = table_counts["players"]
        player_market_values = table_counts["player_market_values"]
        team_market_values = table_counts["team_market_values"]
        team_stat_snapshots_count = table_counts["team_stat_snapshots"]
        team_stat_metrics = table_counts["team_stat_metrics"]
        dongqiudi_roster_players = table_counts["dongqiudi_roster_players"]
        dongqiudi_roster_player_market_values = table_counts["dongqiudi_roster_player_market_values"]
        dongqiudi_roster_teams = table_counts["dongqiudi_roster_teams"]
        ranked_dongqiudi_roster_teams = table_counts["ranked_dongqiudi_roster_teams"]
        venue_total = table_counts["venues"]
        venue_enriched = table_counts["venue_enriched"]
        news_sources = self.count_distinct_news_sources()
        schedule_context_matches = self.count_world_cup_schedule_context_matches()
        historical_match_count = table_counts["historical_international_matches"]
        historical_team_match_results = table_counts["historical_team_match_results"]
        roster_team_rank_coverage = ranked_dongqiudi_roster_teams / dongqiudi_roster_teams if dongqiudi_roster_teams else 0
        player_market_coverage = player_market_values / player_total if player_total else 0
        dongqiudi_roster_market_coverage = (
            dongqiudi_roster_player_market_values / dongqiudi_roster_players if dongqiudi_roster_players else 0
        )
        finished_matches = self.count_finished_world_cup_schedule_context_matches()
        lineup_match_coverage = self.count_lineup_matches() / finished_matches if finished_matches else 0
        checks = {
            "dongqiudi_rosters": {
                "status": "pass" if dongqiudi_roster_players >= 48 * 26 and dongqiudi_roster_teams >= 48 else "needs_attention",
                "value": dongqiudi_roster_players,
                "target": 48 * 26,
                "note": "Dongqiudi team/member_v2 is the canonical player dataset: 48 teams x 26 players.",
            },
            "fifa_rank_dongqiudi_roster_team_coverage": {
                "status": "pass" if roster_team_rank_coverage >= 0.9 else "needs_attention",
                "value": round(roster_team_rank_coverage, 3),
                "target": 0.9,
                "note": "Dongqiudi roster teams should have FIFA rank from the team ranking source.",
            },
            "player_market_value_coverage": {
                "status": "pass" if player_market_coverage >= 0.8 else "needs_attention",
                "value": round(player_market_coverage, 3),
                "target": 0.8,
                "note": "General player market coverage. The canonical Dongqiudi roster coverage is checked separately.",
            },
            "dongqiudi_roster_market_value_coverage": {
                "status": "pass" if dongqiudi_roster_players >= 48 * 26 and dongqiudi_roster_market_coverage >= 1 else "needs_attention",
                "value": round(dongqiudi_roster_market_coverage, 3),
                "count": dongqiudi_roster_player_market_values,
                "target": dongqiudi_roster_players,
                "note": "Dongqiudi national-team roster players should have sourced player market values from team pages/member APIs or player profiles.",
            },
            "team_market_value_coverage": {
                "status": "pass" if team_market_values >= 48 else "needs_attention",
                "value": team_market_values,
                "target": 48,
                "note": "Team market value should cover all 48 participating teams.",
            },
            "dongqiudi_team_stat_coverage": {
                "status": "pass" if team_stat_snapshots_count >= 800 and team_stat_metrics >= 40 else "needs_attention",
                "value": team_stat_snapshots_count,
                "metric_count": team_stat_metrics,
                "target": ">=800 rows and >=40 metrics",
                "note": "Dongqiudi team ranking APIs should provide structured team-stat rows for model features.",
            },
            "venue_enrichment": {
                "status": "pass" if venue_total > 0 and venue_enriched == venue_total else "needs_attention",
                "value": venue_enriched,
                "target": venue_total,
                "note": "All venues should have capacity, surface, and weather coordinates.",
            },
            "lineup_finished_match_coverage": {
                "status": "pass" if lineup_match_coverage >= 0.95 else "needs_attention",
                "value": round(lineup_match_coverage, 3),
                "target": 0.95,
                "note": "Lineups are expected only for played matches.",
            },
            "multi_source_news": {
                "status": "pass" if news_sources >= 3 else "needs_attention",
                "value": news_sources,
                "target": 3,
                "note": "News should not rely on Dongqiudi only.",
            },
            "team_match_results": {
                "status": "pass" if schedule_context_matches > 0 and table_counts["team_match_results"] >= schedule_context_matches * 2 else "needs_attention",
                "value": table_counts["team_match_results"],
                "target": schedule_context_matches * 2,
                "note": "Team perspective result rows should cover the normalized Dongqiudi World Cup schedule.",
            },
            "historical_international_matches": {
                "status": "pass" if historical_match_count >= 1000 else "needs_attention",
                "value": historical_match_count,
                "target": ">=1000 actual match rows",
                "note": "Historical national-team results should be stored as one real match row per source match before any model-oriented feature rows are derived.",
            },
            "historical_team_match_results": {
                "status": "pass" if historical_team_match_results >= 1000 else "needs_attention",
                "value": historical_team_match_results,
                "target": ">=1000 team-perspective rows",
                "note": "Historical national-team results should be imported from martj42/international_results or a local Kaggle export.",
            },
        }
        status = "pass" if all(item["status"] == "pass" for item in checks.values()) else "needs_attention"
        return {"status": status, "checks": checks}

    def source_quality_summary(self) -> list[dict]:
        rows = self.db.execute(
            select(
                data_source_links.c.source,
                data_source_links.c.source_type,
                func.count(data_source_links.c.id).label("records"),
                func.min(data_source_links.c.confidence).label("min_confidence"),
                func.avg(data_source_links.c.confidence).label("avg_confidence"),
            )
            .group_by(data_source_links.c.source, data_source_links.c.source_type)
            .order_by(data_source_links.c.source.asc(), data_source_links.c.source_type.asc())
        ).mappings().all()

        return [
            {
                "source": row.source,
                "source_type": row.source_type,
                "records": int(row.records),
                "trust_level": SOURCE_TRUST_POLICY.get(row.source, {}).get("trust_level", "unclassified"),
                "label": SOURCE_TRUST_POLICY.get(row.source, {}).get("label", "Unclassified source"),
                "min_confidence": float(row.min_confidence) if row.min_confidence is not None else None,
                "avg_confidence": round(float(row.avg_confidence), 3) if row.avg_confidence is not None else None,
                "is_approved_real_source": row.source in APPROVED_REAL_SOURCES,
            }
            for row in rows
        ]

    def count_blocked_source_records(self) -> int:
        return int(
            self.db.execute(
                text(
                    """
                    select
                        (select count(*) from raw_snapshots where source in :blocked_sources) +
                        (select count(*) from collector_runs where source in :blocked_sources) +
                        (select count(*) from data_source_links where source in :blocked_sources)
                    """
                ).bindparams(bindparam("blocked_sources", expanding=True)),
                {"blocked_sources": tuple(BLOCKED_DATA_SOURCES)},
            ).scalar_one()
        )

    def missing_source_checks(self) -> dict:
        rows = self.db.execute(
            text(
                """
                select 'matches_without_source' as check_name, count(*) as missing_count
                from matches m
                where not exists (
                    select 1 from data_source_links l where l.entity_type = 'match' and l.entity_key = m.public_id
                )
                union all
                select 'venues_without_source', count(*)
                from venues v
                where not exists (
                    select 1 from data_source_links l where l.entity_type = 'venue' and l.entity_key = v.code
                )
                union all
                select 'teams_without_source', count(*)
                from teams t
                where not exists (
                    select 1 from data_source_links l where l.entity_type = 'team' and l.entity_key = t.code
                )
                union all
                select 'players_without_source', count(*)
                from players p
                where not exists (
                    select 1 from data_source_links l where l.entity_type = 'player' and l.entity_key = p.code
                )
                union all
                select 'news_without_source', count(*)
                from news_items n
                where not exists (
                    select 1 from data_source_links l where l.entity_type = 'news_item' and l.entity_key = n.source_url
                )
                union all
                select 'group_standings_without_source', count(*)
                from group_standings gs
                join competition_stages s on s.id = gs.stage_id
                join teams t on t.id = gs.team_id
                where not exists (
                    select 1 from data_source_links l
                    where l.entity_type = 'group_standing' and l.entity_key = s.code || ':' || t.code
                )
                union all
                select 'team_forms_without_source', count(*)
                from team_form_snapshots tf
                join teams t on t.id = tf.team_id
                where not exists (
                    select 1 from data_source_links l
                    where l.entity_type = 'team_form'
                      and l.entity_key = t.code || ':' || to_char(tf.as_of_at at time zone 'Asia/Shanghai', 'YYYY-MM-DD"T"HH24:MI:SS') || '+08:00'
                )
                union all
                select 'player_forms_without_source', count(*)
                from player_form_snapshots pf
                join players p on p.id = pf.player_id
                where not exists (
                    select 1 from data_source_links l
                    where l.entity_type = 'player_form'
                      and l.entity_key = p.code || ':' || to_char(pf.as_of_at at time zone 'Asia/Shanghai', 'YYYY-MM-DD"T"HH24:MI:SS') || '+08:00'
                )
                union all
                select 'player_market_values_without_source', count(*)
                from players p
                where p.market_value_eur is not null
                  and not exists (
                    select 1 from data_source_links l
                    where l.entity_type = 'player_market_value' and l.entity_key = p.code
                  )
                union all
                select 'team_market_values_without_source', count(*)
                from teams t
                where t.market_value_eur is not null
                  and not exists (
                    select 1 from data_source_links l
                    where l.entity_type = 'team_market_value' and l.entity_key = t.code
                  )
                union all
                select 'team_stat_snapshots_without_source', count(*)
                from team_stat_snapshots ts
                join teams t on t.id = ts.team_id
                where not exists (
                    select 1 from data_source_links l
                    where l.entity_type = 'team_stat' and l.entity_key = t.code || ':' || ts.metric_type
                )
                union all
                select 'weather_snapshots_without_source', count(*)
                from weather_snapshots ws
                join venues v on v.id = ws.venue_id
                where not exists (
                    select 1 from data_source_links l
                    where l.entity_type = 'weather_snapshot'
                      and l.entity_key = v.code || ':' || to_char(ws.observed_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS') || '+00:00'
                )
                union all
                select 'coaches_without_source', count(*)
                from coaches c
                join teams t on t.id = c.team_id
                where not exists (
                    select 1 from data_source_links l
                    where l.entity_type = 'coach' and l.entity_key = t.code || ':' || c.name_zh
                )
                union all
                select 'injury_reports_without_source', count(*)
                from injury_reports ir
                where not exists (
                    select 1 from data_source_links l
                    where l.entity_type = 'injury_report' and l.entity_key = ir.id::text
                )
                union all
                select 'ai_insights_without_source', count(*)
                from ai_insights ai
                where not exists (
                    select 1 from data_source_links l
                    where l.entity_type = 'ai_insight' and l.entity_key = ai.id::text
                )
                union all
                select 'lineup_snapshots_without_source', count(*)
                from lineup_snapshots ls
                join matches m on m.id = ls.match_id
                where not exists (
                    select 1 from data_source_links l
                    where l.entity_type = 'lineup_snapshot'
                      and l.entity_key = m.public_id || ':' || ls.team_id::text || ':' || coalesce(ls.source_player_id, ls.player_name)
                )
                union all
                select 'historical_international_matches_without_source', count(*)
                from historical_international_matches him
                where not exists (
                    select 1 from data_source_links l
                    where l.entity_type = 'historical_international_match'
                      and l.entity_key = him.source_match_id
                )
                union all
                select 'team_match_results_without_source', count(*)
                from team_match_results tmr
                where not exists (
                    select 1 from data_source_links l
                    where l.entity_type = 'team_match_result'
                      and l.entity_key = tmr.team_id::text || ':' || tmr.source_match_id
                )
                order by check_name
                """
            )
        ).mappings().all()
        return {row.check_name: int(row.missing_count) for row in rows}

    def count_real_matches(self) -> int:
        return int(
            self.db.execute(
                select(func.count()).select_from(matches).where(matches.c.public_id.like("dongqiudi-%"))
            ).scalar_one()
        )

    def count_historical_team_match_results(self) -> int:
        return int(
            self.db.execute(
                select(func.count())
                .select_from(team_match_results)
                .where(team_match_results.c.source_match_id.like("martj42-%"))
            ).scalar_one()
        )

    def count_raw_snapshots(self, source: str, source_type: str) -> int:
        return int(
            self.db.execute(
                select(func.count())
                .select_from(raw_snapshots)
                .where(and_(raw_snapshots.c.source == source, raw_snapshots.c.source_type == source_type))
            ).scalar_one()
        )

    def count_source_links(self, source: str, source_type: str) -> int:
        return int(
            self.db.execute(
                select(func.count()).select_from(data_source_links).where(
                    and_(data_source_links.c.source == source, data_source_links.c.source_type == source_type)
                )
            ).scalar_one()
        )

    def count_player_market_values(self) -> int:
        return int(
            self.db.execute(
                select(func.count()).select_from(players).where(players.c.market_value_eur.is_not(None))
            ).scalar_one()
        )

    def count_dongqiudi_roster_players(self) -> int:
        return int(
            self.db.execute(
                select(func.count()).select_from(players).where(players.c.code.like("DQD-P%"))
            ).scalar_one()
        )

    def count_dongqiudi_roster_teams(self) -> int:
        return int(
            self.db.execute(
                select(func.count(func.distinct(players.c.team_id)))
                .select_from(players)
                .where(players.c.code.like("DQD-P%"))
            ).scalar_one()
        )

    def count_ranked_dongqiudi_roster_teams(self) -> int:
        return int(
            self.db.execute(
                select(func.count(func.distinct(players.c.team_id)))
                .select_from(players.join(teams, players.c.team_id == teams.c.id))
                .where(players.c.code.like("DQD-P%"), teams.c.fifa_rank.is_not(None))
            ).scalar_one()
        )

    def count_dongqiudi_roster_player_market_values(self) -> int:
        return int(
            self.db.execute(
                select(func.count())
                .select_from(players)
                .where(players.c.code.like("DQD-P%"), players.c.market_value_eur.is_not(None))
            ).scalar_one()
        )

    def count_team_market_values(self) -> int:
        return int(
            self.db.execute(
                select(func.count()).select_from(teams).where(teams.c.market_value_eur.is_not(None))
            ).scalar_one()
        )

    def count_team_stat_metrics(self) -> int:
        return int(
            self.db.execute(
                select(func.count(func.distinct(team_stat_snapshots.c.metric_type))).select_from(team_stat_snapshots)
            ).scalar_one()
        )

    def count_distinct_news_sources(self) -> int:
        return int(self.db.execute(select(func.count(func.distinct(news_items.c.source))).select_from(news_items)).scalar_one())

    def count_lineup_matches(self) -> int:
        return int(
            self.db.execute(select(func.count(func.distinct(lineup_snapshots.c.match_id))).select_from(lineup_snapshots)).scalar_one()
        )

    def count_finished_world_cup_schedule_context_matches(self) -> int:
        return int(
            self.db.execute(
                text(
                    """
                    select count(*)
                    from matches m
                    where m.status = 'finished'
                      and exists (
                          select 1 from data_source_links l
                          where l.entity_type = 'match'
                            and l.entity_key = m.public_id
                            and l.source = 'dongqiudi'
                            and l.source_type = 'world_cup_schedule'
                      )
                    """
                )
            ).scalar_one()
        )

    def count_world_cup_schedule_context_matches(self) -> int:
        return int(
            self.db.execute(
                text(
                    """
                    select count(*)
                    from matches m
                    where exists (
                        select 1 from data_source_links l
                        where l.entity_type = 'match'
                          and l.entity_key = m.public_id
                          and l.source = 'dongqiudi'
                          and l.source_type = 'world_cup_schedule'
                    )
                    """
                )
            ).scalar_one()
        )

    def count_enriched_venues(self) -> int:
        return int(
            self.db.execute(
                select(func.count())
                .select_from(venues)
                .where(
                    venues.c.capacity.is_not(None),
                    venues.c.surface.is_not(None),
                    venues.c.weather_profile.is_not(None),
                )
            ).scalar_one()
        )

    def list_rankings(self, ranking_type: str, limit: int) -> list[dict]:
        rows = self.db.execute(self.rankings_query(ranking_type, limit)).mappings().all()
        return [
            {
                "rank": row.rank,
                "team": team_payload(row),
                "probability": float(row.probability),
                "delta": float(row.delta) if row.delta is not None else None,
                "reason": row.reason,
            }
            for row in rows
        ]

    def list_team_news(self, team_uuid, team_row=None, limit: int = 5) -> list[dict]:
        rows = self.db.execute(
            self.team_news_query(
                team_uuid,
                getattr(team_row, "name_zh", None),
                getattr(team_row, "name_en", None),
                limit,
            )
        ).mappings().all()
        relevance = "team"
        if not rows:
            rows = self.db.execute(self.latest_news_query(limit)).mappings().all()
            relevance = "latest"
        return [news_payload(row, relevance) for row in rows]

    def has_real_matches(self) -> bool:
        return bool(
            self.db.execute(
                select(matches.c.id).where(matches.c.public_id.like("dongqiudi-%")).limit(1)
            ).first()
        )

    def list_matches(
        self,
        limit: int | None = None,
        include_prediction: bool = False,
        real_only: bool = False,
        match_date: str | None = None,
        timezone: str = "Asia/Shanghai",
        min_kickoff_at: datetime | None = None,
    ) -> list[dict]:
        rows = self.db.execute(
            self.matches_query(
                limit,
                real_only=real_only,
                match_date=match_date,
                timezone_name=timezone,
                min_kickoff_at=min_kickoff_at,
            )
        ).mappings().all()
        values = [match_payload(row) for row in rows]
        if include_prediction:
            for value in values:
                prediction = self.get_match_prediction(value["id"])
                value["prediction_summary"] = self.prediction_summary(prediction) if prediction else None
        return values

    def get_match(self, public_id: str) -> dict | None:
        row = self.db.execute(self.match_query(public_id)).mappings().first()
        if row is None:
            return None
        value = match_payload(row)
        return value

    def get_match_prediction(self, public_id: str) -> dict | None:
        prediction = self.db.execute(self.latest_prediction_query(public_id)).mappings().first()
        if prediction is None:
            return None
        scorelines = self.db.execute(self.scorelines_query(prediction.id)).mappings().all()
        return {
            "probabilities": {
                "home_win": float(prediction.home_win_prob),
                "draw": float(prediction.draw_prob),
                "away_win": float(prediction.away_win_prob),
            },
            "inference_mode": prediction.inference_mode,
            "calibration_applied": prediction.calibration_applied,
            "fallback_reason": prediction.fallback_reason,
            "base_probabilities": prediction.base_probabilities,
            "expected_goals": {
                "home": float(prediction.home_expected_goals),
                "away": float(prediction.away_expected_goals),
            },
            "confidence": prediction.confidence,
            "key_factors": prediction.key_factors,
            "feature_snapshot": prediction.feature_snapshot or {},
            "match_feature_quality_status": prediction.feature_quality_status,
            "match_feature_missing_count": prediction.feature_missing_count or 0,
            "match_feature_sources": prediction.feature_sources or [],
            "scorelines": [
                {
                    "home_goals": item.home_goals,
                    "away_goals": item.away_goals,
                    "probability": float(item.probability),
                    "rank": item.rank,
                }
                for item in scorelines
            ],
            "generated_at": prediction.generated_at.isoformat(),
        }

    def get_match_ai_report(self, public_id: str) -> dict | None:
        identity = self.db.execute(self.match_identity_query(public_id)).mappings().first()
        if identity is None:
            return None

        prediction = self.get_match_prediction(public_id)
        explanation = self.db.execute(self.latest_match_explanation_query(identity.match_uuid)).mappings().first()
        insights = self.db.execute(
            self.match_ai_insights_query(identity.match_uuid, identity.home_team_id, identity.away_team_id)
        ).mappings().all()
        if explanation is None and prediction is None and not insights:
            return None

        generated_at = None
        if explanation and explanation.generated_at:
            generated_at = explanation.generated_at.isoformat()
        elif prediction:
            generated_at = prediction["generated_at"]
        elif insights and insights[0].created_at:
            generated_at = insights[0].created_at.isoformat()

        return {
            "match_id": public_id,
            "title": explanation.title if explanation else self.match_report_title(identity),
            "content": explanation.content if explanation else self.match_report_content(identity, prediction, insights),
            "confidence_label": explanation.confidence_label
            if explanation
            else self.prediction_confidence_label(prediction["confidence"] if prediction else None),
            "evidence": self.match_report_evidence(prediction, explanation, insights),
            "probabilities": prediction["probabilities"] if prediction else None,
            "expected_goals": prediction["expected_goals"] if prediction else None,
            "scorelines": prediction["scorelines"][:5] if prediction else [],
            "feature_sources": prediction["match_feature_sources"] if prediction else [],
            "source": "ai_explanations" if explanation else "match_predictions",
            "generated_at": generated_at,
        }

    @staticmethod
    def match_report_title(identity) -> str:
        home = display_text(identity.home_name, identity.home_name_en)
        away = display_text(identity.away_name, identity.away_name_en)
        return f"{home} vs {away} AI 赛前报告"

    @staticmethod
    def prediction_confidence_label(value: str | None) -> str:
        if value == "high":
            return "high"
        if value == "medium":
            return "medium"
        if value == "low":
            return "low"
        return value or "unknown"

    @staticmethod
    def match_report_content(identity, prediction: dict | None, insights: list) -> str:
        home = display_text(identity.home_name, identity.home_name_en)
        away = display_text(identity.away_name, identity.away_name_en)
        if prediction:
            probabilities = prediction["probabilities"]
            expected_goals = prediction["expected_goals"]
            return (
                f"{home} vs {away} 的赛前模型已生成：主队胜率 {probabilities['home_win']:.1%}，"
                f"平局 {probabilities['draw']:.1%}，客队胜率 {probabilities['away_win']:.1%}；"
                f"预期进球 {expected_goals['home']:.2f}-{expected_goals['away']:.2f}。"
                f"报告基于已入库的比赛预测、比分模型和赛前特征证据生成。"
            )
        return (
            f"{home} vs {away} 已有 AI 情报记录，但当前还没有生成比赛预测快照。"
        )

    @staticmethod
    def numeric_value(value) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def match_report_evidence(self, prediction: dict | None, explanation, insights: list) -> list[dict]:
        evidence = []
        if explanation and isinstance(explanation.evidence_refs, list):
            for item in explanation.evidence_refs[:6]:
                if not isinstance(item, dict):
                    continue
                evidence.append(
                    {
                        "label": str(item.get("label") or item.get("source") or "evidence"),
                        "value": self.numeric_value(item.get("value")) or 0,
                        "note": str(item.get("note") or item.get("text") or "ai_explanations"),
                    }
                )
        if prediction:
            for item in (prediction.get("key_factors") or [])[:6]:
                if not isinstance(item, dict):
                    continue
                evidence.append(
                    {
                        "label": str(item.get("label") or "feature"),
                        "value": self.numeric_value(item.get("value")) or 0,
                        "note": str(item.get("note") or "match_predictions"),
                    }
                )
        for insight in insights[:6]:
            evidence.append(
                {
                    "label": insight.impact_area or insight.event_type,
                    "value": float(insight.impact_score),
                    "note": insight.evidence_text,
                    "source_url": insight.source_url,
                    "confidence": float(insight.confidence),
                }
            )
        return evidence[:8]

    def get_player_detail(self, player_id: str) -> dict | None:
        row = self.db.execute(self.player_detail_query(player_id)).mappings().first()
        if row is None:
            return None

        form = self.db.execute(self.latest_player_form_query(row.player_id)).mappings().first()
        injuries = self.db.execute(self.player_injuries_query(row.player_id)).mappings().all()
        insights = self.db.execute(self.player_ai_insights_query(row.player_id)).mappings().all()
        source_player_id = source_player_id_from_code(row.player_code)
        updated_at = self.player_detail_updated_at(row, form, injuries, insights)

        return {
            "id": str(row.player_id),
            "code": row.player_code,
            "source_player_id": source_player_id,
            "name": display_text(row.name_zh, row.name_en),
            "name_en": display_text(row.name_en),
            "team": {
                "id": team_public_id(row.team_code, row.team_name_en),
                "code": row.team_code,
                "abbr": row.team_code,
                "name": display_text(row.team_name_zh, row.team_name_en or row.team_code),
                "name_en": display_text(row.team_name_en, row.team_code),
                "confederation": row.team_confederation,
                "fifa_rank": row.team_fifa_rank,
                "elo_rating": safe_float(row.team_elo_rating),
                "market_value_eur": safe_float(row.team_market_value_eur),
                "quality_status": row.team_quality_status,
            },
            "position": row.position,
            "shirt_number": row.shirt_number,
            "birth_date": row.birth_date.isoformat() if row.birth_date else None,
            "club": row.club_name,
            "market_value_eur": safe_float(row.market_value_eur),
            "is_key_player": row.is_key_player,
            "profile_url": DONGQIUDI_PLAYER_PAGE_URL.format(person_id=source_player_id)
            if source_player_id
            else None,
            "avatar_url": dongqiudi_player_avatar_url(source_player_id),
            "form": self.player_detail_form_score(row, form),
            "recent_form": self.player_recent_form_payload(form),
            "injuries": self.player_injury_payloads(injuries),
            "insights": self.player_insight_payloads(insights),
            "quality_status": row.player_quality_status,
            "data_sources": {
                "player": "players",
                "player_form": "player_form_snapshots" if form else None,
                "injuries": "injury_reports" if injuries else None,
                "insights": "ai_insights" if insights else None,
            },
            "updated_at": updated_at.isoformat() if updated_at else None,
        }

    def player_detail_form_score(self, row, form) -> float | None:
        if form is None:
            return None
        return self.player_display_form_score_from_values(
            form.form_score,
            form.rating,
            form.recent_matches,
            form.goals,
            form.assists,
            row.market_value_eur,
            form.availability_status,
        )

    @staticmethod
    def player_recent_form_payload(form) -> dict | None:
        if form is None:
            return None
        return {
            "matches": form.recent_matches,
            "minutes": form.minutes,
            "goals": form.goals,
            "assists": form.assists,
            "shots": form.shots,
            "key_passes": form.key_passes,
            "rating": safe_float(form.rating),
            "form_score": safe_float(form.form_score),
            "availability": form.availability_status,
            "source_count": form.source_count,
            "as_of_at": form.as_of_at.isoformat() if form.as_of_at else None,
        }

    @staticmethod
    def player_injury_payloads(rows: list) -> list[dict]:
        return [
            {
                "id": str(row.id),
                "report_type": row.report_type,
                "status": row.status,
                "impact_score": safe_float(row.impact_score),
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "expected_return_at": row.expected_return_at.isoformat() if row.expected_return_at else None,
                "source_url": row.source_url,
                "confidence": safe_float(row.confidence),
                "evidence_text": row.evidence_text,
                "is_model_eligible": row.is_model_eligible,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in rows
        ]

    @staticmethod
    def player_insight_payloads(rows: list) -> list[dict]:
        return [
            {
                "id": str(row.id),
                "event_type": row.event_type,
                "impact_area": row.impact_area,
                "impact_score": safe_float(row.impact_score),
                "confidence": safe_float(row.confidence),
                "evidence_text": row.evidence_text,
                "source_url": row.source_url,
                "is_model_eligible": row.is_model_eligible,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

    @staticmethod
    def player_detail_updated_at(row, form, injuries: list, insights: list) -> datetime | None:
        candidates = [row.player_updated_at]
        if form and form.as_of_at:
            candidates.append(form.as_of_at)
        candidates.extend(item.updated_at for item in injuries if item.updated_at)
        candidates.extend(item.created_at for item in insights if item.created_at)
        values = [item for item in candidates if item is not None]
        return max(values) if values else None

    def get_team_profile(self, team_id: str) -> dict | None:
        team_row = self.get_team_row(team_id)
        if team_row is None:
            return None

        player_rows = self.latest_team_player_forms(team_row.id)
        key_players = self.key_player_payloads(player_rows)
        form_stats = self.team_form_stats(player_rows)
        team_form = self.latest_team_form_snapshot(team_row.id)
        group_profile = self.team_group_profile(team_row.id)
        result_summary = self.team_result_summary(team_row.id, team_form)
        coach_profile = self.team_coach_profile(team_row.id)
        related_matches = self.team_related_matches(team_row.id, team_id)
        champion_ranking = self.latest_team_ranking_entry(team_row.id, "champion")
        semifinal_ranking = self.latest_team_ranking_entry(team_row.id, "semifinal")
        team_news = self.list_team_news(team_row.id, team_row)

        return {
            "team": team_payload(team_row),
            "summary": self.team_profile_summary(team_row, form_stats, result_summary, group_profile),
            "group": group_profile,
            "probabilities": [
                {
                    "label": "冠军概率",
                    "value": champion_ranking["probability"] if champion_ranking else None,
                    "delta": champion_ranking["delta"] if champion_ranking else None,
                    "source": "ranking_predictions",
                },
                {
                    "label": "四强概率",
                    "value": semifinal_ranking["probability"] if semifinal_ranking else None,
                    "delta": semifinal_ranking["delta"] if semifinal_ranking else None,
                    "source": "ranking_predictions",
                },
                {
                    "label": "小组第一",
                    "value": group_profile.get("rank_1_prob") if group_profile else None,
                    "source": "group_simulations",
                },
            ],
            "ratings": self.team_profile_ratings(team_row, form_stats, team_form, result_summary),
            "form": {
                "headline": result_summary["headline"],
                "recent": result_summary["recent"],
                "evidence": result_summary["evidence"],
                "stats": [
                    {"label": "入选球员", "value": form_stats["player_count"]},
                    {"label": "近况进球", "value": form_stats["goals"]},
                    {"label": "近况助攻", "value": form_stats["assists"]},
                    {"label": "Top5身价占比", "value": form_stats["top5_market_share"]},
                ],
            },
            "key_players": key_players,
            "coach": coach_profile,
            "related_matches": related_matches,
            "news": team_news,
            "risks": self.team_profile_risks(player_rows, form_stats, team_form),
            "data_sources": {
                "team": "teams",
                "players": "players",
                "player_form": "player_form_snapshots",
                "team_form": "team_form_snapshots",
                "team_results": "team_match_results",
                "group": "group_standings/group_simulations",
                "coach": "coaches",
                "related_matches": "matches",
                "probabilities": "ranking_predictions",
                "news": "news_items",
            },
        }

    def team_group_profile(self, team_uuid) -> dict | None:
        row = self.db.execute(self.team_group_profile_query(team_uuid)).mappings().first()
        if row is None:
            return None
        simulation = self.db.execute(
            self.latest_team_group_simulation_query(team_uuid, row.stage_uuid)
        ).mappings().first()
        payload = {
            "id": row.group_id,
            "name": group_display_name(row.group_id, row.group_name),
            "rank": row.rank,
            "record": f"{row.wins}-{row.draws}-{row.losses}",
            "points": row.points,
            "goals": f"{row.goals_for}:{row.goals_against}",
            "played": row.played,
            "wins": row.wins,
            "draws": row.draws,
            "losses": row.losses,
        }
        if simulation:
            payload.update(
                {
                    "rank_1_prob": safe_float(simulation.rank_1_prob),
                    "rank_2_prob": safe_float(simulation.rank_2_prob),
                    "qualify_prob": safe_float(simulation.qualify_prob),
                    "expected_points": safe_float(simulation.expected_points),
                }
            )
        return payload

    def latest_team_form_snapshot(self, team_uuid):
        return self.db.execute(self.latest_team_form_query(team_uuid)).mappings().first()

    def team_result_summary(self, team_uuid, team_form=None) -> dict:
        rows = self.db.execute(self.team_match_results_query(team_uuid)).mappings().all()
        if rows:
            wins = sum(1 for row in rows if row.result == "win")
            draws = sum(1 for row in rows if row.result == "draw")
            losses = sum(1 for row in rows if row.result == "loss")
            goals_for = sum(row.goals_for or 0 for row in rows)
            goals_against = sum(row.goals_against or 0 for row in rows)
            top30_rows = [
                row
                for row in rows
                if row.opponent_rank_bucket in ("top10", "top30")
                or (row.opponent_rank is not None and row.opponent_rank <= 30)
            ]
            top30_wins = sum(1 for row in top30_rows if row.result == "win")
            top30_draws = sum(1 for row in top30_rows if row.result == "draw")
            top30_losses = sum(1 for row in top30_rows if row.result == "loss")
            clean_sheets = sum(1 for row in rows if (row.goals_against or 0) == 0)
            matches_count = len(rows)
            avg_goals = goals_for / matches_count if matches_count else 0
            recent = {
                "matches": matches_count,
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "goals_for": goals_for,
                "goals_against": goals_against,
            }
            top30_count = len(top30_rows)
            top30_value = (
                f"样本{top30_count}场 · {top30_wins}胜 {top30_draws}平 {top30_losses}负"
                if top30_rows
                else "样本不足"
            )
            evidence = [
                {
                    "label": "对Top30",
                    "value": top30_value,
                    "tone": "positive" if top30_count >= 3 and top30_wins >= top30_losses else "neutral",
                    "source": "team_match_results",
                },
                {
                    "label": "零封率",
                    "value": f"{round(clean_sheets / matches_count * 100)}%",
                    "tone": "positive" if clean_sheets / matches_count >= 0.35 else "neutral",
                    "source": "team_match_results",
                },
                {
                    "label": "场均进球",
                    "value": f"{avg_goals:.1f}",
                    "tone": "positive" if avg_goals >= 1.8 else "neutral",
                    "source": "team_match_results",
                },
            ]
            return {
                "headline": f"近{matches_count}场 {wins}胜{draws}平{losses}负 · 进{goals_for}失{goals_against}",
                "recent": recent,
                "evidence": evidence,
                "points_per_match": round((wins * 3 + draws) / matches_count, 2),
                "goals_for_per_match": round(avg_goals, 2),
                "goals_against_per_match": round(goals_against / matches_count, 2),
            }

        recent_matches = int(team_form.recent_matches) if team_form and team_form.recent_matches is not None else 0
        goals_for = safe_float(team_form.goals_for_per_match) if team_form else None
        goals_against = safe_float(team_form.goals_against_per_match) if team_form else None
        headline = "球队近期战绩待同步"
        if recent_matches and goals_for is not None and goals_against is not None:
            headline = f"近{recent_matches}场 · 场均进{goals_for:.1f}失{goals_against:.1f}"
        return {
            "headline": headline,
            "recent": {
                "matches": recent_matches,
                "wins": None,
                "draws": None,
                "losses": None,
                "goals_for": None,
                "goals_against": None,
            },
            "evidence": [
                {"label": "对Top30", "value": "待同步", "tone": "neutral", "source": "team_match_results"},
                {
                    "label": "场均进球",
                    "value": f"{goals_for:.1f}" if goals_for is not None else "待同步",
                    "tone": "neutral",
                    "source": "team_form_snapshots",
                },
                {
                    "label": "场均失球",
                    "value": f"{goals_against:.1f}" if goals_against is not None else "待同步",
                    "tone": "neutral",
                    "source": "team_form_snapshots",
                },
            ],
            "points_per_match": safe_float(team_form.points_per_match) if team_form else None,
            "goals_for_per_match": goals_for,
            "goals_against_per_match": goals_against,
        }

    def team_coach_profile(self, team_uuid) -> dict | None:
        row = self.db.execute(self.coach_query(team_uuid)).mappings().first()
        if row is None:
            return None
        record_parts = []
        if row.matches_count is not None:
            record_parts.append(f"{row.matches_count}场")
        if row.wins is not None and row.draws is not None and row.losses is not None:
            record_parts.append(f"{row.wins}胜{row.draws}平{row.losses}负")
        return {
            "name": display_text(row.name_zh, row.name_en),
            "name_en": display_text(row.name_en),
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "record": " · ".join(record_parts) if record_parts else "战绩待同步",
            "win_rate": safe_float(row.win_rate),
            "quality_status": row.quality_status,
            "source_confidence": safe_float(row.source_confidence),
        }

    def team_related_matches(self, team_uuid, team_id: str) -> list[dict]:
        rows = self.db.execute(self.team_matches_query(team_uuid)).mappings().all()
        values = [match_payload(row) for row in rows]
        unique_values: dict[str, dict] = {}
        for value in values:
            if value["home_team"]["id"] == team_id:
                value["opponent_team"] = value["away_team"]
            else:
                value["opponent_team"] = value["home_team"]
            prediction = self.get_match_prediction(value["id"])
            value["prediction_summary"] = self.prediction_summary(prediction) if prediction else None
            opponent_id = value["opponent_team"]["id"]
            current = unique_values.get(opponent_id)
            if current is None or self.related_match_quality(value) > self.related_match_quality(current):
                unique_values[opponent_id] = value
        return sorted(
            unique_values.values(),
            key=lambda item: (item["status"] != "live", item["status"] != "scheduled", item["kickoff_at"]),
        )[:4]

    @staticmethod
    def related_match_quality(match: dict) -> int:
        score = 0
        if match.get("venue"):
            score += 2
        if match.get("stage") and match["stage"] != "Dongqiudi Schedule Context":
            score += 2
        if match.get("prediction_summary"):
            score += 1
        return score

    def latest_team_player_forms(self, team_uuid) -> list:
        rows = self.db.execute(
            select(
                players.c.id.label("player_id"),
                players.c.code.label("player_code"),
                players.c.name_zh,
                players.c.name_en,
                players.c.position,
                players.c.club_name,
                players.c.market_value_eur,
                players.c.is_key_player,
                players.c.quality_status.label("player_quality_status"),
                player_form_snapshots.c.as_of_at,
                player_form_snapshots.c.recent_matches,
                player_form_snapshots.c.minutes,
                player_form_snapshots.c.goals,
                player_form_snapshots.c.assists,
                player_form_snapshots.c.shots,
                player_form_snapshots.c.key_passes,
                player_form_snapshots.c.rating,
                player_form_snapshots.c.availability_status,
                player_form_snapshots.c.form_score,
                player_form_snapshots.c.source_count,
            )
            .select_from(players.outerjoin(player_form_snapshots, players.c.id == player_form_snapshots.c.player_id))
            .where(players.c.team_id == team_uuid)
            .order_by(
                players.c.is_key_player.desc(),
                player_form_snapshots.c.as_of_at.desc().nulls_last(),
                player_form_snapshots.c.form_score.desc().nulls_last(),
                players.c.name_zh.asc(),
            )
            .limit(40)
        ).mappings().all()

        latest_by_player = {}
        for row in rows:
            if row.player_id not in latest_by_player:
                latest_by_player[row.player_id] = row
        return list(latest_by_player.values())

    def key_player_payloads(self, player_rows: list) -> list[dict]:
        payloads = []
        for row in player_rows[:5]:
            source_player_id = source_player_id_from_code(row.player_code)
            payloads.append(
                {
                    "id": str(row.player_id),
                    "source_player_id": source_player_id,
                    "name": display_text(row.name_zh, row.name_en),
                    "name_en": display_text(row.name_en),
                    "role": row.position,
                    "form": self.player_display_form_score(row),
                    "position": row.position,
                    "club": row.club_name,
                    "market_value_eur": float(row.market_value_eur) if row.market_value_eur is not None else None,
                    "profile_url": DONGQIUDI_PLAYER_PAGE_URL.format(person_id=source_player_id)
                    if source_player_id
                    else None,
                    "avatar_url": dongqiudi_player_avatar_url(source_player_id),
                    "recent_form": {
                        "matches": row.recent_matches,
                        "minutes": row.minutes,
                        "goals": row.goals,
                        "assists": row.assists,
                        "shots": row.shots,
                        "key_passes": row.key_passes,
                        "rating": float(row.rating) if row.rating is not None else None,
                        "form_score": float(row.form_score) if row.form_score is not None else None,
                        "availability": row.availability_status,
                        "as_of_at": row.as_of_at.isoformat() if row.as_of_at else None,
                    },
                    "quality_status": row.player_quality_status,
                }
            )
        return payloads

    @staticmethod
    def player_display_form_score(row) -> float:
        return PublicDataRepository.player_display_form_score_from_values(
            row.form_score,
            row.rating,
            row.recent_matches,
            row.goals,
            row.assists,
            row.market_value_eur,
            row.availability_status,
        )

    @staticmethod
    def player_display_form_score_from_values(
        form_score,
        rating,
        recent_matches,
        goals,
        assists,
        market_value_eur,
        availability_status,
    ) -> float:
        if form_score is not None:
            return clamp_score(float(form_score), 0.0, 10.0)
        if rating is not None:
            return clamp_score(float(rating), 0.0, 10.0)
        recent_matches = recent_matches or 0
        goals = goals or 0
        assists = assists or 0
        market_value = float(market_value_eur or 0)
        score = 5.6
        score += min(recent_matches, 20) * 0.04
        score += min(goals, 12) * 0.16
        score += min(assists, 10) * 0.12
        score += min(market_value, 100_000_000) / 100_000_000 * 0.8
        if availability_status and availability_status != "available":
            score -= 1.2
        return clamp_score(score, 4.8, 9.4)

    @staticmethod
    def team_form_stats(player_rows: list) -> dict:
        goals = sum(row.goals or 0 for row in player_rows)
        assists = sum(row.assists or 0 for row in player_rows)
        ratings = [float(row.rating) for row in player_rows if row.rating is not None]
        scores = [float(row.form_score) for row in player_rows if row.form_score is not None]
        market_values = sorted(
            [float(row.market_value_eur) for row in player_rows if row.market_value_eur is not None],
            reverse=True,
        )
        total_market_value = sum(market_values)
        top5_market_share = (
            round(sum(market_values[:5]) / total_market_value * 100, 1) if total_market_value > 0 else None
        )
        return {
            "player_count": len(player_rows),
            "goals": goals,
            "assists": assists,
            "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "avg_form_score": round(sum(scores) / len(scores), 2) if scores else None,
            "total_market_value": total_market_value or None,
            "top5_market_share": f"{top5_market_share}%" if top5_market_share is not None else None,
        }

    def latest_team_ranking_entry(self, team_uuid, ranking_type: str) -> dict | None:
        latest_snapshot = (
            select(prediction_snapshots.c.id.label("snapshot_id"))
            .join(ranking_predictions, ranking_predictions.c.prediction_snapshot_id == prediction_snapshots.c.id)
            .where(ranking_predictions.c.ranking_type == ranking_type)
            .order_by(desc(prediction_snapshots.c.generated_at))
            .limit(1)
            .subquery()
        )
        row = self.db.execute(
            select(ranking_predictions.c.probability, ranking_predictions.c.delta)
            .join(latest_snapshot, ranking_predictions.c.prediction_snapshot_id == latest_snapshot.c.snapshot_id)
            .where(and_(ranking_predictions.c.team_id == team_uuid, ranking_predictions.c.ranking_type == ranking_type))
            .limit(1)
        ).first()
        if not row:
            return None
        return {
            "probability": float(row.probability),
            "delta": float(row.delta) if row.delta is not None else None,
        }

    def latest_team_ranking_probability(self, team_uuid, ranking_type: str) -> float | None:
        entry = self.latest_team_ranking_entry(team_uuid, ranking_type)
        return entry["probability"] if entry else None

    @staticmethod
    def team_profile_summary(team_row, form_stats: dict, result_summary: dict, group_profile: dict | None) -> str:
        team_name = display_text(team_row.name_zh, team_row.name_en or team_row.code)
        quality = team_row.quality_status or "unknown"
        rank_text = f"FIFA排名第 {team_row.fifa_rank}" if team_row.fifa_rank else "FIFA排名待同步"
        group_text = f"，当前位于{group_profile['name']}第 {group_profile['rank']}" if group_profile else ""
        if form_stats["player_count"] == 0:
            return f"{team_name} {rank_text}{group_text}；基础数据质量为 {quality}，球员近期状态仍待采集。"
        return (
            f"{team_name} {rank_text}{group_text}；{result_summary['headline']}。"
            f"当前覆盖 {form_stats['player_count']} 名球员，关键判断关注进攻效率、对强队表现和阵容稳定性。"
        )

    @staticmethod
    def team_profile_ratings(team_row, form_stats: dict, team_form=None, result_summary: dict | None = None) -> list[dict]:
        elo = float(team_row.elo_rating) if team_row.elo_rating is not None else None
        rank = team_row.fifa_rank
        form_score = form_stats["avg_form_score"]
        goals_for_per_match = result_summary.get("goals_for_per_match") if result_summary else None
        goals_against_per_match = result_summary.get("goals_against_per_match") if result_summary else None
        ratings = []
        if goals_for_per_match is not None or form_stats["goals"] or form_stats["assists"]:
            attack_base = 5.8 + form_stats["goals"] * 0.08 + form_stats["assists"] * 0.05
            if goals_for_per_match is not None:
                attack_base = max(attack_base, 5.7 + goals_for_per_match * 1.25)
            ratings.append(
                {
                    "label": "进攻",
                    "value": clamp_score(attack_base),
                    "source": "player_form_snapshots/team_match_results",
                }
            )
        if rank is not None or goals_against_per_match is not None:
            defense_base = 7.0 if rank is None else 8.9 - rank / 35
            if goals_against_per_match is not None:
                defense_base = max(5.2, defense_base - goals_against_per_match * 0.35)
            ratings.append({"label": "防守", "value": clamp_score(defense_base), "source": "teams/team_match_results"})
        market_value = float(team_row.market_value_eur or form_stats["total_market_value"] or 0)
        player_depth = min(form_stats["player_count"], 26) / 26 if form_stats["player_count"] else 0
        market_depth = min(market_value, 1_500_000_000) / 1_500_000_000 if market_value else 0
        if form_stats["player_count"] or market_value or rank is not None or elo is not None:
            depth = 5.4 + player_depth * 1.4 + market_depth * 2.3
            if rank is not None:
                depth = max(depth, max(5.5, min(9.3, 9.2 - rank / 30)))
            if elo is not None:
                depth = max(depth, max(5.5, min(9.4, (elo - 1400) / 120 + 5.8)))
            ratings.append({"label": "阵容深度", "value": clamp_score(depth), "source": "players/teams"})
        stability = None
        stability_source = None
        if team_form and team_form.lineup_stability_score is not None:
            stability = float(team_form.lineup_stability_score)
            stability_source = "team_form_snapshots"
        elif result_summary and result_summary.get("points_per_match") is not None:
            stability = 5.6 + min(float(result_summary["points_per_match"]), 3.0)
            stability_source = "team_match_results"
        elif form_score is not None:
            stability = form_score
            stability_source = "player_form_snapshots"
        if stability is not None:
            ratings.append({"label": "稳定性", "value": clamp_score(stability), "source": stability_source})
        return ratings

    @staticmethod
    def team_form_headline(player_rows: list, form_stats: dict) -> str:
        if not player_rows:
            return "球员近期状态数据待采集"
        return f"{form_stats['player_count']} 名球员近期合计 {form_stats['goals']} 球 {form_stats['assists']} 助攻"

    @staticmethod
    def team_profile_risks(player_rows: list, form_stats: dict, team_form=None) -> list[dict]:
        risks = []
        unavailable = [row for row in player_rows if row.availability_status and row.availability_status != "available"]
        if unavailable:
            risks.append({"label": "出勤风险", "value": len(unavailable), "source": "player_form_snapshots"})
        if team_form and team_form.injury_impact_score is not None and float(team_form.injury_impact_score) > 0:
            risks.append(
                {
                    "label": "伤停影响",
                    "value": round(float(team_form.injury_impact_score), 1),
                    "source": "team_form_snapshots",
                }
            )
        if form_stats["player_count"] < 5:
            risks.append({"label": "球员样本不足", "value": 5 - form_stats["player_count"], "source": "players"})
        return risks

    @staticmethod
    def prediction_summary(prediction: dict | None) -> dict | None:
        if prediction is None:
            return None
        probabilities = prediction["probabilities"]
        home = probabilities["home_win"]
        draw = probabilities["draw"]
        away = probabilities["away_win"]
        if draw >= home and draw >= away:
            tendency = "draw"
        elif home > away:
            tendency = "home"
        else:
            tendency = "away"
        return {
            "tendency": tendency,
            "home_win_prob": home,
            "draw_prob": draw,
            "away_win_prob": away,
            "confidence": prediction["confidence"],
        }

    def get_home_data(self, date: str | None, timezone: str) -> dict | None:
        min_kickoff_at = None
        if date is None:
            min_kickoff_at = datetime.now(ZoneInfo(timezone)).astimezone(utc_timezone.utc)
        matches_value = self.list_matches(
            limit=10,
            include_prediction=True,
            real_only=self.has_real_matches(),
            match_date=date,
            timezone=timezone,
            min_kickoff_at=min_kickoff_at,
        )
        if not matches_value:
            return None
        featured_match = matches_value[0]
        prediction_summary = featured_match.pop("prediction_summary", None)
        featured_match["prediction"] = prediction_summary
        return {
            "featured_match": featured_match,
            "upcoming_matches": matches_value[1:],
            "champion_rankings": self.list_rankings("champion", 3),
            "date": date,
            "timezone": timezone,
        }

    def list_groups(self) -> list[dict]:
        rows = self.db.execute(self.groups_query()).mappings().all()
        return [
            {
                "id": row.code,
                "name": group_display_name(row.code, row.name),
                "matches_finished": int(row.matches_finished),
                "matches_total": int(row.matches_total),
                "summary": "Data generated from competition stage and match tables.",
            }
            for row in rows
        ]

    def get_group_detail(self, group_id: str) -> dict | None:
        rows = self.db.execute(self.group_standings_query(group_id)).mappings().all()
        if not rows:
            return None
        first = rows[0]
        return {
            "id": first.group_id,
            "name": group_display_name(first.group_id, first.group_name),
            "standings": [
                {
                    "rank": row.rank,
                    "team": team_payload(row),
                    "record": f"{row.wins}-{row.draws}-{row.losses}",
                    "points": row.points,
                    "goals": f"{row.goals_for}:{row.goals_against}",
                }
                for row in rows
            ],
        }

    def get_group_simulation(self, group_id: str) -> dict | None:
        rows = self.db.execute(self.group_simulation_query(group_id)).mappings().all()
        if not rows:
            return None
        return {
            "group_id": group_id,
            "simulation_count": 50000,
            "teams": [
                {
                    "team": team_payload(row),
                    "qualify_prob": float(row.qualify_prob),
                    "rank_1_prob": float(row.rank_1_prob),
                    "rank_2_prob": float(row.rank_2_prob),
                    "expected_points": float(row.expected_points),
                }
                for row in rows
            ],
        }

    def list_team_matches(self, team_id: str) -> list[dict] | None:
        team = self.get_team(team_id)
        if team is None:
            return None
        return [
            match
            for match in self.list_matches()
            if match["home_team"]["id"] == team_id or match["away_team"]["id"] == team_id
        ]
