from uuid import uuid4

from scripts.build_ai_news_insights import extract_insights_from_news


def test_extracts_model_eligible_injury_signal_for_matched_player():
    team_id = uuid4()
    player_id = uuid4()
    news_id = uuid4()
    news = {
        "id": news_id,
        "source": "bbc",
        "source_url": "https://example.test/injury",
        "title": "Brazil forward Neymar ruled out with calf injury",
        "summary": "The Brazil squad confirmed Neymar is injured before the World Cup match.",
        "related_team_ids": [team_id],
    }
    players = [
        {
            "id": player_id,
            "team_id": team_id,
            "name_zh": "内马尔",
            "name_en": "Neymar",
            "position": "FW",
            "market_value_eur": 50000000,
            "is_key_player": True,
        }
    ]

    insights = extract_insights_from_news(news, players, source_confidence=0.84)

    injury = next(item for item in insights if item["event_type"] == "injury")
    assert injury["team_id"] == team_id
    assert injury["player_id"] == player_id
    assert injury["impact_area"] == "availability"
    assert injury["importance"] == "core"
    assert injury["impact_direction"] == "negative"
    assert injury["impact_value_source"] == "rule_mapping"
    assert injury["impact_score"] < -0.8
    assert injury["confidence"] >= 0.65
    assert injury["is_model_eligible"] is True


def test_coach_comment_signal_is_not_model_eligible_by_default():
    team_id = uuid4()
    news = {
        "id": uuid4(),
        "source": "guardian",
        "source_url": "https://example.test/coach",
        "title": "England coach gives press conference before opener",
        "summary": "The manager discussed preparation and training.",
        "related_team_ids": [team_id],
    }

    insights = extract_insights_from_news(news, [], source_confidence=0.82)

    coach = next(item for item in insights if item["event_type"] == "coach_comment")
    assert coach["team_id"] == team_id
    assert coach["importance"] == "rotation"
    assert coach["impact_direction"] == "neutral"
    assert coach["is_model_eligible"] is False


def test_generic_injury_context_without_player_is_not_model_eligible():
    team_id = uuid4()
    news = {
        "id": uuid4(),
        "source": "guardian",
        "source_url": "https://example.test/generic-injury",
        "title": "Injury history shapes Brazil's World Cup story",
        "summary": "The article discusses past tournament injuries without naming a current absentee.",
        "related_team_ids": [team_id],
    }

    insights = extract_insights_from_news(news, [], source_confidence=0.82)

    injury = next(item for item in insights if item["event_type"] == "injury")
    assert injury["team_id"] == team_id
    assert injury["player_id"] is None
    assert injury["is_model_eligible"] is False


def test_red_card_without_player_is_model_eligible_for_related_team():
    team_id = uuid4()
    news = {
        "id": uuid4(),
        "source": "espn",
        "source_url": "https://example.test/red-card",
        "title": "South Africa midfielder sent off after red card against Canada",
        "summary": "The team will be without a suspended player for the next World Cup match.",
        "related_team_ids": [team_id],
    }

    insights = extract_insights_from_news(news, [], source_confidence=0.82)

    suspension = next(item for item in insights if item["event_type"] == "suspension")
    assert suspension["team_id"] == team_id
    assert suspension["player_id"] is None
    assert suspension["impact_direction"] == "negative"
    assert suspension["is_model_eligible"] is True


def test_fractured_ankle_absence_without_player_is_model_eligible_for_related_team():
    team_id = uuid4()
    news = {
        "id": uuid4(),
        "source": "guardian",
        "source_url": "https://example.test/fractured-ankle",
        "title": "Canada midfielder fractured ankle and will miss rest of tournament",
        "summary": "The World Cup squad confirmed a long absence.",
        "related_team_ids": [team_id],
    }

    insights = extract_insights_from_news(news, [], source_confidence=0.82)

    injury = next(item for item in insights if item["event_type"] == "injury")
    assert injury["team_id"] == team_id
    assert injury["player_id"] is None
    assert injury["impact_direction"] == "negative"
    assert injury["is_model_eligible"] is True
