# 世界杯预测数据采集与组织方案

版本：v0.1  
更新日期：2026-06-15  
目标：把数据采集从“页面能看到一些真实数据”推进到“可持续入库、可验收、可供模型使用”。

## 1. 当前结论

现在先暂停 UI 扩展，优先把数据底座做扎实。

当前真实接入范围：

- 懂球帝首页低频采集：`https://pc.dongqiudi.com/`
- 已能写入 `raw_snapshots`、`collector_runs`、`news_items`、`teams/team_aliases`、`matches`
- 前端数据库模式已优先展示 `dongqiudi-` 开头的真实比赛
- TheStatsAPI 2026 世界杯 fixtures：`https://www.thestatsapi.com/world-cup/data/fixtures.json`
- 已能写入全量 104 场赛程、球队占位/参赛队、场地、城市、国家和时区
- 懂球帝 sport-data 世界杯 2026 接口：`competition_id=61`、`season_id=26123`
- 已能写入 12 个小组积分榜，以及球员射手、助攻、射门、射正、关键传球榜
- 懂球帝全站球员身价榜：按 `person_id` 匹配世界杯球员，已能写入匹配球员的 `market_value_eur`

当前还不能当成真实生产数据：

- 球队对不同世界排名球队战绩、阵容稳定性
- 球队总身价、主教练带队战绩
- 场地、天气、海拔、草皮
- AI 新闻结构化情报

原则：所有“还没真实来源”的数据，页面和模型都要标记为 `sample_or_partial` 或 `missing_real_source`，不能伪装成真实数据。

## 2. 数据分层

```text
外部来源
  -> raw_snapshots 原始快照
  -> normalizer 标准化
  -> canonical tables 标准业务表
  -> feature tables 模型特征
  -> prediction tables 预测结果
  -> API / miniapp 展示
```

### 2.1 Raw 层

所有外部数据先落 `raw_snapshots`。

| 字段 | 用途 |
| --- | --- |
| `source` | 数据源，例如 `dongqiudi`、`authorized_or_official` |
| `source_type` | 采集类型，例如 `homepage`、`schedule`、`player_ranking` |
| `source_url` | 原始 URL 或本地样本 URL |
| `payload` | 原始/半结构化 JSON |
| `checksum` | 去重与幂等 |
| `parser_version` | 解析器版本，方便回溯 |

### 2.2 Canonical 层

| 数据域 | 标准表 |
| --- | --- |
| 赛事/比赛 | `competitions`、`competition_stages`、`matches` |
| 球队 | `teams`、`team_aliases`、`team_form_snapshots` |
| 球员 | `players`、`player_form_snapshots` |
| 积分榜 | `group_standings` |
| 场地 | `venues`，后续补 `weather_snapshots` |
| 新闻 | `news_items` |
| AI 情报 | `ai_insights`、`ai_explanations` |
| 预测 | `model_versions`、`prediction_snapshots`、`match_predictions`、`scoreline_predictions`、`group_simulations`、`ranking_predictions` |

### 2.3 Quality 层

| 问题 | 字段/策略 |
| --- | --- |
| 从哪来 | `source`、`source_url`、`raw_snapshot_id` 或 `snapshot_id` |
| 有多可信 | `source_confidence`、`quality_status`、`data_quality`、`source_count` |
| 是否能进模型 | `is_model_eligible`、特征缺失 fallback、质量阈值 |

质量状态统一使用：

| 状态 | 含义 |
| --- | --- |
| `verified` | 官方或人工核验 |
| `source` | 来自外部源，字段完整 |
| `partial` | 字段不完整，但可展示 |
| `estimated` | 推断或兜底 |
| `sample` | 样例数据，只能开发测试 |
| `missing` | 未采集 |

## 3. 数据源矩阵

正式接入前，授权、频率、字段稳定性需要再验一次。懂球帝适合中文补充和原型验证，生产主数据建议接授权数据源或官方可用源。

| 需求 | 当前来源 | 当前状态 | 目标来源 | 标准表 | 更新频率 | 验收点 |
| --- | --- | --- | --- | --- | --- | --- |
| 赛程/比分/状态 | TheStatsAPI fixtures + 懂球帝首页 | 赛程/场地真实，比分片段部分真实 | 官方/授权赛程源 + 懂球帝校验 | `matches` | 每日，比赛日加密 | 覆盖全部世界杯比赛，时间/双方/状态可解析 |
| 中文新闻链接 | 懂球帝首页 | 部分真实 | 懂球帝/新闻源 | `news_items` | 每日 | 去重、保留 URL、可关联球队 |
| 小组积分榜 | 懂球帝 sport-data | 部分真实 | 官方/授权积分源交叉校验 | `group_standings` | 赛后 30 分钟 | 积分、净胜球、排名一致 |
| 球员近期进球助攻 | 懂球帝 sport-data | 部分真实 | 授权球员数据或稳定页面 | `players`、`player_form_snapshots` | 每日 | 已有进球、助攻、射门、射正、关键传球；分钟、评分、可用状态待补 |
| 球队今年比赛状态 | 懂球帝 sport-data 积分榜 | 部分真实 | 历史比赛库/授权数据源补全年队比赛 | `team_form_snapshots` | 每日 | 已有当前杯赛已赛、场均积分、进失球 |
| 对不同世界排名球队战绩 | 未接入 | 缺失 | 历史比赛 + FIFA/Elo 排名快照 | `team_form_snapshots.top30_record` | 每周/赛前 | Top10/Top30/Top50 战绩可计算 |
| 阵容稳定性 | 未接入 | 缺失 | 首发/出场分钟/大名单 | `team_form_snapshots.lineup_stability_score` | 每日 | 最近 N 场主力出勤率可计算 |
| 球员/球队身价 | 懂球帝 market_value_ranking | 球员部分真实 | 授权身价源/人工核验 | `players.market_value_eur`，后续补 `teams.market_value_eur` | 每周 | 已按 `person_id` 匹配部分世界杯球员，单位 EUR |
| 主教练带队战绩 | 未接入 | schema 缺口 | 授权源/人工核验 | `coaches` | 每周 | 任期、场次、胜率、大赛成绩 |
| 场地信息 | TheStatsAPI fixtures | 部分真实 | 官方场馆源补容量/海拔/草皮 | `venues` | 低频 | 城市、时区、国家已入库；容量、海拔、草皮待补 |
| 天气 | 未接入 | schema 缺口 | 天气 API | `weather_snapshots` | 赛前 24h/3h | 温度、湿度、风、降水概率 |
| 伤停/停赛 | 未接入 | 缺失 | 新闻 + AI 抽取 + 人工确认 | `injuries` 或 `ai_insights` | 每日/赛前 | 置信度大于 0.65 才进模型 |

## 4. 采集任务目录

后端已新增 `services/api/app/collectors/catalog.py`，`GET /api/v1/data-status` 会返回 `collection_catalog`。

| 顺序 | job | 目标 | 说明 |
| --- | --- | --- | --- |
| 1 | `dongqiudi_homepage` | 已有真实入口稳定化 | 保留 raw、比赛、新闻链接；继续做解析健壮性 |
| 2 | `official_schedule_venues` | 全量赛程 + 场地 | 已用 TheStatsAPI fixtures 接入 104 场赛程和场地基础字段 |
| 3 | `group_standings` | 小组积分榜 | 已用懂球帝 sport-data 接入 12 个小组 |
| 4 | `player_recent_form` | 球员进球、助攻、评分 | 已用懂球帝 sport-data 接入射手/助攻/射门等榜单；评分和出勤待补 |
| 5 | `team_form` | 球队近期状态 | 已从积分榜派生当前杯赛场均积分/进失球 |
| 6 | `team_market_value` | 身价 | 已按 `person_id` 匹配部分球员身价；球队总身价待聚合/校验 |
| 7 | `coach_records` | 主教练 | 后续补 schema 和采集 |
| 8 | `venue_weather` | 场地天气 | 后续补天气快照表 |
| 9 | `ai_news_insights` | AI 情报 | 把新闻转伤停、阵容、战术、教练言论 |

## 5. 标准 Payload

所有 adapter 输出统一 payload，runner 只认识标准字段。

### 5.1 matches

```json
{
  "matches": [
    {
      "public_id": "dongqiudi-home-away-2026-06-15",
      "competition_code": "world_cup_2026",
      "stage_code": "world-cup-homepage",
      "stage_name": "世界杯",
      "stage_type": "group",
      "home": "瑞典",
      "away": "突尼斯",
      "kickoff_at": "2026-06-15T00:00:00+08:00",
      "status": "live",
      "home_score": 3,
      "away_score": 1,
      "venue_code": null,
      "neutral_site": true,
      "source_confidence": 0.7
    }
  ]
}
```

### 5.2 groups

```json
{
  "groups": [
    {
      "code": "group-a",
      "teams": [
        {
          "team": "France",
          "rank": 1,
          "played": 1,
          "wins": 1,
          "draws": 0,
          "losses": 0,
          "goals_for": 2,
          "goals_against": 0,
          "points": 3
        }
      ]
    }
  ]
}
```

### 5.3 players

```json
{
  "as_of_at": "2026-06-15T02:00:00+08:00",
  "players": [
    {
      "code": "FRA-mbappe",
      "name": "姆巴佩",
      "name_en": "Kylian Mbappe",
      "team": "FRA",
      "position": "FW",
      "club_name": "Real Madrid",
      "market_value_eur": 180000000,
      "is_key_player": true,
      "recent_matches": 10,
      "minutes": 820,
      "goals": 8,
      "assists": 2,
      "shots": 41,
      "key_passes": 15,
      "rating": 7.8,
      "availability_status": "available",
      "form_score": 8.6,
      "source_count": 1
    }
  ]
}
```

### 5.4 team form

```json
{
  "team_forms": [
    {
      "team": "FRA",
      "as_of_at": "2026-06-15T02:00:00+08:00",
      "recent_matches": 10,
      "points_per_match": 2.2,
      "goals_for_per_match": 2.1,
      "goals_against_per_match": 0.8,
      "top30_record": {
        "wins": 4,
        "draws": 2,
        "losses": 1
      },
      "lineup_stability_score": 7.4,
      "injury_impact_score": -0.8,
      "data_quality": "partial"
    }
  ]
}
```

### 5.5 news and AI insights

```json
{
  "items": [
    {
      "type": "link",
      "title": "法国队赛前训练更新",
      "href": "https://example.com/news/1",
      "published_at": "2026-06-15T10:00:00+08:00"
    }
  ],
  "ai_insights": [
    {
      "event_type": "injury",
      "team": "FRA",
      "player": "某球员",
      "impact_area": "defense",
      "impact_score": -1.5,
      "confidence": 0.72,
      "evidence_text": "新闻提到该球员缺席训练",
      "source_url": "https://example.com/news/1",
      "is_model_eligible": true
    }
  ]
}
```

## 6. 更新频率

MVP 不做秒级实时，按低频批处理。

| 场景 | 频率 |
| --- | --- |
| 平时赛程/球队/球员 | 每日 02:00 |
| 比赛日前一天 | 开赛前 24 小时 |
| 比赛日 | 开赛前 3 小时 |
| 赛后 | 完场后 30 分钟 |
| 身价/教练 | 每周 |
| 天气 | 开赛前 24 小时、3 小时 |

每次采集后：

```text
run collector
  -> write raw snapshot
  -> normalize
  -> quality checks
  -> recompute predictions if feature data changed
  -> rebuild AI explanations if prediction/news changed
  -> data-status exposes readiness
```

## 7. 并发和幂等

已有策略：

- `raw_snapshots` 用 `source + source_type + checksum` 去重
- `CollectorRunner` 使用 PostgreSQL advisory transaction lock：`collector:{source}:{source_type}`
- `matches.public_id` upsert，重复运行不会重复插比赛
- `team_aliases` 按 `source + alias` upsert
- `player_form_snapshots` 同一球员同一 `as_of_at` replace
- `group_standings` 同一 stage/team replace

后续要补：

- 每个 source 的超时、重试、失败降级
- 采集任务不要并发写同一个 source_type
- scheduler 每个 job 设置最大执行时长
- 数据源异常时保留上一批可用标准表，不清空展示数据

## 8. 模型使用方式

模型不直接读 raw，而读标准表和特征表。

| 特征 | 来源 | 缺失处理 |
| --- | --- | --- |
| `fifa_rank_diff` | `teams` | 使用中位排名，标记 low confidence |
| `elo_diff` | `teams` | 使用默认 Elo，标记 estimated |
| `recent_points_diff` | `team_form_snapshots` | 缺失则不进入该特征 |
| `recent_goal_diff` | `team_form_snapshots` | 缺失则不进入该特征 |
| `player_form_diff` | `player_form_snapshots` | 缺失则权重为 0 |
| `market_value_diff` | `teams/players` | 缺失则权重为 0 |
| `injury_impact_diff` | `ai_insights/injuries` | 置信度低于 0.65 不进入模型 |
| `venue_weather_factor` | `venues/weather_snapshots` | 缺失则中性值 |

预测结果必须绑定：

- `model_version_id`
- `prediction_snapshot_id`
- 数据更新时间
- 关键特征解释

## 9. 验收点

### 9.1 数据采集验收

| 验收项 | 标准 |
| --- | --- |
| raw 快照 | 每个真实 collector 都写入 `raw_snapshots` |
| 运行记录 | 成功/失败都写入 `collector_runs` |
| 幂等 | 同一数据重复采集不产生重复比赛/新闻/球员 |
| 真实状态 | `data-status.collection_catalog.domains` 能区分 partial/sample/missing |
| 错误处理 | 外部源超时不会导致 API 读取崩溃 |
| 来源追溯 | 展示/模型数据能追到 source 或 snapshot |

### 9.2 数据完整性验收

| 数据域 | MVP 最低标准 |
| --- | --- |
| 比赛 | 全量赛程覆盖，双方、时间、状态完整 |
| 球队 | 参赛队至少 name/code/rank/quality_status |
| 球员 | 每队至少核心 5 人，近期进球助攻可用 |
| 积分榜 | 每个小组 4 队，排名/积分/净胜球完整 |
| 场地 | 每场比赛能关联 venue |
| 新闻 | 每场重点比赛至少 3 条候选新闻或明确为空 |
| AI 情报 | 低置信度过滤，高置信度可解释 |

### 9.3 模型验收

| 验收项 | 标准 |
| --- | --- |
| 缺失特征 | 不报错，降级为 neutral/estimated |
| 概率 | 胜平负概率和为 1 |
| 可复现 | 固定 seed 结果稳定 |
| 可解释 | 输出 key_factors，说明哪些数据缺失 |
| 质量标签 | 数据缺失较多时 confidence 降低 |

## 10. 测试点

后端测试：

```powershell
python -m pytest tests/test_collectors.py
python -m pytest tests/test_contract.py
$env:RUN_DATABASE_TESTS="1"; python -m pytest tests/test_database_backend.py
```

采集 smoke：

```powershell
python scripts/run_collector.py --source dongqiudi --source-type homepage --dry-run
python scripts/run_collector.py --source dongqiudi --source-type homepage
python scripts/run_collector.py --source local_sample --source-type schedule
python scripts/run_collector.py --source local_sample --source-type standings
python scripts/run_collector.py --source local_sample --source-type player_ranking
```

API smoke：

```powershell
curl http://127.0.0.1:8001/api/v1/data-status
curl http://127.0.0.1:8001/api/v1/home
curl http://127.0.0.1:8001/api/v1/matches/today
```

数据库检查：

```sql
select source, source_type, count(*) from raw_snapshots group by 1,2;
select source, job_type, status, records_read, records_written from collector_runs order by started_at desc limit 10;
select public_id, status, kickoff_at from matches order by updated_at desc limit 20;
select source, count(*) from news_items group by 1;
```

## 11. 下一步执行顺序

1. 保持现有懂球帝首页采集稳定，补解析测试样本。
2. TheStatsAPI fixtures 已接入；下一步补官方/人工校验字段，包括 stadium 容量、海拔、草皮。
3. 懂球帝世界杯积分榜已接入；后续接官方/授权积分源做交叉校验。
4. 懂球帝球员榜已接入；下一步补球员分钟、评分、可用状态和国家队名单。
5. `team_form_snapshots` 已从当前杯赛积分榜派生；下一步补全年国家队近期战绩。
6. 球员身价已部分接入；下一步聚合球队总身价并补缺失球员。
7. 补 `coaches`、`weather_snapshots`、`injuries` schema。
8. 接 AI 新闻抽取，生成 `ai_insights`。
9. 每次数据域变成真实后，更新 `collection_catalog` 状态和测试。
