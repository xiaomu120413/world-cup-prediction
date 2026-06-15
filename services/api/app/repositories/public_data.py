from sqlalchemy import Select, and_, case, desc, func, select
from sqlalchemy.orm import Session

from app.db.schema import (
    competition_stages,
    group_simulations,
    group_standings,
    match_predictions,
    matches,
    prediction_snapshots,
    ranking_predictions,
    scoreline_predictions,
    teams,
    venues,
)

TEAM_PUBLIC_IDS = {
    "USA": "usa",
    "PAR": "paraguay",
    "FRA": "france",
    "BRA": "brazil",
    "ENG": "england",
}


def team_public_id(code: str, name_en: str | None = None) -> str:
    if code in TEAM_PUBLIC_IDS:
        return TEAM_PUBLIC_IDS[code]
    if name_en:
        return name_en.lower().replace(" ", "-")
    return code.lower()


def team_payload(row) -> dict:
    return {
        "id": team_public_id(row.code, row.name_en),
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
            "name": row.home_name,
            "name_en": row.home_name_en,
            "fifa_rank": row.home_fifa_rank,
            "elo_rating": float(row.home_elo_rating) if row.home_elo_rating is not None else None,
        },
        "away_team": {
            "id": team_public_id(row.away_code, row.away_name_en),
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


class PublicDataRepository:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def teams_query() -> Select:
        return select(teams).order_by(teams.c.fifa_rank.asc().nulls_last(), teams.c.code.asc())

    @staticmethod
    def match_query(public_id: str) -> Select:
        return PublicDataRepository.matches_query().where(matches.c.public_id == public_id)

    @staticmethod
    def matches_query(limit: int | None = None) -> Select:
        home = teams.alias("home_team")
        away = teams.alias("away_team")
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
            .order_by(matches.c.kickoff_at.asc(), matches.c.public_id.asc())
        )
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

    @staticmethod
    def groups_query() -> Select:
        return (
            select(
                competition_stages.c.code,
                competition_stages.c.name,
                func.count(matches.c.id).label("matches_total"),
                func.coalesce(
                    func.sum(case((matches.c.status == "finished", 1), else_=0)),
                    0,
                ).label("matches_finished"),
            )
            .outerjoin(matches, matches.c.stage_id == competition_stages.c.id)
            .where(competition_stages.c.stage_type == "group")
            .group_by(competition_stages.c.id, competition_stages.c.code, competition_stages.c.name)
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

    def get_team(self, team_id: str) -> dict | None:
        return next((team for team in self.list_teams() if team["id"] == team_id), None)

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

    def list_matches(self, limit: int | None = None, include_prediction: bool = False) -> list[dict]:
        rows = self.db.execute(self.matches_query(limit)).mappings().all()
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
        return match_payload(row)

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

    @staticmethod
    def prediction_summary(prediction: dict | None) -> dict | None:
        if prediction is None:
            return None
        probabilities = prediction["probabilities"]
        home = probabilities["home_win"]
        away = probabilities["away_win"]
        if home > away:
            tendency = "home"
        elif away > home:
            tendency = "away"
        else:
            tendency = "draw"
        return {
            "tendency": tendency,
            "home_win_prob": home,
            "draw_prob": probabilities["draw"],
            "away_win_prob": away,
            "confidence": prediction["confidence"],
        }

    def get_home_data(self, date: str | None, timezone: str) -> dict | None:
        matches_value = self.list_matches(limit=10, include_prediction=True)
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
                "name": row.name,
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
            "name": first.group_name,
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
