from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.schema import collector_runs, data_source_links, matches, news_items, players, raw_snapshots, teams
from app.db.session import SessionLocal

API_TZ = ZoneInfo("Asia/Shanghai")

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
    {
        "source": "foxsports",
        "source_type": "world_cup_rss",
        "url": "https://api.foxsports.com/v2/content/optimized-rss?partnerKey=MB0Wehpmuj2lUhuRhQaafhBjAJqaPU244mlTDK1i&size=30&tags=soccer/wc/league/12",
        "confidence": 0.82,
    },
    {
        "source": "skysports",
        "source_type": "football_rss",
        "url": "https://www.skysports.com/rss/12040",
        "confidence": 0.82,
    },
    {
        "source": "skysports",
        "source_type": "world_cup_rss",
        "url": "https://www.skysports.com/rss/13973",
        "confidence": 0.82,
    },
    {
        "source": "sportsmole",
        "source_type": "football_rss",
        "url": "https://www.sportsmole.co.uk/football/rss.xml",
        "confidence": 0.78,
    },
]

MIN_SUCCESSFUL_NEWS_FEEDS = 2

BASE_KEYWORDS = (
    "2026 world cup",
    "world cup 2026",
    "world cup",
    "fifa world cup",
    "fifa",
    "injury",
    "injured",
    "ruled out",
    "will miss",
    "withdraws",
    "withdrawn",
    "fracture",
    "fractured",
    "broken leg",
    "ankle",
    "muscle fatigue",
    "hamstring",
    "suspension",
    "suspended",
    "red card",
    "sent off",
    "sending off",
    "three-match ban",
    "fitness",
    "doubtful",
    "squad",
    "lineup",
    "line-up",
    "starting xi",
    "team news",
    "training",
    "coach",
    "manager",
    "qualifier",
    "qualifiers",
)

TEAM_ALIASES = {
    "BOSNIA-AND-HERZEGOVINA": ["Bosnia", "Bosnia and Herzegovina"],
    "BRA": ["Brazil"],
    "CABO-VERDE": ["Cape Verde", "Cabo Verde"],
    "CANADA": ["Canada", "CanMNT"],
    "CONGO-DR": ["DR Congo", "Democratic Republic of Congo"],
    "COTE-D-IVOIRE": ["Ivory Coast", "Cote d'Ivoire"],
    "CZECHIA": ["Czechia", "Czech Republic"],
    "ENG": ["England"],
    "FRA": ["France"],
    "IR-IRAN": ["Iran"],
    "KOREA-REPUBLIC": ["South Korea", "Korea Republic"],
    "NETHERLANDS": ["Netherlands", "Holland"],
    "NEW-ZEALAND": ["New Zealand"],
    "PAR": ["Paraguay"],
    "SAUDI-ARABIA": ["Saudi Arabia"],
    "SOUTH-AFRICA": ["South Africa"],
    "TURKIYE": ["Turkey", "Turkiye"],
    "USA": ["United States", "USMNT", "USA"],
}


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
            parser_version="public_news_rss_v2",
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


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def item_text_any(item: ET.Element, names: set[str]) -> str | None:
    for child in item.iter():
        if local_name(child.tag) in names and child.text:
            return " ".join(child.text.split())
    return None


def item_link(item: ET.Element) -> str | None:
    value = item_text(item, "link")
    if value:
        return value
    for child in item.iter():
        if local_name(child.tag) == "link":
            href = child.attrib.get("href")
            if href:
                return href
    return None


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def phrase_matches(phrase: str, haystack: str) -> bool:
    normalized = normalize_text(phrase)
    if len(normalized) < 3:
        return False
    return f" {normalized} " in f" {haystack} "


def roster_team_terms(db) -> tuple[set[str], dict[str, list[dict]]]:
    rows = db.execute(
        select(teams.c.id, teams.c.code, teams.c.name_en)
        .select_from(teams.join(players, players.c.team_id == teams.c.id))
        .where(players.c.code.like("DQD-P%"))
        .group_by(teams.c.id, teams.c.code, teams.c.name_en)
    ).mappings().all()
    keyword_terms: set[str] = set()
    team_terms: dict[str, list[dict]] = {}
    for row in rows:
        terms = {row.name_en}
        if "-" in row.code:
            terms.add(row.code.replace("-", " "))
        terms.update(TEAM_ALIASES.get(row.code, []))
        for term in {value.strip() for value in terms if value and value.strip()}:
            normalized = normalize_text(term)
            if len(normalized) < 3:
                continue
            keyword_terms.add(normalized)
            team_terms.setdefault(normalized, []).append({"id": row.id, "code": row.code, "name": row.name_en})
    return keyword_terms, team_terms


def matchday_teams(db, current: datetime, local_day) -> list[dict]:
    next_24h = current + timedelta(hours=24)
    rows = db.execute(
        text(
            """
            select distinct t.code, t.name_en
            from matches m
            join teams t on t.id in (m.home_team_id, m.away_team_id)
            where (
                (m.kickoff_at at time zone 'Asia/Shanghai')::date = :local_day
                or (m.kickoff_at >= :now_at and m.kickoff_at < :next_24h)
              )
              and exists (
                  select 1
                  from players p
                  where p.team_id = t.id
                    and p.code like 'DQD-P%'
              )
            order by t.code
            """
        ),
        {"local_day": local_day, "now_at": current, "next_24h": next_24h},
    ).mappings().all()
    return [{"code": row.code, "name": row.name_en} for row in rows]


def matchday_context(db, now: datetime | None = None) -> dict:
    current = now or datetime.now(API_TZ)
    local_day = current.date()
    next_24h = current + timedelta(hours=24)
    previous_12h = current - timedelta(hours=12)
    values = db.execute(
        text(
            """
            select
              count(*) filter (where (kickoff_at at time zone 'Asia/Shanghai')::date = :local_day) as today_matches,
              count(*) filter (where kickoff_at >= :now_at and kickoff_at < :next_24h) as next_24h_matches,
              count(*) filter (where kickoff_at >= :previous_12h and kickoff_at < :now_at and status = 'finished') as recent_finished_matches
            from matches
            """
        ),
        {
            "local_day": local_day,
            "now_at": current,
            "next_24h": next_24h,
            "previous_12h": previous_12h,
        },
    ).mappings().one()
    is_matchday = int(values.today_matches or 0) > 0
    priority_teams = matchday_teams(db, current, local_day)
    return {
        "local_date": local_day.isoformat(),
        "mode": "matchday" if is_matchday else "offday",
        "is_matchday": is_matchday,
        "today_matches": int(values.today_matches or 0),
        "next_24h_matches": int(values.next_24h_matches or 0),
        "recent_finished_matches": int(values.recent_finished_matches or 0),
        "priority_team_codes": [team["code"] for team in priority_teams],
        "priority_teams": priority_teams,
        "definition": "matchday means at least one match kickoff falls on the local Asia/Shanghai calendar date",
    }


def feed_items(xml_text: str, keyword_terms: set[str], team_terms: dict[str, list[dict]]) -> list[dict]:
    root = ET.fromstring(xml_text)
    values = []
    for item in root.findall(".//item"):
        title = item_text_any(item, {"title"})
        link = item_link(item)
        description = item_text_any(item, {"description", "summary", "encoded", "content"})
        published_at = parse_date(item_text_any(item, {"pubdate", "published", "updated"}))
        if not title or not link:
            continue
        haystack = normalize_text(f"{title} {description or ''}")
        matched_keywords = sorted(term for term in keyword_terms if phrase_matches(term, haystack))
        matched_team_by_code = {}
        for term in matched_keywords:
            for team in team_terms.get(term, []):
                matched_team_by_code[team["code"]] = team
        if not matched_keywords:
            continue
        values.append(
            {
                "title": title,
                "link": link,
                "summary": description,
                "published_at": published_at.isoformat() if published_at else None,
                "matched_keywords": matched_keywords,
                "matched_teams": sorted(matched_team_by_code.values(), key=lambda value: value["code"]),
            }
        )
    return values


def snapshot_safe_items(items: list[dict]) -> list[dict]:
    return [
        {
            **item,
            "matched_teams": [{"code": team["code"], "name": team["name"]} for team in item["matched_teams"]],
        }
        for item in items
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect public football news RSS items.")
    parser.add_argument("--mode", choices=["auto", "daily", "matchday"], default="auto")
    args = parser.parse_args()
    started_at = datetime.now(API_TZ)

    with SessionLocal() as db:
        context = matchday_context(db)
        if args.mode != "auto":
            context["mode"] = args.mode
            context["is_matchday"] = args.mode == "matchday"
            context["definition"] += "; mode overridden by CLI"
        team_keywords, team_terms = roster_team_terms(db)
        keyword_terms = {normalize_text(value) for value in BASE_KEYWORDS}
        keyword_terms.update(team_keywords)
        total_items = 0
        errors = []
        source_links_by_key = {}
        snapshot_ids = []
        for feed in NEWS_FEEDS:
            try:
                response = httpx.get(
                    feed["url"],
                    timeout=30.0,
                    headers={"User-Agent": "Mozilla/5.0", "Accept": "application/rss+xml,text/xml,application/xml"},
                    follow_redirects=True,
                )
                response.raise_for_status()
                items = feed_items(response.text, keyword_terms, team_terms)
            except Exception as exc:
                errors.append({"source": feed["source"], "url": feed["url"], "error": str(exc)})
                continue
            snapshot_id = write_raw_snapshot(
                db,
                feed["source"],
                feed["source_type"],
                feed["url"],
                {"feed_url": feed["url"], "items": snapshot_safe_items(items), "matchday_context": context},
            )
            snapshot_ids.append(snapshot_id)
            rows_by_url = {}
            for item in items:
                related_team_ids = [team["id"] for team in item["matched_teams"]] or None
                row = {
                    "source": feed["source"],
                    "source_url": item["link"],
                    "title": item["title"],
                    "summary": item["summary"],
                    "language": "en",
                    "published_at": item["published_at"],
                    "related_team_ids": related_team_ids,
                    "checksum": checksum({"source": feed["source"], "url": item["link"], "title": item["title"]}),
                }
                rows_by_url[row["source_url"]] = row
                source_link = {
                    "entity_type": "news_item",
                    "entity_key": item["link"],
                    "source": feed["source"],
                    "source_type": feed["source_type"],
                    "source_url": item["link"],
                    "raw_snapshot_id": snapshot_id,
                    "source_record_id": checksum({"url": item["link"]})[:32],
                    "confidence": feed["confidence"],
                    "metadata": {
                        "title": item["title"],
                        "feed_url": feed["url"],
                        "matched_keywords": item["matched_keywords"],
                        "matched_teams": [{"code": team["code"], "name": team["name"]} for team in item["matched_teams"]],
                        "matchday_context": context,
                    },
                }
                source_links_by_key[
                    (
                        source_link["entity_type"],
                        source_link["entity_key"],
                        source_link["source"],
                        source_link["source_type"],
                    )
                ] = source_link
            rows = list(rows_by_url.values())
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
                            "related_team_ids": pg_insert(news_items).excluded.related_team_ids,
                            "fetched_at": text("now()"),
                            "checksum": pg_insert(news_items).excluded.checksum,
                        },
                    )
                )
            total_items += len(rows)
        source_links = list(source_links_by_key.values())
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
        successful_feeds = len(NEWS_FEEDS) - len(errors)
        if total_items == 0:
            status = "failed"
        elif successful_feeds >= MIN_SUCCESSFUL_NEWS_FEEDS:
            status = "success"
        else:
            status = "partial"
        db.execute(
            pg_insert(collector_runs).values(
                source="public_news_rss",
                job_type=f"collect_public_news:{context['mode']}",
                status=status,
                started_at=started_at,
                finished_at=datetime.now(API_TZ),
                records_read=len(NEWS_FEEDS),
                records_written=total_items,
                error_message=json.dumps(errors, ensure_ascii=False)[:4000] if errors else None,
                snapshot_ids=snapshot_ids,
            )
        )
        db.commit()
    print(
        json.dumps(
            {
                "feeds": len(NEWS_FEEDS),
                "successful_feeds": successful_feeds,
                "news_items_read": total_items,
                "source_links": len(source_links),
                "matchday_context": context,
                "keyword_terms": len(keyword_terms),
                "team_keyword_terms": len(team_keywords),
                "errors": errors,
            },
            ensure_ascii=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
