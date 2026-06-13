UPDATED_AT = "2026-06-13T18:00:00+08:00"

TEAMS = {
    "usa": {
        "id": "usa",
        "name": "美国",
        "abbr": "USA",
        "fifa_rank": 11,
        "elo_rating": 1838,
    },
    "paraguay": {
        "id": "paraguay",
        "name": "巴拉圭",
        "abbr": "PAR",
        "fifa_rank": 48,
        "elo_rating": 1741,
    },
    "france": {
        "id": "france",
        "name": "法国",
        "abbr": "FRA",
        "fifa_rank": 2,
        "elo_rating": 2104,
    },
    "brazil": {
        "id": "brazil",
        "name": "巴西",
        "abbr": "BRA",
        "fifa_rank": 5,
        "elo_rating": 2078,
    },
    "england": {
        "id": "england",
        "name": "英格兰",
        "abbr": "ENG",
        "fifa_rank": 4,
        "elo_rating": 2059,
    },
}

MATCH_ID = "usa-paraguay-2026-06-13"

MATCHES = {
    MATCH_ID: {
        "id": MATCH_ID,
        "stage": "小组赛",
        "kickoff_at": "2026-06-13T01:00:00+08:00",
        "venue": {
            "name": "洛杉矶",
            "city": "Los Angeles",
            "timezone": "America/Los_Angeles",
        },
        "home_team": TEAMS["usa"],
        "away_team": TEAMS["paraguay"],
        "status": "scheduled",
    }
}

UPCOMING_MATCHES = [
    {
        "id": "qatar-switzerland-2026-06-13",
        "home_team": {"id": "qatar", "name": "卡塔尔", "abbr": "QAT"},
        "away_team": {"id": "switzerland", "name": "瑞士", "abbr": "SUI"},
        "kickoff_at": "2026-06-13T19:00:00+08:00",
        "status": "scheduled",
        "prediction_summary": {
            "tendency": "瑞士略优",
            "home_win_prob": 0.24,
            "draw_prob": 0.29,
            "away_win_prob": 0.47,
        },
    },
    {
        "id": "brazil-morocco-2026-06-13",
        "home_team": {"id": "brazil", "name": "巴西", "abbr": "BRA"},
        "away_team": {"id": "morocco", "name": "摩洛哥", "abbr": "MAR"},
        "kickoff_at": "2026-06-13T22:00:00+08:00",
        "status": "scheduled",
        "prediction_summary": {
            "tendency": "巴西占优",
            "home_win_prob": 0.56,
            "draw_prob": 0.24,
            "away_win_prob": 0.20,
        },
    },
]

MATCH_PREDICTIONS = {
    MATCH_ID: {
        "match_id": MATCH_ID,
        "model_version": "baseline_2026_06_13",
        "generated_at": UPDATED_AT,
        "probabilities": {
            "home_win": 0.44,
            "draw": 0.27,
            "away_win": 0.29,
        },
        "expected_goals": {
            "home": 1.42,
            "away": 1.18,
        },
        "scorelines": [
            {"score": "1-1", "probability": 0.12, "rank": 1},
            {"score": "2-1", "probability": 0.10, "rank": 2},
            {"score": "1-0", "probability": 0.09, "rank": 3},
            {"score": "0-0", "probability": 0.08, "rank": 4},
        ],
        "key_factors": [
            {"label": "阵容稳定", "value": 6, "note": "近 5 场首发重复率更高"},
            {"label": "近期进攻", "value": 4, "note": "前场创造力略优"},
            {"label": "伤停影响", "value": -2, "note": "边路轮换深度下降"},
        ],
        "confidence": "medium",
    }
}

AI_REPORTS = {
    MATCH_ID: {
        "title": "核心判断",
        "confidence_label": "中等信心",
        "content": "美国整体评分略高，但巴拉圭反击效率让平局和小比分概率上升。",
        "evidence": [
            {
                "type": "model_factor",
                "label": "阵容稳定",
                "value": 6,
                "source": "model_features",
            },
            {
                "type": "news",
                "label": "伤停影响",
                "confidence": 0.82,
                "source_url": "https://example.com/news",
            },
        ],
        "generated_at": UPDATED_AT,
    }
}

GROUPS = [
    {
        "id": "group-a",
        "name": "A组",
        "matches_finished": 2,
        "matches_total": 6,
        "summary": "墨西哥和韩国出线优势明显，捷克仍保留第三名晋级机会。",
    }
]

GROUP_DETAILS = {
    "group-a": {
        "id": "group-a",
        "name": "A组",
        "standings": [
            {
                "rank": 1,
                "team": {"id": "mexico", "name": "墨西哥"},
                "record": "1胜0平0负",
                "points": 3,
                "goals": "进2失0",
            },
            {
                "rank": 2,
                "team": {"id": "korea", "name": "韩国"},
                "record": "1胜0平0负",
                "points": 3,
                "goals": "进2失1",
            },
            {
                "rank": 3,
                "team": {"id": "czech", "name": "捷克"},
                "record": "0胜0平1负",
                "points": 0,
                "goals": "进1失2",
            },
            {
                "rank": 4,
                "team": {"id": "south-africa", "name": "南非"},
                "record": "0胜0平1负",
                "points": 0,
                "goals": "进0失2",
            },
        ],
    }
}

GROUP_SIMULATIONS = {
    "group-a": {
        "group_id": "group-a",
        "simulation_count": 50000,
        "teams": [
            {
                "team": {"id": "mexico", "name": "墨西哥"},
                "qualify_prob": 0.985,
                "rank_1_prob": 0.612,
                "rank_2_prob": 0.373,
                "expected_points": 6.8,
            },
            {
                "team": {"id": "korea", "name": "韩国"},
                "qualify_prob": 0.977,
                "rank_1_prob": 0.584,
                "rank_2_prob": 0.393,
                "expected_points": 6.5,
            },
        ],
    }
}

RANKINGS = {
    "champion": [
        {
            "rank": 1,
            "team": TEAMS["france"],
            "probability": 0.158,
            "delta": 0.012,
            "reason": "阵容深度",
        },
        {
            "rank": 2,
            "team": TEAMS["brazil"],
            "probability": 0.136,
            "delta": 0.008,
            "reason": "进攻状态",
        },
        {
            "rank": 3,
            "team": TEAMS["england"],
            "probability": 0.129,
            "delta": -0.003,
            "reason": "路径难度",
        },
    ],
    "semifinal": [
        {
            "rank": 1,
            "team": TEAMS["france"],
            "probability": 0.426,
            "delta": 0.023,
            "reason": "阵容深度",
        }
    ],
    "darkhorse": [
        {
            "rank": 1,
            "team": {"id": "morocco", "name": "摩洛哥", "abbr": "MAR"},
            "probability": 0.184,
            "delta": 0.036,
            "reason": "防守韧性",
        }
    ],
}

TEAM_PROFILES = {
    "france": {
        "team": TEAMS["france"],
        "summary": "法国阵容深度和进攻创造力领先，但后防伤停让淘汰赛稳定性略受影响。",
        "probabilities": [
            {"label": "冠军概率", "value": 0.158, "delta": 0.012},
            {"label": "四强概率", "value": 0.426},
            {"label": "小组第一", "value": 0.714},
        ],
        "ratings": [
            {"label": "进攻", "value": 8.7},
            {"label": "防守", "value": 7.8},
            {"label": "阵容深度", "value": 9.1},
            {"label": "稳定性", "value": 8.3},
        ],
        "form": {
            "headline": "近10场 7胜2平1负 · 进21失8",
            "stats": ["对Top30 3胜1平1负", "零封率 40%", "场均进球 2.1"],
        },
        "key_players": [
            {"id": "mbappe", "name": "姆巴佩", "role": "前锋", "form": 9.2},
            {"id": "griezmann", "name": "格列兹曼", "role": "中场", "form": 8.5},
        ],
        "risks": [{"label": "主力中卫伤停", "value": -2.4}],
    }
}

PLAYERS = {
    "mbappe": {
        "id": "mbappe",
        "team": TEAMS["france"],
        "name": "姆巴佩",
        "role": "前锋",
        "recent_form": {
            "matches": 10,
            "goals": 8,
            "assists": 3,
            "form_score": 9.2,
        },
    }
}

