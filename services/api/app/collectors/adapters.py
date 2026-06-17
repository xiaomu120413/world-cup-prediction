from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
import re
from typing import Protocol
from urllib.parse import urljoin

import httpx


@dataclass(frozen=True)
class RawSnapshot:
    source: str
    source_type: str
    source_url: str | None
    payload: dict
    parser_version: str = "raw_snapshot_v1"


class CollectorAdapter(Protocol):
    source: str
    source_type: str

    def fetch(self) -> RawSnapshot:
        ...


class TextExtractor(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.title = ""
        self.text_blocks: list[str] = []
        self.links: list[dict] = []
        self._current_link: str | None = None
        self._current_link_text: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag == "a" and attrs_dict.get("href"):
            self._current_link = urljoin(self.base_url, attrs_dict["href"] or "")
            self._current_link_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag == "a" and self._current_link:
            text = " ".join(" ".join(self._current_link_text).split())
            if text:
                self.links.append({"text": text, "href": self._current_link})
            self._current_link = None
            self._current_link_text = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self.title = text
        if self._current_link:
            self._current_link_text.append(text)
        self.text_blocks.append(text)


class DongqiudiHomepageAdapter:
    source = "dongqiudi"
    source_url = "https://pc.dongqiudi.com/"
    parser_version = "dongqiudi_homepage_v1"
    football_competitions = {"世界杯"}

    def __init__(self, source_type: str = "homepage", timeout_seconds: float = 10.0):
        if source_type not in {"homepage", "schedule", "news", "league_data"}:
            raise ValueError(f"Unsupported dongqiudi source_type: {source_type}")
        self.source_type = source_type
        self.timeout_seconds = timeout_seconds

    def fetch(self) -> RawSnapshot:
        response = httpx.get(
            self.source_url,
            timeout=self.timeout_seconds,
            headers={
                "User-Agent": "world-cup-prediction-bot/0.1 (+low-frequency research collector)",
                "Accept": "text/html,application/xhtml+xml",
            },
            follow_redirects=True,
        )
        response.raise_for_status()
        return self.parse(response.text, str(response.url))

    def parse(self, html: str, source_url: str | None = None) -> RawSnapshot:
        extractor = TextExtractor(source_url or self.source_url)
        extractor.feed(html)
        text_blocks = extractor.text_blocks[:300]
        links = extractor.links[:120]
        payload = {
            "items": self.extract_items(text_blocks, links),
            "matches": self.extract_matches(text_blocks),
            "title": extractor.title,
            "source_url": source_url or self.source_url,
            "text_blocks": text_blocks,
            "links": links,
        }
        return RawSnapshot(
            source=self.source,
            source_type=self.source_type,
            source_url=source_url or self.source_url,
            payload=payload,
            parser_version=self.parser_version,
        )

    @staticmethod
    def extract_items(text_blocks: list[str], links: list[dict]) -> list[dict]:
        football_keywords = ("世界杯", "足球", "英超", "西甲", "德甲", "意甲", "中超")
        news_items = [
            {"type": "link", "title": item["text"], "href": item["href"]}
            for item in links
            if any(keyword in item["text"] for keyword in football_keywords)
        ]
        match_blocks = [
            {
                "type": "match_block",
                "competition": item["competition"],
                "home": item["home"],
                "time_or_score": item.get("score_text") or item.get("time_text"),
                "away": item["away"],
            }
            for item in DongqiudiHomepageAdapter.extract_matches(text_blocks)
        ]
        return [*match_blocks[:20], *news_items[:80]]

    @classmethod
    def extract_matches(cls, text_blocks: list[str]) -> list[dict]:
        match_date = cls.extract_match_date(text_blocks)
        values = []
        for index, text in enumerate(text_blocks):
            if text not in cls.football_competitions:
                continue
            parsed = cls.parse_match_at(text_blocks, index, match_date)
            if parsed:
                values.append(parsed)
        return values[:20]

    @staticmethod
    def extract_match_date(text_blocks: list[str]) -> str:
        current_year = datetime.now().year
        for text in text_blocks:
            match = re.search(r"(\d{1,2})月(\d{1,2})日", text)
            if match:
                return f"{current_year:04d}-{int(match.group(1)):02d}-{int(match.group(2)):02d}"
        now = datetime.now()
        return f"{current_year:04d}-{now.month:02d}-{now.day:02d}"

    @classmethod
    def parse_match_at(cls, text_blocks: list[str], index: int, match_date: str) -> dict | None:
        if index + 3 >= len(text_blocks):
            return None
        competition = text_blocks[index]
        cursor = index + 1
        status_token = None
        if cls.is_status_token(text_blocks[cursor]):
            status_token = text_blocks[cursor]
            cursor += 1
        if cursor + 2 >= len(text_blocks):
            return None

        home = text_blocks[cursor]
        center = text_blocks[cursor + 1]
        away = text_blocks[cursor + 2]
        if not cls.looks_like_team(home) or not cls.looks_like_team(away):
            return None
        if not (cls.is_score(center) or cls.is_time(center)):
            return None

        home_score = None
        away_score = None
        status = "scheduled"
        kickoff_time = center if cls.is_time(center) else "00:00"
        if cls.is_score(center):
            score_parts = [int(value) for value in re.findall(r"\d+", center)[:2]]
            if len(score_parts) == 2:
                home_score, away_score = score_parts
            status = "finished" if status_token == "FT" else "live"
        if status_token and re.fullmatch(r"\d+'", status_token):
            status = "live"

        return {
            "public_id": f"dongqiudi-{cls.slug(home)}-{cls.slug(away)}-{match_date}",
            "competition": competition,
            "competition_code": "world_cup_2026",
            "stage_code": "world-cup-homepage" if competition == "世界杯" else f"{cls.slug(competition)}-homepage",
            "stage_name": competition,
            "stage_type": "group",
            "home": home,
            "away": away,
            "kickoff_at": f"{match_date}T{kickoff_time}:00+08:00",
            "status": status,
            "home_score": home_score,
            "away_score": away_score,
            "neutral_site": True,
            "source_confidence": 0.7,
            "status_text": status_token,
            "score_text": center if cls.is_score(center) else None,
            "time_text": center if cls.is_time(center) else None,
        }

    @staticmethod
    def is_status_token(value: str) -> bool:
        return value in {"FT", "HT"} or bool(re.fullmatch(r"\d+'", value))

    @staticmethod
    def is_score(value: str) -> bool:
        return bool(re.fullmatch(r"\d+\s*-\s*\d+", value))

    @staticmethod
    def is_time(value: str) -> bool:
        return bool(re.fullmatch(r"\d{1,2}:\d{2}", value))

    @staticmethod
    def looks_like_team(value: str) -> bool:
        if not value or len(value) > 20:
            return False
        if re.search(r"\d{1,2}-\d{1,2}|\d{1,2}:\d{2}|评论|评|播放|：|，|。|·", value):
            return False
        return True

    @staticmethod
    def slug(value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip().lower()).strip("-")
        return slug or "team"


class DongqiudiWorldCupDataAdapter:
    source = "dongqiudi"
    competition_id = "61"
    season_id = "26123"
    parser_version = "dongqiudi_world_cup_data_v1"
    api_base_url = "https://sport-data.dongqiudi.com/soccer/biz/data"

    ranking_types = {
        "goals": "goals",
        "assists": "assists",
        "shots": "shots",
        "shots_on_target": "shots_on_target",
        "key_passes": "key_passes",
        "appearances": "appearances",
        "minutes": "time_played",
        "starts": "starts",
        "yellow_cards": "yellow_cards",
        "red_cards": "red_cards",
    }

    def __init__(self, source_type: str, timeout_seconds: float = 20.0):
        if source_type not in {"world_cup_standings", "world_cup_player_rankings"}:
            raise ValueError(f"Unsupported dongqiudi world cup source_type: {source_type}")
        self.source_type = source_type
        self.timeout_seconds = timeout_seconds

    def fetch(self) -> RawSnapshot:
        if self.source_type == "world_cup_standings":
            url = self.standings_url()
            response = self.get_json(url)
            payload = {
                "competition_id": self.competition_id,
                "season_id": self.season_id,
                "groups": self.extract_groups(response),
                "items": [],
            }
            return RawSnapshot(
                source=self.source,
                source_type=self.source_type,
                source_url=url,
                payload=payload,
                parser_version=self.parser_version,
            )

        ranking_payloads = {name: self.get_json(self.ranking_url(api_type)) for name, api_type in self.ranking_types.items()}
        market_values = self.extract_market_values(self.get_json(self.market_value_url()))
        payload = {
            "competition_id": self.competition_id,
            "season_id": self.season_id,
            "players": self.extract_players(ranking_payloads, market_values),
            "ranking_sources": {
                **{name: self.ranking_url(api_type) for name, api_type in self.ranking_types.items()},
                "market_values": self.market_value_url(),
            },
            "items": [],
        }
        return RawSnapshot(
            source=self.source,
            source_type=self.source_type,
            source_url=self.ranking_url("goals"),
            payload=payload,
            parser_version=self.parser_version,
        )

    def get_json(self, url: str) -> dict:
        response = httpx.get(
            url,
            timeout=self.timeout_seconds,
            headers={
                "User-Agent": "world-cup-prediction-bot/0.1 (+low-frequency research collector)",
                "Accept": "application/json",
                "Referer": "https://m.dongqiudi.com/stat/9/rankingGoal",
            },
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.json()

    def standings_url(self) -> str:
        return (
            f"{self.api_base_url}/standing?season_id={self.season_id}"
            "&app=dqd&version=830&platform=miniprogram&language=zh-cn&app_type="
        )

    def ranking_url(self, ranking_type: str) -> str:
        return (
            f"{self.api_base_url}/person_ranking?app=dqd&version=830&platform=miniprogram"
            f"&type={ranking_type}&season_id={self.season_id}"
        )

    def market_value_url(self) -> str:
        return f"{self.api_base_url}/market_value_ranking?&app=dqd&version=830&platform=miniprogram&language=zh-cn&app_type="

    @classmethod
    def extract_groups(cls, data: dict) -> list[dict]:
        values = []
        rounds = data.get("content", {}).get("rounds", [])
        for round_item in rounds:
            for group_item in round_item.get("content", {}).get("data", []):
                group_name = group_item.get("name") or ""
                group_code = cls.group_code(group_name)
                teams = []
                for row in group_item.get("data", []):
                    goals_for = cls.to_int(row.get("goals_pro"))
                    goals_against = cls.to_int(row.get("goals_against"))
                    teams.append(
                        {
                            "team": row.get("team_name"),
                            "source_team_id": row.get("team_id"),
                            "rank": cls.to_int(row.get("rank"), 99),
                            "played": cls.to_int(row.get("matches_total")),
                            "wins": cls.to_int(row.get("matches_won")),
                            "draws": cls.to_int(row.get("matches_draw")),
                            "losses": cls.to_int(row.get("matches_lost")),
                            "goals_for": goals_for,
                            "goals_against": goals_against,
                            "goal_diff": goals_for - goals_against,
                            "points": cls.to_int(row.get("points")),
                        }
                    )
                if teams:
                    values.append({"code": group_code, "name": group_name, "teams": teams})
        return values

    @classmethod
    def extract_players(cls, ranking_payloads: dict[str, dict], market_values: dict[str, int] | None = None) -> list[dict]:
        market_values = market_values or {}
        players: dict[str, dict] = {}
        for stat_name, payload in ranking_payloads.items():
            for row in payload.get("content", {}).get("data", []):
                person_id = row.get("person_id")
                if not person_id:
                    continue
                player = players.setdefault(
                    person_id,
                    {
                        "code": f"DQD-P{person_id}",
                        "source_player_id": person_id,
                        "name": row.get("person_name"),
                        "team": row.get("team_name") or row.get("row_1"),
                        "source_team_id": row.get("team_id"),
                        "market_value_eur": market_values.get(person_id),
                        "recent_matches": 1,
                        "source_count": 1,
                    },
                )
                if person_id in market_values:
                    player["market_value_eur"] = market_values[person_id]
                count = cls.to_int(row.get("count") or row.get("row_2"))
                if stat_name == "appearances":
                    player["recent_matches"] = count
                elif stat_name == "minutes":
                    player["minutes"] = count
                else:
                    player[stat_name] = count
                player["source_count"] = len(
                    [
                        key
                        for key in (
                            "goals",
                            "assists",
                            "shots",
                            "shots_on_target",
                            "key_passes",
                            "minutes",
                            "starts",
                            "yellow_cards",
                            "red_cards",
                        )
                        if player.get(key) is not None
                    ]
                )
        return list(players.values())

    @classmethod
    def extract_market_values(cls, data: dict) -> dict[str, int]:
        values = {}
        for row in data.get("content", {}).get("data", []):
            person_id = row.get("person_id")
            currency = row.get("currency")
            if not person_id or currency != "EUR":
                continue
            values[person_id] = cls.to_int(row.get("value"))
        return values

    @staticmethod
    def group_code(value: str) -> str:
        match = re.search(r"([A-ZＡ-ＺA-L])\s*组|([A-L])", value, re.IGNORECASE)
        if match:
            letter = (match.group(1) or match.group(2)).lower()
            return f"group-{letter}"
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
        return slug or "group-unknown"

    @staticmethod
    def to_int(value, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


class TheStatsApiFixturesAdapter:
    source = "thestatsapi"
    source_type = "fixtures"
    source_url = "https://www.thestatsapi.com/world-cup/data/fixtures.json"
    parser_version = "thestatsapi_fixtures_v1"

    HOST_CITIES = {
        "atlanta": {"city": "Atlanta", "country": "United States", "timezone": "America/New_York"},
        "boston": {"city": "Boston", "country": "United States", "timezone": "America/New_York"},
        "dallas": {"city": "Dallas", "country": "United States", "timezone": "America/Chicago"},
        "guadalajara": {"city": "Guadalajara", "country": "Mexico", "timezone": "America/Mexico_City"},
        "houston": {"city": "Houston", "country": "United States", "timezone": "America/Chicago"},
        "kansas-city": {"city": "Kansas City", "country": "United States", "timezone": "America/Chicago"},
        "los-angeles": {"city": "Los Angeles", "country": "United States", "timezone": "America/Los_Angeles"},
        "mexico-city": {"city": "Mexico City", "country": "Mexico", "timezone": "America/Mexico_City"},
        "miami": {"city": "Miami", "country": "United States", "timezone": "America/New_York"},
        "monterrey": {"city": "Monterrey", "country": "Mexico", "timezone": "America/Monterrey"},
        "new-york": {"city": "New York/New Jersey", "country": "United States", "timezone": "America/New_York"},
        "philadelphia": {"city": "Philadelphia", "country": "United States", "timezone": "America/New_York"},
        "san-francisco": {"city": "San Francisco Bay Area", "country": "United States", "timezone": "America/Los_Angeles"},
        "san-francisco-bay-area": {"city": "San Francisco Bay Area", "country": "United States", "timezone": "America/Los_Angeles"},
        "seattle": {"city": "Seattle", "country": "United States", "timezone": "America/Los_Angeles"},
        "toronto": {"city": "Toronto", "country": "Canada", "timezone": "America/Toronto"},
        "vancouver": {"city": "Vancouver", "country": "Canada", "timezone": "America/Vancouver"},
    }

    def __init__(self, source_type: str = "fixtures", timeout_seconds: float = 20.0):
        if source_type not in {"fixtures", "schedule"}:
            raise ValueError(f"Unsupported thestatsapi source_type: {source_type}")
        self.source_type = source_type
        self.timeout_seconds = timeout_seconds

    def fetch(self) -> RawSnapshot:
        response = httpx.get(
            self.source_url,
            timeout=self.timeout_seconds,
            headers={
                "User-Agent": "world-cup-prediction-bot/0.1 (+low-frequency research collector)",
                "Accept": "application/json",
            },
            follow_redirects=True,
        )
        response.raise_for_status()
        return self.parse(response.json(), str(response.url))

    def parse(self, data: dict, source_url: str | None = None) -> RawSnapshot:
        fixtures = data.get("fixtures", [])
        venues = {}
        matches = []
        for item in fixtures:
            venue = self.venue_from_fixture(item)
            if venue:
                venues[venue["code"]] = venue
            matches.append(self.match_from_fixture(item, venue))
        return RawSnapshot(
            source=self.source,
            source_type=self.source_type,
            source_url=source_url or self.source_url,
            payload={
                "source": data.get("source"),
                "license": data.get("license"),
                "tournament": data.get("tournament", {}),
                "venues": list(venues.values()),
                "matches": matches,
                "items": [],
            },
            parser_version=self.parser_version,
        )

    @classmethod
    def venue_from_fixture(cls, item: dict) -> dict | None:
        stadium = item.get("stadium")
        host_city = item.get("hostCity")
        if not stadium or not host_city:
            return None
        metadata = cls.HOST_CITIES.get(host_city, {})
        return {
            "code": cls.slug(stadium),
            "name": stadium,
            "city": metadata.get("city", host_city.replace("-", " ").title()),
            "country": metadata.get("country", "Unknown"),
            "timezone": metadata.get("timezone", "UTC"),
        }

    @classmethod
    def match_from_fixture(cls, item: dict, venue: dict | None) -> dict:
        match_number = item.get("matchNumber")
        group = item.get("group")
        stage = item.get("stage") or "unknown-stage"
        stage_code = f"group-{str(group).lower()}" if group else cls.slug(stage)
        stage_name = f"Group {group}" if group else stage.replace("-", " ").title()
        home = item.get("homeTeam") or f"Match {match_number} Home"
        away = item.get("awayTeam") or f"Match {match_number} Away"
        return {
            "public_id": f"thestatsapi-match-{match_number}",
            "source_match_url": item.get("matchUrl"),
            "match_number": match_number,
            "competition_code": "world_cup_2026",
            "stage_code": stage_code,
            "stage_name": stage_name,
            "stage_type": "group" if stage == "group-stage" else "knockout",
            "home": home,
            "away": away,
            "kickoff_at": item.get("kickoffUtc"),
            "status": "scheduled",
            "home_score": None,
            "away_score": None,
            "venue_code": venue["code"] if venue else None,
            "neutral_site": True,
            "source_confidence": 0.95,
        }

    @staticmethod
    def slug(value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
        return slug or "unknown"


def build_adapter(source: str, source_type: str) -> CollectorAdapter:
    if source == "dongqiudi":
        if source_type in {"world_cup_standings", "world_cup_player_rankings"}:
            return DongqiudiWorldCupDataAdapter(source_type)
        return DongqiudiHomepageAdapter(source_type)
    raise ValueError(f"Unsupported collector source: {source}")
