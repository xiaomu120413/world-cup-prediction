# API 合约设计

版本：v0.1  
更新时间：2026-06-13  
Base URL：`https://api.example.com`，本地开发为 `http://127.0.0.1:8000`

## 1. Overview

世界杯预测小程序 API 为前端提供低频更新的比赛、球队、预测、AI 解读和赛后复盘数据。

约定：

- API 版本前缀：`/api/v1`
- 返回格式：统一 envelope
- 时间格式：ISO 8601，默认带时区
- 金额单位：欧元，字段名包含 `_eur`
- 概率格式：API 返回 0 到 1 的小数，前端展示成百分比
- 公共小程序接口不要求登录
- 管理接口使用 Bearer Token

## 2. Authentication

### Public API

小程序展示接口暂不需要用户登录。

### Admin API

管理和任务触发接口需要：

```http
Authorization: Bearer $TOKEN
```

## 3. Response Envelope

成功：

```json
{
  "data": {},
  "meta": {
    "updated_at": "2026-06-13T18:00:00+08:00",
    "version": "v1",
    "request_id": "req_20260613_001"
  }
}
```

列表：

```json
{
  "data": [],
  "meta": {
    "updated_at": "2026-06-13T18:00:00+08:00",
    "count": 10,
    "version": "v1"
  }
}
```

失败：

```json
{
  "error": {
    "code": "MATCH_NOT_FOUND",
    "message": "比赛不存在",
    "details": {}
  },
  "meta": {
    "request_id": "req_20260613_002"
  }
}
```

## 4. Public Endpoints

### GET /health

**Summary**: 健康检查。

**Authentication**: None

**200 OK**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "time": "2026-06-13T18:00:00+08:00"
}
```

**Example Request**

```bash
curl "$BASE_URL/health"
```

### GET /api/v1/version

**Summary**: API 版本信息。

**Authentication**: None

**200 OK**

```json
{
  "data": {
    "api_version": "v1",
    "build": "2026.06.13",
    "minimum_miniapp_version": "0.1.0"
  },
  "meta": {
    "updated_at": "2026-06-13T18:00:00+08:00",
    "version": "v1"
  }
}
```

**Example Request**

```bash
curl "$BASE_URL/api/v1/version"
```

### GET /api/v1/home

**Summary**: 首页聚合数据。

**Description**: 返回今日重点比赛、即将开始比赛、冠军概率榜和首页 AI 摘要。

**Authentication**: None

#### Query Parameters

| Name | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| date | string | No | today | 比赛日期，格式 `YYYY-MM-DD` |
| timezone | string | No | Asia/Shanghai | 前端展示时区 |

**200 OK**

```json
{
  "data": {
    "featured_match": {
      "id": "usa-paraguay-2026-06-13",
      "home_team": { "id": "usa", "name": "美国", "abbr": "USA" },
      "away_team": { "id": "paraguay", "name": "巴拉圭", "abbr": "PAR" },
      "kickoff_at": "2026-06-13T01:00:00+08:00",
      "venue": "洛杉矶",
      "stage": "小组赛",
      "prediction": {
        "home_win_prob": 0.44,
        "draw_prob": 0.27,
        "away_win_prob": 0.29,
        "confidence": "medium",
        "tendency": "美国略占优"
      },
      "ai_summary": "美国整体评分略高，但巴拉圭反击效率让平局和小比分概率上升。"
    },
    "upcoming_matches": [],
    "champion_rankings": []
  },
  "meta": {
    "updated_at": "2026-06-13T18:00:00+08:00",
    "version": "v1"
  }
}
```

**Example Request**

```bash
curl "$BASE_URL/api/v1/home?date=2026-06-13&timezone=Asia/Shanghai"
```

### GET /api/v1/matches/today

**Summary**: 今日比赛列表。

**Authentication**: None

#### Query Parameters

| Name | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| date | string | No | today | 日期 |
| include_prediction | boolean | No | true | 是否返回预测摘要 |

**200 OK**

```json
{
  "data": [
    {
      "id": "usa-paraguay-2026-06-13",
      "home_team": { "id": "usa", "name": "美国", "abbr": "USA" },
      "away_team": { "id": "paraguay", "name": "巴拉圭", "abbr": "PAR" },
      "kickoff_at": "2026-06-13T01:00:00+08:00",
      "status": "scheduled",
      "prediction_summary": {
        "tendency": "美国略占优",
        "home_win_prob": 0.44,
        "draw_prob": 0.27,
        "away_win_prob": 0.29
      }
    }
  ],
  "meta": {
    "count": 1,
    "updated_at": "2026-06-13T18:00:00+08:00",
    "version": "v1"
  }
}
```

**Example Request**

```bash
curl "$BASE_URL/api/v1/matches/today?date=2026-06-13"
```

### GET /api/v1/matches/{match_id}

**Summary**: 比赛详情。

**Authentication**: None

#### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| match_id | string | Yes | 比赛 ID |

**200 OK**

```json
{
  "data": {
    "id": "usa-paraguay-2026-06-13",
    "stage": "小组赛",
    "kickoff_at": "2026-06-13T01:00:00+08:00",
    "venue": {
      "name": "洛杉矶",
      "city": "Los Angeles",
      "timezone": "America/Los_Angeles"
    },
    "home_team": { "id": "usa", "name": "美国", "abbr": "USA" },
    "away_team": { "id": "paraguay", "name": "巴拉圭", "abbr": "PAR" },
    "status": "scheduled"
  },
  "meta": {
    "updated_at": "2026-06-13T18:00:00+08:00",
    "version": "v1"
  }
}
```

**404 Not Found**: `MATCH_NOT_FOUND`

**Example Request**

```bash
curl "$BASE_URL/api/v1/matches/usa-paraguay-2026-06-13"
```

### GET /api/v1/matches/{match_id}/prediction

**Summary**: 单场预测。

**Authentication**: None

#### Path Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| match_id | string | Yes | 比赛 ID |

**200 OK**

```json
{
  "data": {
    "match_id": "usa-paraguay-2026-06-13",
    "model_version": "baseline_2026_06_13",
    "generated_at": "2026-06-13T18:00:00+08:00",
    "probabilities": {
      "home_win": 0.44,
      "draw": 0.27,
      "away_win": 0.29
    },
    "expected_goals": {
      "home": 1.42,
      "away": 1.18
    },
    "scorelines": [
      { "score": "1-1", "probability": 0.12, "rank": 1 },
      { "score": "2-1", "probability": 0.10, "rank": 2 }
    ],
    "key_factors": [
      { "label": "阵容稳定", "value": 6, "note": "近 5 场首发重复率更高" }
    ],
    "confidence": "medium"
  },
  "meta": {
    "updated_at": "2026-06-13T18:00:00+08:00",
    "version": "v1"
  }
}
```

**404 Not Found**: `PREDICTION_NOT_FOUND`

**Example Request**

```bash
curl "$BASE_URL/api/v1/matches/usa-paraguay-2026-06-13/prediction"
```

### GET /api/v1/matches/{match_id}/ai-report

**Summary**: 比赛 AI 赛前报告。

**Authentication**: None

**200 OK**

```json
{
  "data": {
    "title": "核心判断",
    "confidence_label": "中等信心",
    "content": "美国整体评分略高，但巴拉圭反击效率让平局和小比分概率上升。",
    "evidence": [
      {
        "type": "model_factor",
        "label": "阵容稳定",
        "value": 6,
        "source": "model_features"
      },
      {
        "type": "news",
        "label": "伤停影响",
        "confidence": 0.82,
        "source_url": "https://example.com/news"
      }
    ],
    "generated_at": "2026-06-13T18:00:00+08:00"
  },
  "meta": {
    "updated_at": "2026-06-13T18:00:00+08:00",
    "version": "v1"
  }
}
```

**Example Request**

```bash
curl "$BASE_URL/api/v1/matches/usa-paraguay-2026-06-13/ai-report"
```

### GET /api/v1/groups

**Summary**: 小组列表和概况。

**Authentication**: None

**200 OK**

```json
{
  "data": [
    {
      "id": "group-a",
      "name": "A组",
      "matches_finished": 2,
      "matches_total": 6,
      "summary": "墨西哥和韩国出线优势明显。"
    }
  ],
  "meta": {
    "count": 1,
    "updated_at": "2026-06-13T18:00:00+08:00",
    "version": "v1"
  }
}
```

**Example Request**

```bash
curl "$BASE_URL/api/v1/groups"
```

### GET /api/v1/groups/{group_id}

**Summary**: 小组积分榜。

**Authentication**: None

**200 OK**

```json
{
  "data": {
    "id": "group-a",
    "name": "A组",
    "standings": [
      {
        "rank": 1,
        "team": { "id": "mexico", "name": "墨西哥" },
        "record": "1胜0平0负",
        "points": 3,
        "goals": "进2失0"
      }
    ]
  },
  "meta": {
    "updated_at": "2026-06-13T18:00:00+08:00",
    "version": "v1"
  }
}
```

**Example Request**

```bash
curl "$BASE_URL/api/v1/groups/group-a"
```

### GET /api/v1/groups/{group_id}/simulation

**Summary**: 小组出线模拟。

**Authentication**: None

**200 OK**

```json
{
  "data": {
    "group_id": "group-a",
    "simulation_count": 50000,
    "teams": [
      {
        "team": { "id": "mexico", "name": "墨西哥" },
        "qualify_prob": 0.985,
        "rank_1_prob": 0.612,
        "rank_2_prob": 0.373,
        "expected_points": 6.8
      }
    ]
  },
  "meta": {
    "updated_at": "2026-06-13T18:00:00+08:00",
    "version": "v1"
  }
}
```

**Example Request**

```bash
curl "$BASE_URL/api/v1/groups/group-a/simulation"
```

### GET /api/v1/predictions/rankings

**Summary**: 预测榜。

**Authentication**: None

#### Query Parameters

| Name | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| type | string | No | champion | `champion` / `semifinal` / `darkhorse` |
| limit | integer | No | 20 | 返回数量 |

**200 OK**

```json
{
  "data": [
    {
      "rank": 1,
      "team": { "id": "france", "name": "法国" },
      "probability": 0.158,
      "delta": 0.012,
      "reason": "阵容深度"
    }
  ],
  "meta": {
    "ranking_type": "champion",
    "updated_at": "2026-06-13T18:00:00+08:00",
    "version": "v1"
  }
}
```

**Example Request**

```bash
curl "$BASE_URL/api/v1/predictions/rankings?type=champion&limit=10"
```

### GET /api/v1/teams

**Summary**: 球队列表。

**Authentication**: None

#### Query Parameters

| Name | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| q | string | No | - | 搜索关键字 |
| group_id | string | No | - | 小组筛选 |

**200 OK**

```json
{
  "data": [
    {
      "id": "france",
      "name": "法国",
      "abbr": "FRA",
      "fifa_rank": 2,
      "elo_rating": 2104
    }
  ],
  "meta": {
    "count": 1,
    "updated_at": "2026-06-13T18:00:00+08:00",
    "version": "v1"
  }
}
```

**Example Request**

```bash
curl "$BASE_URL/api/v1/teams?q=france"
```

### GET /api/v1/teams/{team_id}

**Summary**: 球队详情。

**Authentication**: None

**200 OK**

```json
{
  "data": {
    "id": "france",
    "name": "法国",
    "abbr": "FRA",
    "subtitle": "FIFA排名 2 · Elo 2104 · A组",
    "ratings": [
      { "label": "进攻", "value": 8.7 },
      { "label": "防守", "value": 7.8 }
    ],
    "form": {
      "headline": "近10场 7胜2平1负 · 进21失8",
      "stats": ["对Top30 3胜1平1负", "零封率 40%"]
    }
  },
  "meta": {
    "updated_at": "2026-06-13T18:00:00+08:00",
    "version": "v1"
  }
}
```

**Example Request**

```bash
curl "$BASE_URL/api/v1/teams/france"
```

### GET /api/v1/teams/{team_id}/profile

**Summary**: 球队分析页聚合数据。

**Authentication**: None

**200 OK**

```json
{
  "data": {
    "team": { "id": "france", "name": "法国", "abbr": "FRA" },
    "summary": "法国阵容深度和进攻创造力领先，但后防伤停让淘汰赛稳定性略受影响。",
    "probabilities": [
      { "label": "冠军概率", "value": 0.158, "delta": 0.012 }
    ],
    "key_players": [
      { "id": "mbappe", "name": "姆巴佩", "role": "前锋", "form": 9.2 }
    ],
    "risks": [
      { "label": "主力中卫伤停", "value": -2.4 }
    ]
  },
  "meta": {
    "updated_at": "2026-06-13T18:00:00+08:00",
    "version": "v1"
  }
}
```

**Example Request**

```bash
curl "$BASE_URL/api/v1/teams/france/profile"
```

### GET /api/v1/teams/{team_id}/matches

**Summary**: 球队赛程。

**Authentication**: None

**Example Request**

```bash
curl "$BASE_URL/api/v1/teams/france/matches"
```

### GET /api/v1/players/{player_id}

**Summary**: 球员详情。

**Authentication**: None

MVP 前端暂不做完整球员页，但 API 预留给球队页关键球员展开。

**Example Request**

```bash
curl "$BASE_URL/api/v1/players/mbappe"
```

## 5. Admin Endpoints

### POST /api/admin/collectors/run

**Summary**: 手动触发采集任务。

**Authentication**: Bearer Token

#### Request Body

```json
{
  "source": "dongqiudi",
  "job_type": "schedule",
  "dry_run": false
}
```

**Example Request**

```bash
curl -X POST "$BASE_URL/api/admin/collectors/run" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source":"dongqiudi","job_type":"schedule","dry_run":false}'
```

### POST /api/admin/predictions/recompute

**Summary**: 重新生成预测。

**Authentication**: Bearer Token

#### Request Body

```json
{
  "scope": "matchday",
  "match_ids": ["usa-paraguay-2026-06-13"],
  "model_version": "baseline_2026_06_13"
}
```

**Example Request**

```bash
curl -X POST "$BASE_URL/api/admin/predictions/recompute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"scope":"matchday","match_ids":["usa-paraguay-2026-06-13"],"model_version":"baseline_2026_06_13"}'
```

### POST /api/admin/ai/rebuild

**Summary**: 重新生成 AI 解读。

**Authentication**: Bearer Token

#### Request Body

```json
{
  "target_type": "match",
  "target_ids": ["usa-paraguay-2026-06-13"]
}
```

**Example Request**

```bash
curl -X POST "$BASE_URL/api/admin/ai/rebuild" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"target_type":"match","target_ids":["usa-paraguay-2026-06-13"]}'
```

## 6. Reusable Schemas

### TeamSummary

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| id | string | Yes | 球队 ID |
| name | string | Yes | 中文名 |
| abbr | string | Yes | 三字母缩写 |

### ProbabilityTriple

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| home_win | number | Yes | 主胜概率 |
| draw | number | Yes | 平局概率 |
| away_win | number | Yes | 客胜概率 |

### Error

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| code | string | Yes | 业务错误码 |
| message | string | Yes | 用户可读错误 |
| details | object | No | 调试信息 |

## 7. Error Reference

| HTTP | Code | Meaning | Resolution |
| --- | --- | --- | --- |
| 400 | INVALID_QUERY | 参数非法 | 检查 query/body |
| 401 | UNAUTHORIZED | 管理接口未认证 | 添加 Bearer token |
| 404 | MATCH_NOT_FOUND | 比赛不存在 | 检查 match_id |
| 404 | TEAM_NOT_FOUND | 球队不存在 | 检查 team_id |
| 404 | PREDICTION_NOT_FOUND | 预测未生成 | 先运行预测任务 |
| 409 | DATA_CONFLICT | 数据冲突 | 查看 collector_runs |
| 500 | INTERNAL_ERROR | 未预期错误 | 查看服务日志 |

## 8. Rate Limits

MVP 建议：

- Public API：每 IP 每分钟 120 次。
- Admin API：每 token 每分钟 30 次。
- 429 返回 `RATE_LIMITED`。

## 9. Versioning Notes

- v1 阶段只新增字段，不删除字段。
- 前端必须忽略未知字段。
- 破坏性变更进入 `/api/v2`。

