# 数据模型设计

版本：v0.1  
更新时间：2026-06-13  
用途：指导 M2 后端 API、M3 数据采集、M4 预测链路、M5 AI 情报开发。

## 1. 设计原则

- 前端只读后端 API，不直接访问第三方数据源。
- 所有外部数据必须先保存 raw 快照，再归一化到标准表。
- 预测结果必须绑定 `snapshot_id` 和 `model_version_id`，保证可追溯。
- 低频更新优先，MVP 不做秒级实时比分。
- 关键展示数据都要有 `updated_at`、`source_count`、`confidence` 或 `quality_status`。
- 懂球帝只作为原型和中文补充源，正式上线需要授权数据源或人工校验链路。

## 2. 数据域

| 数据域 | 说明 | MVP 优先级 |
| --- | --- | --- |
| 基础赛事 | 世界杯、赛季、阶段、小组、比赛、场馆 | P0 |
| 球队资料 | 球队、别名、FIFA 排名、Elo、阵容稳定性 | P0 |
| 球员资料 | 球员、别名、所属队、位置、近期进球助攻 | P1 |
| 教练资料 | 主教练、任期、带队战绩 | P1 |
| 数据源 | raw 快照、采集任务、源 ID 映射 | P0 |
| 近期状态 | 球队近况、球员近况、伤停、身价 | P0 |
| 预测结果 | 胜平负、比分分布、小组出线、冠军榜 | P0 |
| AI 情报 | 新闻、结构化事件、AI 解读、证据引用 | P0 |
| 赛后复盘 | 实际比分、预测命中、误差原因 | P2 |

## 3. 核心表

### 3.1 competitions

赛事表。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| code | varchar(64) | 是 | `world_cup_2026` |
| name | varchar(128) | 是 | 世界杯 |
| host_countries | jsonb | 否 | 主办国列表 |
| start_date | date | 是 | 开始日期 |
| end_date | date | 是 | 结束日期 |
| created_at | timestamptz | 是 | 创建时间 |
| updated_at | timestamptz | 是 | 更新时间 |

唯一约束：`code`

### 3.2 competition_stages

阶段表。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| competition_id | uuid | 是 | 赛事 ID |
| code | varchar(64) | 是 | `group_a`、`round_16` |
| name | varchar(128) | 是 | A组、16强 |
| stage_type | varchar(32) | 是 | `group` / `knockout` |
| sort_order | int | 是 | 展示顺序 |

唯一约束：`competition_id, code`

### 3.3 teams

球队标准表。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| code | varchar(32) | 是 | `FRA`、`BRA` |
| name_zh | varchar(128) | 是 | 中文名 |
| name_en | varchar(128) | 否 | 英文名 |
| confederation | varchar(32) | 否 | UEFA、CONMEBOL 等 |
| fifa_rank | int | 否 | FIFA 排名 |
| elo_rating | numeric(8,2) | 否 | Elo 分 |
| market_value_eur | numeric(14,2) | 否 | 全队身价 |
| quality_status | varchar(32) | 是 | `verified` / `estimated` / `missing` |
| created_at | timestamptz | 是 | 创建时间 |
| updated_at | timestamptz | 是 | 更新时间 |

索引：`code`、`fifa_rank`、`elo_rating`

### 3.4 team_aliases

球队源 ID 和别名映射。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| team_id | uuid | 是 | 标准球队 ID |
| source | varchar(64) | 是 | `dongqiudi`、`api_football` |
| source_team_id | varchar(128) | 否 | 外部源球队 ID |
| alias | varchar(128) | 是 | 外部源名称 |
| confidence | numeric(4,3) | 是 | 匹配置信度 |
| is_primary | boolean | 是 | 是否主映射 |

唯一约束：`source, source_team_id`，`source, alias`

### 3.5 players

球员标准表。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| team_id | uuid | 是 | 当前国家队 |
| name_zh | varchar(128) | 是 | 中文名 |
| name_en | varchar(128) | 否 | 英文名 |
| position | varchar(32) | 否 | GK/DF/MF/FW |
| shirt_number | int | 否 | 球衣号码 |
| birth_date | date | 否 | 出生日期 |
| club_name | varchar(128) | 否 | 俱乐部 |
| market_value_eur | numeric(14,2) | 否 | 身价 |
| is_key_player | boolean | 是 | 是否关键球员 |
| quality_status | varchar(32) | 是 | 数据质量 |
| created_at | timestamptz | 是 | 创建时间 |
| updated_at | timestamptz | 是 | 更新时间 |

索引：`team_id, position`、`team_id, is_key_player`

### 3.6 player_aliases

球员外部源映射。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| player_id | uuid | 是 | 标准球员 ID |
| source | varchar(64) | 是 | 数据源 |
| source_player_id | varchar(128) | 否 | 外部源球员 ID |
| alias | varchar(128) | 是 | 外部源名称 |
| confidence | numeric(4,3) | 是 | 匹配置信度 |

唯一约束：`source, source_player_id`，`source, alias`

### 3.7 coaches

主教练表。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| team_id | uuid | 是 | 球队 |
| name_zh | varchar(128) | 是 | 中文名 |
| name_en | varchar(128) | 否 | 英文名 |
| started_at | date | 否 | 上任日期 |
| matches_count | int | 否 | 带队场次 |
| win_rate | numeric(5,2) | 否 | 胜率百分比 |
| major_tournament_record | jsonb | 否 | 大赛战绩摘要 |
| updated_at | timestamptz | 是 | 更新时间 |

### 3.8 venues

场馆表。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| name | varchar(128) | 是 | 场馆名 |
| city | varchar(128) | 是 | 城市 |
| country | varchar(128) | 是 | 国家 |
| timezone | varchar(64) | 是 | 时区 |
| capacity | int | 否 | 容量 |
| altitude_m | int | 否 | 海拔 |
| surface | varchar(64) | 否 | 草皮类型 |
| weather_profile | jsonb | 否 | 常见天气 |

### 3.9 matches

比赛表。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| competition_id | uuid | 是 | 赛事 |
| stage_id | uuid | 是 | 阶段/小组 |
| home_team_id | uuid | 是 | 主队 |
| away_team_id | uuid | 是 | 客队 |
| venue_id | uuid | 否 | 场馆 |
| kickoff_at | timestamptz | 是 | 开球时间 |
| status | varchar(32) | 是 | `scheduled` / `live` / `finished` / `postponed` |
| home_score | int | 否 | 主队比分 |
| away_score | int | 否 | 客队比分 |
| neutral_site | boolean | 是 | 是否中立场 |
| source_confidence | numeric(4,3) | 是 | 数据源置信度 |
| updated_at | timestamptz | 是 | 更新时间 |

索引：`kickoff_at`、`status`、`stage_id`

### 3.10 group_standings

小组积分榜快照。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| stage_id | uuid | 是 | 小组 ID |
| team_id | uuid | 是 | 球队 ID |
| played | int | 是 | 已赛 |
| wins | int | 是 | 胜 |
| draws | int | 是 | 平 |
| losses | int | 是 | 负 |
| goals_for | int | 是 | 进球 |
| goals_against | int | 是 | 失球 |
| goal_diff | int | 是 | 净胜球 |
| points | int | 是 | 积分 |
| rank | int | 是 | 排名 |
| snapshot_id | uuid | 是 | 数据快照 |
| updated_at | timestamptz | 是 | 更新时间 |

唯一约束：`stage_id, team_id, snapshot_id`

### 3.11 team_form_snapshots

球队近期状态特征。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| team_id | uuid | 是 | 球队 |
| as_of_at | timestamptz | 是 | 截止时间 |
| recent_matches | int | 是 | 统计场次，默认 10 |
| points_per_match | numeric(5,2) | 否 | 场均积分 |
| goals_for_per_match | numeric(5,2) | 否 | 场均进球 |
| goals_against_per_match | numeric(5,2) | 否 | 场均失球 |
| xg_for_per_match | numeric(5,2) | 否 | 场均 xG |
| xg_against_per_match | numeric(5,2) | 否 | 场均被 xG |
| top30_record | jsonb | 否 | 对 Top30 战绩 |
| lineup_stability_score | numeric(5,2) | 否 | 阵容稳定性 |
| injury_impact_score | numeric(5,2) | 否 | 伤停影响 |
| data_quality | varchar(32) | 是 | `complete` / `partial` / `estimated` |

索引：`team_id, as_of_at`

### 3.12 player_form_snapshots

球员近期状态。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| player_id | uuid | 是 | 球员 |
| team_id | uuid | 是 | 国家队 |
| as_of_at | timestamptz | 是 | 截止时间 |
| recent_matches | int | 是 | 统计场次 |
| minutes | int | 否 | 出场时间 |
| goals | int | 否 | 进球 |
| assists | int | 否 | 助攻 |
| shots | int | 否 | 射门 |
| key_passes | int | 否 | 关键传球 |
| rating | numeric(4,2) | 否 | 近期评分 |
| availability_status | varchar(32) | 是 | `available` / `doubtful` / `injured` / `suspended` |
| form_score | numeric(5,2) | 否 | 归一化状态分 |
| source_count | int | 是 | 来源数量 |

索引：`team_id, as_of_at`、`player_id, as_of_at`

### 3.13 injuries

伤停和停赛表。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| team_id | uuid | 是 | 球队 |
| player_id | uuid | 否 | 球员 |
| type | varchar(32) | 是 | `injury` / `suspension` / `fitness` |
| status | varchar(32) | 是 | `confirmed` / `doubtful` / `returned` |
| impact_score | numeric(5,2) | 是 | 对球队影响，负数为不利 |
| started_at | date | 否 | 开始日期 |
| expected_return_at | date | 否 | 预计复出 |
| source_url | text | 否 | 来源 |
| confidence | numeric(4,3) | 是 | 置信度 |
| updated_at | timestamptz | 是 | 更新时间 |

### 3.14 raw_snapshots

外部数据原始快照。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| source | varchar(64) | 是 | 数据源 |
| source_url | text | 否 | 请求 URL 或页面 URL |
| source_type | varchar(64) | 是 | `schedule` / `standings` / `player_ranking` / `news` |
| fetched_at | timestamptz | 是 | 拉取时间 |
| checksum | varchar(128) | 是 | 内容哈希 |
| payload | jsonb | 是 | 原始数据 |
| parser_version | varchar(64) | 是 | 解析器版本 |

唯一约束：`source, source_type, checksum`

### 3.15 collector_runs

采集任务运行记录。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| source | varchar(64) | 是 | 数据源 |
| job_type | varchar(64) | 是 | 任务类型 |
| status | varchar(32) | 是 | `success` / `failed` / `partial` |
| started_at | timestamptz | 是 | 开始时间 |
| finished_at | timestamptz | 否 | 结束时间 |
| records_read | int | 是 | 读取数 |
| records_written | int | 是 | 写入数 |
| error_message | text | 否 | 错误摘要 |
| snapshot_ids | uuid[] | 否 | 关联快照 |

### 3.16 model_versions

模型版本表。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| name | varchar(128) | 是 | 模型名 |
| version | varchar(64) | 是 | `baseline_2026_06_13` |
| model_type | varchar(64) | 是 | `elo_poisson` / `xg_baseline` |
| training_data_start | date | 否 | 训练数据开始 |
| training_data_end | date | 否 | 训练数据结束 |
| feature_schema | jsonb | 是 | 特征定义 |
| metrics | jsonb | 否 | 回测指标 |
| is_active | boolean | 是 | 是否当前版本 |
| created_at | timestamptz | 是 | 创建时间 |

唯一约束：`name, version`

### 3.17 prediction_snapshots

预测批次快照。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| model_version_id | uuid | 是 | 模型版本 |
| data_snapshot_id | uuid | 否 | 关联 raw 快照或数据批次 |
| generated_at | timestamptz | 是 | 生成时间 |
| scope | varchar(64) | 是 | `matchday` / `group` / `tournament` |
| status | varchar(32) | 是 | `success` / `failed` |
| seed | int | 否 | Monte Carlo 随机种子 |
| notes | text | 否 | 说明 |

### 3.18 match_predictions

单场预测结果。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| match_id | uuid | 是 | 比赛 |
| prediction_snapshot_id | uuid | 是 | 预测批次 |
| model_version_id | uuid | 是 | 模型版本 |
| home_win_prob | numeric(6,5) | 是 | 主胜概率 |
| draw_prob | numeric(6,5) | 是 | 平局概率 |
| away_win_prob | numeric(6,5) | 是 | 客胜概率 |
| home_expected_goals | numeric(5,2) | 是 | 主队期望进球 |
| away_expected_goals | numeric(5,2) | 是 | 客队期望进球 |
| confidence | varchar(32) | 是 | `low` / `medium` / `high` |
| key_factors | jsonb | 是 | 关键因素 |
| generated_at | timestamptz | 是 | 生成时间 |

约束：`home_win_prob + draw_prob + away_win_prob` 误差小于 0.001

### 3.19 scoreline_predictions

比分分布。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| match_prediction_id | uuid | 是 | 单场预测 |
| home_goals | int | 是 | 主队进球 |
| away_goals | int | 是 | 客队进球 |
| probability | numeric(6,5) | 是 | 概率 |
| rank | int | 是 | 排名 |

唯一约束：`match_prediction_id, home_goals, away_goals`

### 3.20 group_simulations

小组出线模拟结果。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| stage_id | uuid | 是 | 小组 |
| prediction_snapshot_id | uuid | 是 | 预测批次 |
| team_id | uuid | 是 | 球队 |
| rank_1_prob | numeric(6,5) | 是 | 小组第一概率 |
| rank_2_prob | numeric(6,5) | 是 | 小组第二概率 |
| qualify_prob | numeric(6,5) | 是 | 出线概率 |
| expected_points | numeric(5,2) | 是 | 期望积分 |

唯一约束：`stage_id, prediction_snapshot_id, team_id`

### 3.21 ranking_predictions

冠军、四强、黑马榜。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| prediction_snapshot_id | uuid | 是 | 预测批次 |
| ranking_type | varchar(32) | 是 | `champion` / `semifinal` / `darkhorse` |
| team_id | uuid | 是 | 球队 |
| probability | numeric(6,5) | 是 | 概率 |
| delta | numeric(6,5) | 否 | 相比上批变化 |
| rank | int | 是 | 排名 |
| reason | varchar(128) | 否 | 榜单原因 |

### 3.22 news_items

新闻表。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| source | varchar(64) | 是 | 新闻源 |
| source_url | text | 是 | 原文链接 |
| title | text | 是 | 标题 |
| summary | text | 否 | 摘要 |
| language | varchar(16) | 是 | 语言 |
| published_at | timestamptz | 否 | 发布时间 |
| fetched_at | timestamptz | 是 | 抓取时间 |
| related_team_ids | uuid[] | 否 | 相关球队 |
| related_player_ids | uuid[] | 否 | 相关球员 |
| checksum | varchar(128) | 是 | 内容哈希 |

唯一约束：`source_url`，`checksum`

### 3.23 ai_insights

AI 结构化情报。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| news_item_id | uuid | 否 | 来源新闻 |
| event_type | varchar(64) | 是 | `injury` / `lineup` / `coach_comment` / `venue` |
| team_id | uuid | 否 | 相关球队 |
| player_id | uuid | 否 | 相关球员 |
| match_id | uuid | 否 | 相关比赛 |
| impact_area | varchar(64) | 是 | `attack` / `defense` / `morale` / `availability` |
| impact_score | numeric(5,2) | 是 | 对模型的影响 |
| confidence | numeric(4,3) | 是 | AI 置信度 |
| evidence_text | text | 是 | 证据摘要 |
| source_url | text | 否 | 来源 URL |
| is_model_eligible | boolean | 是 | 是否进入模型特征 |
| created_at | timestamptz | 是 | 创建时间 |

规则：`confidence < 0.65` 时 `is_model_eligible=false`

### 3.24 ai_explanations

AI 展示文案。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| target_type | varchar(32) | 是 | `match` / `team` / `group` / `ranking` |
| target_id | uuid | 是 | 目标 ID |
| prediction_snapshot_id | uuid | 否 | 预测批次 |
| title | varchar(128) | 是 | 标题 |
| content | text | 是 | 展示文案 |
| confidence_label | varchar(32) | 是 | 低/中/高信心 |
| evidence_refs | jsonb | 是 | 引用的预测和情报 |
| generated_at | timestamptz | 是 | 生成时间 |

### 3.25 post_match_reviews

赛后复盘。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| id | uuid | 是 | 主键 |
| match_id | uuid | 是 | 比赛 |
| match_prediction_id | uuid | 是 | 使用的赛前预测 |
| predicted_result | varchar(16) | 是 | `home` / `draw` / `away` |
| actual_result | varchar(16) | 是 | 实际结果 |
| result_hit | boolean | 是 | 方向是否命中 |
| scoreline_hit | boolean | 是 | 比分是否命中 |
| brier_score | numeric(8,5) | 否 | 预测误差 |
| review_text | text | 否 | 复盘摘要 |
| generated_at | timestamptz | 是 | 生成时间 |

## 4. 标准 ID 和映射规则

### 4.1 ID 策略

- 内部主键统一使用 UUID。
- 外部源 ID 不进入业务表主键，只放在 alias 或 raw 快照里。
- 小程序 API 对外可以使用短 ID，例如 `usa-paraguay-2026-06-13`，后端映射到 UUID。

### 4.2 映射优先级

1. 外部源 ID 精确匹配。
2. 中文名/英文名 + 国家队匹配。
3. 别名表 fuzzy match，置信度大于 0.92 自动通过。
4. 置信度 0.75 到 0.92 进入人工校验队列。
5. 低于 0.75 不入标准表，只保留 raw 快照。

## 5. 数据质量规则

| 规则 | 阈值 | 处理 |
| --- | --- | --- |
| 比赛双方为空 | 不允许 | 采集任务失败 |
| 开球时间不可解析 | 不允许 | 进入人工校验 |
| 胜平负概率不等于 1 | 误差大于 0.001 | 阻断预测入库 |
| 球员近期数据缺失 | 允许 | 标记 `partial` |
| 伤停置信度过低 | 小于 0.65 | 不进入模型 |
| 同一新闻重复 | checksum 相同 | 去重 |
| 小组积分异常 | 积分不等于胜平计算 | 标记冲突 |

## 6. MVP 必须先建的表

M2/M3/M4 最小闭环先建：

```text
competitions
competition_stages
teams
team_aliases
players
player_aliases
venues
matches
group_standings
team_form_snapshots
player_form_snapshots
injuries
raw_snapshots
collector_runs
model_versions
prediction_snapshots
match_predictions
scoreline_predictions
group_simulations
ranking_predictions
news_items
ai_insights
ai_explanations
```

`coaches` 和 `post_match_reviews` 可以在 M4/M5 之后补。

