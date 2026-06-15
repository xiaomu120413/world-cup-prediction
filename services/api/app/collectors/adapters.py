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
    parser_version: str = "local_sample_v1"


class CollectorAdapter(Protocol):
    source: str
    source_type: str

    def fetch(self) -> RawSnapshot:
        ...


class LocalSampleAdapter:
    source = "local_sample"

    def __init__(self, source_type: str):
        self.source_type = source_type

    def fetch(self) -> RawSnapshot:
        payload = SAMPLE_PAYLOADS.get(self.source_type)
        if payload is None:
            raise ValueError(f"Unsupported local sample source_type: {self.source_type}")
        return RawSnapshot(
            source=self.source,
            source_type=self.source_type,
            source_url=f"local://sample/{self.source_type}",
            payload=payload,
        )


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


SAMPLE_PAYLOADS = {
    "schedule": {
        "matches": [
            {
                "public_id": "usa-paraguay-2026-06-13",
                "home": "USA",
                "away": "PAR",
                "kickoff_at": "2026-06-13T01:00:00+08:00",
                "status": "scheduled",
            }
        ]
    },
    "standings": {
        "groups": [
            {
                "code": "group-a",
                "teams": [
                    {"code": "FRA", "rank": 1, "points": 3},
                    {"code": "BRA", "rank": 2, "points": 3},
                    {"code": "USA", "rank": 3, "points": 0},
                    {"code": "PAR", "rank": 4, "points": 0},
                ],
            }
        ]
    },
    "player_ranking": {
        "players": [
            {"name": "sample_forward", "team": "FRA", "goals": 3, "assists": 1},
            {"name": "sample_midfielder", "team": "BRA", "goals": 1, "assists": 2},
        ]
    },
}


def build_adapter(source: str, source_type: str) -> CollectorAdapter:
    if source == "local_sample":
        return LocalSampleAdapter(source_type)
    if source == "dongqiudi":
        return DongqiudiHomepageAdapter(source_type)
    raise ValueError(f"Unsupported collector source: {source}")
