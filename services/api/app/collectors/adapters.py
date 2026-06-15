from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
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
        match_blocks = []
        for index, text in enumerate(text_blocks):
            if text in {"世界杯", "友谊赛"} and index + 3 < len(text_blocks):
                match_blocks.append(
                    {
                        "type": "match_block",
                        "competition": text,
                        "home": text_blocks[index + 1],
                        "time_or_score": text_blocks[index + 2],
                        "away": text_blocks[index + 3],
                    }
                )
        return [*match_blocks[:20], *news_items[:80]]


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
