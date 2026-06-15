from __future__ import annotations

import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.schema import data_source_links, news_items, raw_snapshots
from app.db.session import SessionLocal

NEWS_FEEDS = [
    {
        "source": "guardian",
        "source_type": "football_rss",
        "url": "https://www.theguardian.com/football/rss",
        "confidence": 0.82,
    },
    {
        "source": "bbc",
        "source_type": "football_rss",
        "url": "https://feeds.bbci.co.uk/sport/football/rss.xml",
        "confidence": 0.84,
    },
    {
        "source": "espn",
        "source_type": "soccer_rss",
        "url": "https://www.espn.com/espn/rss/soccer/news",
        "confidence": 0.82,
    },
]

KEYWORDS = (
    "world cup",
    "fifa",
    "injury",
    "squad",
    "lineup",
    "team news",
    "argentina",
    "france",
    "spain",
    "brazil",
    "england",
    "germany",
    "mexico",
    "usa",
    "united states",
)


def checksum(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def write_raw_snapshot(db, source: str, source_type: str, source_url: str, payload: dict):
    statement = (
        pg_insert(raw_snapshots)
        .values(
            source=source,
            source_type=source_type,
            source_url=source_url,
            checksum=checksum(payload),
            payload=payload,
            parser_version="public_news_rss_v1",
        )
        .on_conflict_do_nothing(index_elements=["source", "source_type", "checksum"])
        .returning(raw_snapshots.c.id)
    )
    inserted = db.execute(statement).scalar_one_or_none()
    if inserted:
        return inserted
    return db.execute(
        text(
            """
            select id from raw_snapshots
            where source = :source and source_type = :source_type and checksum = :checksum
            """
        ),
        {"source": source, "source_type": source_type, "checksum": checksum(payload)},
    ).scalar_one()


def parse_date(value: str | None):
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None


def item_text(item: ET.Element, tag: str) -> str | None:
    value = item.findtext(tag)
    return " ".join(value.split()) if value else None


def feed_items(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    values = []
    for item in root.findall(".//item"):
        title = item_text(item, "title")
        link = item_text(item, "link")
        description = item_text(item, "description")
        published_at = parse_date(item_text(item, "pubDate"))
        if not title or not link:
            continue
        haystack = f"{title} {description or ''}".lower()
        if not any(keyword in haystack for keyword in KEYWORDS):
            continue
        values.append(
            {
                "title": title,
                "link": link,
                "summary": description,
                "published_at": published_at.isoformat() if published_at else None,
            }
        )
    return values


def main() -> None:
    with SessionLocal() as db:
        total_items = 0
        errors = []
        source_links = []
        for feed in NEWS_FEEDS:
            try:
                response = httpx.get(
                    feed["url"],
                    timeout=30.0,
                    headers={"User-Agent": "Mozilla/5.0", "Accept": "application/rss+xml,text/xml,application/xml"},
                    follow_redirects=True,
                )
                response.raise_for_status()
                items = feed_items(response.text)
            except Exception as exc:
                errors.append({"source": feed["source"], "url": feed["url"], "error": str(exc)})
                continue
            snapshot_id = write_raw_snapshot(
                db,
                feed["source"],
                feed["source_type"],
                feed["url"],
                {"feed_url": feed["url"], "items": items},
            )
            rows = []
            for item in items:
                row = {
                    "source": feed["source"],
                    "source_url": item["link"],
                    "title": item["title"],
                    "summary": item["summary"],
                    "language": "en",
                    "published_at": item["published_at"],
                    "checksum": checksum({"source": feed["source"], "url": item["link"], "title": item["title"]}),
                }
                rows.append(row)
                source_links.append(
                    {
                        "entity_type": "news_item",
                        "entity_key": item["link"],
                        "source": feed["source"],
                        "source_type": feed["source_type"],
                        "source_url": item["link"],
                        "raw_snapshot_id": snapshot_id,
                        "source_record_id": checksum({"url": item["link"]})[:32],
                        "confidence": feed["confidence"],
                        "metadata": {"title": item["title"], "feed_url": feed["url"]},
                    }
                )
            if rows:
                db.execute(
                    pg_insert(news_items)
                    .values(rows)
                    .on_conflict_do_update(
                        index_elements=["source_url"],
                        set_={
                            "source": pg_insert(news_items).excluded.source,
                            "title": pg_insert(news_items).excluded.title,
                            "summary": pg_insert(news_items).excluded.summary,
                            "language": pg_insert(news_items).excluded.language,
                            "published_at": pg_insert(news_items).excluded.published_at,
                            "fetched_at": text("now()"),
                            "checksum": pg_insert(news_items).excluded.checksum,
                        },
                    )
                )
            total_items += len(rows)
        if source_links:
            db.execute(
                pg_insert(data_source_links)
                .values(source_links)
                .on_conflict_do_update(
                    index_elements=["entity_type", "entity_key", "source", "source_type"],
                    set_={
                        "source_url": pg_insert(data_source_links).excluded.source_url,
                        "raw_snapshot_id": pg_insert(data_source_links).excluded.raw_snapshot_id,
                        "source_record_id": pg_insert(data_source_links).excluded.source_record_id,
                        "confidence": pg_insert(data_source_links).excluded.confidence,
                        "fetched_at": text("now()"),
                        "metadata": pg_insert(data_source_links).excluded["metadata"],
                    },
                )
            )
        db.commit()
    print(
        json.dumps(
            {"feeds": len(NEWS_FEEDS), "news_items_read": total_items, "source_links": len(source_links), "errors": errors},
            ensure_ascii=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
