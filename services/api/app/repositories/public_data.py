from sqlalchemy import Select, and_, desc, select
from sqlalchemy.orm import Session

from app.db.schema import (
    match_predictions,
    matches,
    prediction_snapshots,
    ranking_predictions,
    scoreline_predictions,
    teams,
    venues,
)


def team_payload(row) -> dict:
    return {
        "id": row.code.lower(),
        "code": row.code,
        "abbr": row.code,
        "name": row.name_zh,
        "name_en": row.name_en,
        "confederation": row.confederation,
        "fifa_rank": row.fifa_rank,
        "elo_rating": float(row.elo_rating) if row.elo_rating is not None else None,
        "market_value_eur": float(row.market_value_eur) if row.market_value_eur is not None else None,
        "quality_status": row.quality_status,
    }


class PublicDataRepository:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def teams_query() -> Select:
        return select(teams).order_by(teams.c.fifa_rank.asc().nulls_last(), teams.c.code.asc())

    @staticmethod
    def match_query(public_id: str) -> Select:
        home = teams.alias("home_team")
        away = teams.alias("away_team")
        return (
            select(
                matches.c.public_id,
                matches.c.kickoff_at,
                matches.c.status,
                matches.c.home_score,
                matches.c.away_score,
                matches.c.neutral_site,
                matches.c.source_confidence,
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
            .join(home, matches.c.home_team_id == home.c.id)
            .join(away, matches.c.away_team_id == away.c.id)
            .outerjoin(venues, matches.c.venue_id == venues.c.id)
            .where(matches.c.public_id == public_id)
        )

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
            .order_by(scoreline_predictions.c.rank.asc())
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
            .order_by(ranking_predictions.c.rank.asc())
            .limit(limit)
        )

    def list_teams(self) -> list[dict]:
        rows = self.db.execute(self.teams_query()).mappings().all()
        return [team_payload(row) for row in rows]

    def get_match(self, public_id: str) -> dict | None:
        row = self.db.execute(self.match_query(public_id)).mappings().first()
        if row is None:
            return None
        return {
            "id": row.public_id,
            "status": row.status,
            "kickoff_at": row.kickoff_at.isoformat(),
            "home_score": row.home_score,
            "away_score": row.away_score,
            "neutral_site": row.neutral_site,
            "source_confidence": float(row.source_confidence),
            "home_team": {
                "id": row.home_code.lower(),
                "abbr": row.home_code,
                "name": row.home_name,
                "name_en": row.home_name_en,
                "fifa_rank": row.home_fifa_rank,
                "elo_rating": float(row.home_elo_rating) if row.home_elo_rating is not None else None,
            },
            "away_team": {
                "id": row.away_code.lower(),
                "abbr": row.away_code,
                "name": row.away_name,
                "name_en": row.away_name_en,
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
            "expected_goals": {
                "home": float(prediction.home_expected_goals),
                "away": float(prediction.away_expected_goals),
            },
            "confidence": prediction.confidence,
            "key_factors": prediction.key_factors,
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
