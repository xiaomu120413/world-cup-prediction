from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.schema import ai_insights, collector_runs, data_source_links, news_items, players, teams
from app.db.session import SessionLocal

EXTRACTOR_SOURCE = "ai_news_extractor"
EXTRACTOR_SOURCE_TYPE = "news_insight_v1"
EXTRACTOR_VERSION = "news_insight_rules_v1"
MODEL_ELIGIBLE_THRESHOLD = 0.65
API_TZ = ZoneInfo("Asia/Shanghai")
EXTRA_STRONG_MODEL_KEYWORDS = {
    "injury": {"will miss", "fracture", "fractured", "broken leg", "surgery", "muscle fatigue", "rest of the tournament"},
    "suspension": {"red card", "sent off", "sending off", "dismissed", "ejected", "three-match ban"},
}
STRONG_MODEL_KEYWORDS = {
    "injury": {"ruled out", "withdraw", "withdrawn", "doubtful", "injured", "伤缺", "缺席", "退出", "无缘"},
    "suspension": {"suspended", "suspension", "ban", "banned", "停赛", "禁赛"},
}


@dataclass(frozen=True)
class EventRule:
    event_type: str
    impact_area: str
    keywords: tuple[str, ...]
    importance: str
    impact_direction: str
    impact_score: float
    base_confidence: float
    model_eligible: bool


EVENT_RULES = (
    EventRule(
        "injury",
        "availability",
        (
            "injury",
            "injured",
            "ruled out",
            "will miss",
            "rest of the tournament",
            "withdraw",
            "withdrawn",
            "doubtful",
            "fitness concern",
            "fracture",
            "fractured",
            "broken leg",
            "surgery",
            "muscle fatigue",
            "calf",
            "hamstring",
            "knee",
            "ankle",
            "foot injury",
            "受伤",
            "伤病",
            "伤缺",
            "缺席",
            "退出",
            "无缘",
        ),
        "key",
        "negative",
        -0.8,
        0.72,
        True,
    ),
    EventRule(
        "suspension",
        "availability",
        ("suspended", "suspension", "ban", "banned", "red card", "停赛", "禁赛", "红牌"),
        "key",
        "negative",
        -0.7,
        0.72,
        True,
    ),
    EventRule(
        "suspension",
        "availability",
        ("sent off", "sending off", "dismissed", "ejected", "three-match ban"),
        "key",
        "negative",
        -0.7,
        0.72,
        True,
    ),
    EventRule(
        "fitness",
        "availability",
        ("fit", "fitness", "returned to training", "back in training", "恢复训练", "复出", "伤愈"),
        "rotation",
        "positive",
        0.25,
        0.64,
        False,
    ),
    EventRule(
        "lineup",
        "lineup",
        ("lineup", "line-up", "starting xi", "starting lineup", "bench", "首发", "阵容", "替补"),
        "rotation",
        "neutral",
        0.2,
        0.62,
        False,
    ),
    EventRule(
        "squad",
        "squad",
        ("squad", "call up", "called up", "replacement", "roster", "名单", "征召", "补招", "大名单"),
        "rotation",
        "positive",
        0.15,
        0.62,
        False,
    ),
    EventRule(
        "coach_comment",
        "coach",
        ("coach", "manager", "press conference", "主教练", "教练", "发布会"),
        "rotation",
        "neutral",
        0.05,
        0.58,
        False,
    ),
    EventRule(
        "training",
        "preparation",
        ("training", "trained", "session", "训练", "合练", "备战"),
        "rotation",
        "neutral",
        0.05,
        0.58,
        False,
    ),
    EventRule(
        "tactic",
        "tactic",
        ("tactic", "formation", "pressing", "defensive", "attacking", "战术", "阵型", "高压", "防守", "进攻"),
        "rotation",
        "neutral",
        0.05,
        0.58,
        False,
    ),
)


def stable_key(parts: list[Any]) -> str:
    raw = json.dumps([str(part) if part is not None else "" for part in parts], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def normalize_ascii(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def contains_keyword(text: str, normalized_text: str, keyword: str) -> bool:
    normalized_keyword = normalize_ascii(keyword)
    if normalized_keyword:
        return f" {normalized_keyword} " in f" {normalized_text} "
    return keyword in text


def evidence_text(title: str, summary: str | None) -> str:
    value = f"{title}. {summary or ''}".strip()
    return value[:500]


def load_players(db, team_ids: list[Any] | None) -> list[dict]:
    query = select(
        players.c.id,
        players.c.team_id,
        players.c.name_zh,
        players.c.name_en,
        players.c.position,
        players.c.market_value_eur,
        players.c.is_key_player,
    )
    if team_ids:
        query = query.where(players.c.team_id.in_(team_ids))
    return [dict(row) for row in db.execute(query).mappings().all()]


def match_player(text: str, normalized_text: str, player_rows: list[dict]) -> dict | None:
    matches = []
    for player in player_rows:
        zh = player.get("name_zh") or ""
        en = player.get("name_en") or ""
        score = 0
        if len(zh) >= 2 and zh in text:
            score += 3
        normalized_en = normalize_ascii(en)
        if normalized_en and f" {normalized_en} " in f" {normalized_text} ":
            score += 3
        if not score:
            continue
        if player.get("is_key_player"):
            score += 2
        if player.get("market_value_eur") is not None:
            score += 1
        matches.append((score, player))
    if not matches:
        return None
    return sorted(matches, key=lambda item: item[0], reverse=True)[0][1]


def confidence_for(rule: EventRule, matched_keywords: list[str], team_id: Any | None, player: dict | None, source_confidence: float | None) -> float:
    confidence = rule.base_confidence
    confidence += min(0.12, max(0, len(matched_keywords) - 1) * 0.04)
    if team_id is not None:
        confidence += 0.05
    if player is not None:
        confidence += 0.08
    if source_confidence is not None:
        confidence = (confidence + min(0.95, float(source_confidence))) / 2
    return round(min(confidence, 0.95), 3)


def has_strong_model_keyword(event_type: str, matched_keywords: list[str]) -> bool:
    strong_values = set(STRONG_MODEL_KEYWORDS.get(event_type, set()))
    strong_values.update(EXTRA_STRONG_MODEL_KEYWORDS.get(event_type, set()))
    return any(keyword in strong_values for keyword in matched_keywords)


def is_model_eligible(rule: EventRule, confidence: float, matched_keywords: list[str], player: dict | None) -> bool:
    if not rule.model_eligible or confidence < MODEL_ELIGIBLE_THRESHOLD:
        return False
    return player is not None or has_strong_model_keyword(rule.event_type, matched_keywords)


def impact_for(rule: EventRule, player: dict | None) -> float:
    impact = rule.impact_score
    if player and rule.event_type in {"injury", "suspension"}:
        if player.get("is_key_player"):
            impact -= 0.25
        elif player.get("market_value_eur") is not None and float(player["market_value_eur"]) >= 20_000_000:
            impact -= 0.15
    return round(max(-2.0, min(2.0, impact)), 2)


def insight_classification(rule: EventRule, player: dict | None) -> tuple[str, str]:
    importance = rule.importance
    if player and rule.event_type in {"injury", "suspension"}:
        if player.get("is_key_player"):
            importance = "core"
        elif player.get("market_value_eur") is not None and float(player["market_value_eur"]) >= 20_000_000:
            importance = "key"
    return importance, rule.impact_direction


def extract_insights_from_news(news: dict, player_rows: list[dict], source_confidence: float | None = None) -> list[dict]:
    text_value = f"{news['title']} {news.get('summary') or ''}"
    normalized_text = normalize_ascii(text_value)
    related_team_ids = list(news.get("related_team_ids") or [])
    scoped_players = [player for player in player_rows if not related_team_ids or player["team_id"] in related_team_ids]
    player = match_player(text_value, normalized_text, scoped_players)
    team_ids = [player["team_id"]] if player else (related_team_ids or [None])
    values = []

    for rule in EVENT_RULES:
        matched_keywords = [keyword for keyword in rule.keywords if contains_keyword(text_value, normalized_text, keyword)]
        if not matched_keywords:
            continue
        for team_id in team_ids[:3]:
            confidence = confidence_for(rule, matched_keywords, team_id, player, source_confidence)
            eligible = is_model_eligible(rule, confidence, matched_keywords, player)
            importance, impact_direction = insight_classification(rule, player)
            values.append(
                {
                    "news_item_id": news["id"],
                    "event_type": rule.event_type,
                    "team_id": team_id,
                    "player_id": player["id"] if player else None,
                    "match_id": None,
                    "impact_area": rule.impact_area,
                    "importance": importance,
                    "impact_direction": impact_direction,
                    "impact_score": impact_for(rule, player),
                    "impact_value_source": "rule_mapping",
                    "confidence": confidence,
                    "evidence_text": evidence_text(news["title"], news.get("summary")),
                    "source_url": news["source_url"],
                    "is_model_eligible": eligible,
                    "metadata": {
                        "extractor_version": EXTRACTOR_VERSION,
                        "matched_keywords": matched_keywords,
                        "importance": importance,
                        "impact_direction": impact_direction,
                        "impact_value_source": "rule_mapping",
                        "title": news["title"],
                        "source": news["source"],
                        "player_name": player.get("name_en") or player.get("name_zh") if player else None,
                    },
                }
            )
    return values


def load_news(db, limit: int | None = None) -> list[dict]:
    query = (
        select(
            news_items.c.id,
            news_items.c.source,
            news_items.c.source_url,
            news_items.c.title,
            news_items.c.summary,
            news_items.c.related_team_ids,
            data_source_links.c.confidence.label("source_confidence"),
            data_source_links.c.raw_snapshot_id,
        )
        .select_from(
            news_items.outerjoin(
                data_source_links,
                (data_source_links.c.entity_type == "news_item")
                & (data_source_links.c.entity_key == news_items.c.source_url)
                & (data_source_links.c.source == news_items.c.source),
            )
        )
        .order_by(news_items.c.fetched_at.desc())
    )
    if limit:
        query = query.limit(limit)
    return [dict(row) for row in db.execute(query).mappings().all()]


def write_insights(db, insights: list[dict], news_rows: list[dict]) -> dict:
    news_ids = [row["id"] for row in news_rows]
    news_urls = [row["source_url"] for row in news_rows]
    if news_ids:
        existing_ids = [
            str(row[0])
            for row in db.execute(
                select(ai_insights.c.id).where(ai_insights.c.news_item_id.in_(news_ids))
            ).all()
        ]
        if existing_ids:
            db.execute(
                delete(data_source_links).where(
                    data_source_links.c.entity_type == "ai_insight",
                    data_source_links.c.entity_key.in_(existing_ids),
                    data_source_links.c.source == EXTRACTOR_SOURCE,
                    data_source_links.c.source_type == EXTRACTOR_SOURCE_TYPE,
                )
            )
        if news_urls:
            db.execute(
                delete(data_source_links).where(
                    data_source_links.c.entity_type == "ai_insight",
                    data_source_links.c.source_url.in_(news_urls),
                    data_source_links.c.source == EXTRACTOR_SOURCE,
                    data_source_links.c.source_type == EXTRACTOR_SOURCE_TYPE,
                )
            )
        db.execute(delete(ai_insights).where(ai_insights.c.news_item_id.in_(news_ids)))

    if not insights:
        return {"ai_insights": 0, "source_links": 0}

    rows = [
        {key: value for key, value in insight.items() if key != "metadata"}
        for insight in insights
    ]
    inserted = (
        db.execute(
            pg_insert(ai_insights)
            .values(rows)
            .returning(
                ai_insights.c.id,
                ai_insights.c.news_item_id,
                ai_insights.c.event_type,
                ai_insights.c.team_id,
                ai_insights.c.player_id,
                ai_insights.c.impact_area,
                ai_insights.c.confidence,
                ai_insights.c.source_url,
            )
        )
        .mappings()
        .all()
    )
    metadata_by_key = {
        insight_key(insight): insight["metadata"]
        for insight in insights
    }
    source_rows = []
    for row in inserted:
        key = insight_key(row)
        source_rows.append(
            {
                "entity_type": "ai_insight",
                "entity_key": str(row["id"]),
                "source": EXTRACTOR_SOURCE,
                "source_type": EXTRACTOR_SOURCE_TYPE,
                "source_url": row["source_url"],
                "raw_snapshot_id": None,
                "source_record_id": key,
                "confidence": row["confidence"],
                "metadata": metadata_by_key.get(key, {"extractor_version": EXTRACTOR_VERSION}),
            }
        )
    db.execute(
        pg_insert(data_source_links)
        .values(source_rows)
        .on_conflict_do_update(
            index_elements=["entity_type", "entity_key", "source", "source_type"],
            set_={
                "source_url": pg_insert(data_source_links).excluded.source_url,
                "source_record_id": pg_insert(data_source_links).excluded.source_record_id,
                "confidence": pg_insert(data_source_links).excluded.confidence,
                "fetched_at": text("now()"),
                "metadata": pg_insert(data_source_links).excluded["metadata"],
            },
        )
    )
    return {"ai_insights": len(inserted), "source_links": len(source_rows)}


def insight_key(value: dict) -> str:
    return stable_key(
        [
            value.get("news_item_id"),
            value.get("event_type"),
            value.get("team_id"),
            value.get("player_id"),
            value.get("impact_area"),
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build structured AI news insights from collected news items.")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    started_at = datetime.now(API_TZ)

    with SessionLocal() as db:
        news_rows = load_news(db, args.limit)
        team_ids = list({team_id for row in news_rows for team_id in (row.get("related_team_ids") or [])})
        player_rows = load_players(db, team_ids or None)
        insights = [
            insight
            for news in news_rows
            for insight in extract_insights_from_news(news, player_rows, news.get("source_confidence"))
        ]
        if args.dry_run:
            result = {"status": "dry_run", "news_items": len(news_rows), "ai_insights_to_write": len(insights)}
        else:
            result = {"status": "success", "news_items": len(news_rows), **write_insights(db, insights, news_rows)}
            db.execute(
                pg_insert(collector_runs).values(
                    source=EXTRACTOR_SOURCE,
                    job_type=EXTRACTOR_SOURCE_TYPE,
                    status="success",
                    started_at=started_at,
                    finished_at=datetime.now(API_TZ),
                    records_read=len(news_rows),
                    records_written=result["ai_insights"],
                    error_message=None,
                    snapshot_ids=[],
                )
            )
            db.commit()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
