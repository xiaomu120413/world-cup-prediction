from sqlalchemy import Select, and_, case, desc, func, select
from sqlalchemy.orm import Session

from app.collectors.catalog import collection_catalog_summary
from app.db.schema import (
    competition_stages,
    collector_runs,
    group_simulations,
    group_standings,
    match_predictions,
    matches,
    news_items,
    player_form_snapshots,
    players,
    prediction_snapshots,
    ranking_predictions,
    raw_snapshots,
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
    def matches_query(limit: int | None = None, real_only: bool = False) -> Select:
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
            .order_by(real_source_rank.asc(), status_rank.asc(), matches.c.kickoff_at.desc(), matches.c.public_id.asc())
        )
        if real_only:
            query = query.where(matches.c.public_id.like("dongqiudi-%"))
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
            "thestatsapi_matches": self.count_thestatsapi_matches(),
            "venues": self.count_rows(venues),
            "players": self.count_rows(players),
            "player_form_snapshots": self.count_rows(player_form_snapshots),
            "group_standings": self.count_rows(group_standings),
            "raw_snapshots": self.count_rows(raw_snapshots),
            "dongqiudi_standings_snapshots": self.count_raw_snapshots("dongqiudi", "world_cup_standings"),
            "dongqiudi_player_ranking_snapshots": self.count_raw_snapshots("dongqiudi", "world_cup_player_rankings"),
            "collector_runs": self.count_rows(collector_runs),
            "news_items": self.count_rows(news_items),
            "match_predictions": self.count_rows(match_predictions),
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

    def count_real_matches(self) -> int:
        return int(
            self.db.execute(
                select(func.count()).select_from(matches).where(matches.c.public_id.like("dongqiudi-%"))
            ).scalar_one()
        )

    def count_thestatsapi_matches(self) -> int:
        return int(
            self.db.execute(
                select(func.count()).select_from(matches).where(matches.c.public_id.like("thestatsapi-%"))
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
    ) -> list[dict]:
        rows = self.db.execute(self.matches_query(limit, real_only=real_only)).mappings().all()
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

    def get_team_profile(self, team_id: str) -> dict | None:
        team_row = self.get_team_row(team_id)
        if team_row is None:
            return None

        player_rows = self.latest_team_player_forms(team_row.id)
        key_players = self.key_player_payloads(player_rows)
        form_stats = self.team_form_stats(player_rows)
        champion_probability = self.latest_team_ranking_probability(team_row.id, "champion")
        semifinal_probability = self.latest_team_ranking_probability(team_row.id, "semifinal")

        return {
            "team": team_payload(team_row),
            "summary": self.team_profile_summary(team_row, form_stats),
            "probabilities": [
                {
                    "label": "冠军概率",
                    "value": champion_probability,
                    "source": "ranking_predictions",
                },
                {
                    "label": "四强概率",
                    "value": semifinal_probability,
                    "source": "ranking_predictions",
                },
            ],
            "ratings": self.team_profile_ratings(team_row, form_stats),
            "form": {
                "headline": self.team_form_headline(player_rows, form_stats),
                "stats": [
                    {"label": "入选球员", "value": form_stats["player_count"]},
                    {"label": "近况进球", "value": form_stats["goals"]},
                    {"label": "近况助攻", "value": form_stats["assists"]},
                    {"label": "平均评分", "value": form_stats["avg_rating"]},
                ],
            },
            "key_players": key_players,
            "risks": self.team_profile_risks(player_rows, form_stats),
            "data_sources": {
                "team": "teams",
                "players": "players",
                "player_form": "player_form_snapshots",
                "probabilities": "ranking_predictions",
            },
        }

    def latest_team_player_forms(self, team_uuid) -> list:
        rows = self.db.execute(
            select(
                players.c.id.label("player_id"),
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
        return [
            {
                "id": str(row.player_id),
                "name": row.name_zh,
                "name_en": row.name_en,
                "role": row.position,
                "form": float(row.form_score or row.rating or 0),
                "position": row.position,
                "club": row.club_name,
                "market_value_eur": float(row.market_value_eur) if row.market_value_eur is not None else None,
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
            for row in player_rows[:5]
        ]

    @staticmethod
    def team_form_stats(player_rows: list) -> dict:
        goals = sum(row.goals or 0 for row in player_rows)
        assists = sum(row.assists or 0 for row in player_rows)
        ratings = [float(row.rating) for row in player_rows if row.rating is not None]
        scores = [float(row.form_score) for row in player_rows if row.form_score is not None]
        return {
            "player_count": len(player_rows),
            "goals": goals,
            "assists": assists,
            "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "avg_form_score": round(sum(scores) / len(scores), 2) if scores else None,
        }

    def latest_team_ranking_probability(self, team_uuid, ranking_type: str) -> float | None:
        latest_snapshot = (
            select(prediction_snapshots.c.id.label("snapshot_id"))
            .join(ranking_predictions, ranking_predictions.c.prediction_snapshot_id == prediction_snapshots.c.id)
            .where(ranking_predictions.c.ranking_type == ranking_type)
            .order_by(desc(prediction_snapshots.c.generated_at))
            .limit(1)
            .subquery()
        )
        row = self.db.execute(
            select(ranking_predictions.c.probability)
            .join(latest_snapshot, ranking_predictions.c.prediction_snapshot_id == latest_snapshot.c.snapshot_id)
            .where(and_(ranking_predictions.c.team_id == team_uuid, ranking_predictions.c.ranking_type == ranking_type))
            .limit(1)
        ).first()
        return float(row.probability) if row else None

    @staticmethod
    def team_profile_summary(team_row, form_stats: dict) -> str:
        quality = team_row.quality_status or "unknown"
        if form_stats["player_count"] == 0:
            return f"基于 teams 标准表生成，球队基础数据质量为 {quality}；球员近期状态仍待采集。"
        return (
            f"基于 teams、players 和 player_form_snapshots 标准表生成；"
            f"当前覆盖 {form_stats['player_count']} 名球员，近况合计 {form_stats['goals']} 球 {form_stats['assists']} 助攻。"
        )

    @staticmethod
    def team_profile_ratings(team_row, form_stats: dict) -> list[dict]:
        elo = float(team_row.elo_rating) if team_row.elo_rating is not None else None
        rank = team_row.fifa_rank or 80
        form_score = form_stats["avg_form_score"] or 6.2
        attack = min(9.5, 5.8 + form_stats["goals"] * 0.25 + form_stats["assists"] * 0.15)
        baseline = max(5.5, min(9.3, 9.2 - rank / 30))
        elo_score = max(5.5, min(9.4, ((elo or 1700) - 1400) / 120 + 5.8))
        return [
            {"label": "进攻", "value": round(attack, 1), "source": "player_form_snapshots"},
            {"label": "整体强度", "value": round((baseline + elo_score) / 2, 1), "source": "teams"},
            {"label": "近期状态", "value": round(max(5.0, min(9.5, form_score)), 1), "source": "player_form_snapshots"},
        ]

    @staticmethod
    def team_form_headline(player_rows: list, form_stats: dict) -> str:
        if not player_rows:
            return "球员近期状态数据待采集"
        return f"{form_stats['player_count']} 名球员近期合计 {form_stats['goals']} 球 {form_stats['assists']} 助攻"

    @staticmethod
    def team_profile_risks(player_rows: list, form_stats: dict) -> list[dict]:
        risks = []
        unavailable = [row for row in player_rows if row.availability_status and row.availability_status != "available"]
        if unavailable:
            risks.append({"label": "出勤风险", "value": len(unavailable), "source": "player_form_snapshots"})
        if form_stats["player_count"] < 5:
            risks.append({"label": "球员样本不足", "value": 5 - form_stats["player_count"], "source": "players"})
        if form_stats["avg_rating"] is None:
            risks.append({"label": "评分缺失", "value": 1, "source": "player_form_snapshots"})
        return risks

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
        matches_value = self.list_matches(limit=10, include_prediction=True, real_only=self.has_real_matches())
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
