# 世界杯预测小程序技术执行方案

版本：v0.1  
更新时间：2026-06-13  
目标：把产品方案推进到可开发、可部署、可上线的小程序技术方案。

## 1. 结论

这套方案技术可行，建议按“小程序前端 + 云服务器后端 + 数据任务 + 模型任务 + AI 情报任务”的方式正式执行。

核心判断：

- 微信小程序正式上线需要后端服务器。
- 小程序端只负责展示和交互，不做数据采集、模型训练、AI 调用。
- 后端统一处理数据源、模型、AI、缓存和接口。
- MVP 阶段用 2核4G 轻量云服务器即可。
- Mac mini 可以作为开发机或离线模型/采集辅助机，但正式小程序 API 建议跑在云服务器。

推荐第一版架构：

```text
Taro 微信小程序
  -> HTTPS API 域名
  -> FastAPI 后端
  -> PostgreSQL
  -> Redis
  -> 定时采集任务
  -> 模型预测任务
  -> AI 情报任务
```

## 2. 为什么需要服务器

微信小程序正式环境不能把重逻辑放在客户端。

服务器必须承担：

- 第三方数据源 API key 保密。
- OpenAI API key 保密。
- 数据采集和清洗。
- 模型预测和赛事模拟。
- 预测结果缓存。
- 小程序接口统一输出。
- 日志、监控和异常处理。

小程序只做：

- 页面展示。
- 页面跳转。
- 基础筛选。
- 分享。
- 读取后端 API。

上线约束：

- 小程序请求后端需要 HTTPS。
- 请求域名需要配置到微信小程序后台的 request 合法域名。
- 正式上线通常需要已备案域名。
- 不能直接使用 localhost 或家庭内网地址。
- 不建议让小程序直接请求懂球帝、Sportmonks、OpenAI 等外部服务。

## 3. 技术栈选择

### 3.1 前端

推荐：

```text
Taro + React + TypeScript
```

原因：

- 可以先跑 H5 预览。
- 后续可编译微信小程序。
- 比 Vite H5 再迁移小程序风险低。
- React 组件化适合当前设计稿。

前端目录建议：

```text
apps/miniapp/
  src/
    app.config.ts
    app.ts
    pages/
      matches/
      match-detail/
      groups/
      predictions/
      team-detail/
      player-detail/
    components/
      ProbabilitySummary/
      AIReportCard/
      EvidenceList/
      ScorelineDistribution/
      QualificationImpact/
      TeamRatingPanel/
      MatchRow/
      BottomNav/
    services/
      api.ts
      data.ts
    stores/
    styles/
    utils/
```

### 3.2 后端

推荐：

```text
FastAPI + Python
```

原因：

- 和模型、数据任务、AI 任务同语言。
- 开发速度快。
- 类型清晰，自动生成 OpenAPI。
- 后续可拆模型服务。

后端目录建议：

```text
services/api/
  app/
    main.py
    config.py
    routers/
      matches.py
      teams.py
      players.py
      groups.py
      predictions.py
      admin.py
    schemas/
    services/
    repositories/
    db/
```

### 3.3 数据库

推荐：

```text
PostgreSQL
```

用途：

- 基础数据。
- 预测结果。
- 数据快照。
- 模型版本。
- AI 情报。

### 3.4 缓存

推荐：

```text
Redis
```

用途：

- 首页缓存。
- 比赛详情缓存。
- 预测榜缓存。
- 小组页缓存。
- 限流和任务状态。

### 3.5 后台任务

MVP 推荐：

```text
APScheduler
```

正式版可升级：

```text
Celery + Redis
```

任务类型：

- 数据采集。
- 新闻抓取。
- AI 情报抽取。
- 特征生成。
- 模型预测。
- 赛事模拟。
- 赛后复盘。

### 3.6 模型

MVP 分层：

```text
P0:
  history_core multinomial logistic regression
  context_calibrator multinomial logistic regression

P1:
  LightGBM / CatBoost 胜平负模型

比分:
  Poisson / Dixon-Coles

赛事:
  Monte Carlo Simulation
```

当前不把所有特征简单手写成权重。P0 采用两层结构：

- `history_core` 只学习历史国家队比赛、Elo、近期战绩、赛事类型、休息天数等可回测特征。
- `context_calibrator` 使用 `history_core` 的基础概率，再叠加当前球队榜、球员身价、球员近期状态、教练、伤停和 AI 情报等上下文特征做概率校准。
- 如果某场比赛任一球队缺少当前上下文，推理必须回退到 `history_core_fallback`，并在 API 返回里标明未应用校准。

LightGBM / CatBoost 放到 P1：必须先补齐历史赛前快照或严格控制特征时间点，否则训练会把赛后/当前信息带入历史样本，造成时间泄漏。

### 3.7 AI

推荐：

```text
OpenAI API
```

AI 不直接预测胜负，只做：

- 新闻抽取。
- 伤停识别。
- 战术变化识别。
- 情报影响评分。
- 预测解释生成。
- 数据冲突检查。

## 4. 部署架构

### 4.1 MVP 部署

一台轻量云服务器即可：

```text
2核4G
60G 系统盘
3M-5M 带宽
Ubuntu 22.04 / 24.04
Docker Compose
```

运行：

```text
Nginx
FastAPI
PostgreSQL
Redis
APScheduler Worker
```

结构：

```text
微信小程序
  -> https://api.xxx.cn
  -> Nginx
  -> FastAPI
  -> PostgreSQL / Redis
  -> 定时任务
```

### 4.2 稳定版部署

当用户量和任务量上来：

```text
API 服务器：2核4G 或 4核4G
数据库：托管 PostgreSQL 或单独服务器
Redis：托管版或单独容器
模型任务：独立 worker
对象存储：保存原始快照、图片和日志归档
```

### 4.3 Mac mini 的位置

Mac mini 可以用于：

- 本地开发。
- 跑离线训练。
- 跑数据采集实验。
- 生成模型文件。
- 管理后台内部使用。

不建议直接作为正式小程序 API 服务器，原因：

- 家庭宽带公网 IP 不稳定。
- 域名、备案、HTTPS 和微信合法域名配置麻烦。
- 断电断网会影响小程序。
- 运营商可能限制 80/443。

可选混合方案：

```text
小程序 API 跑云服务器
Mac mini 跑离线训练/采集
训练结果同步到云服务器
```

## 5. 域名和上线准备

建议准备：

```text
域名：xxx.cn / xxx.com
API 域名：api.xxx.cn
管理后台：admin.xxx.cn
HTTPS：Let's Encrypt / 云厂商免费证书
备案：国内小程序正式上线建议完成 ICP 备案
```

微信小程序后台配置：

```text
request 合法域名：
  https://api.xxx.cn

downloadFile 合法域名：
  如需加载远程图片或文件，再配置资源域名

uploadFile 合法域名：
  MVP 暂不需要

socket 合法域名：
  MVP 暂不需要
```

MVP 不做实时通信，因此不需要 WebSocket。

## 6. 系统模块拆解

### 6.1 miniapp 前端

职责：

- 展示页面。
- 调用 API。
- 显示加载、错误、空状态。
- 支持页面分享。

不做：

- 模型计算。
- AI 调用。
- 第三方数据抓取。
- 敏感 key 存储。

页面：

```text
/pages/matches/index
/pages/match-detail/index
/pages/groups/index
/pages/predictions/index
/pages/team-detail/index
/pages/player-detail/index
```

### 6.2 api-service

职责：

- 小程序接口。
- 聚合数据库和缓存。
- 返回稳定 JSON。
- 做基础限流。
- 管理版本兼容。

### 6.3 collector-service

职责：

- 拉取赛程、积分榜、球员榜、球队榜。
- 拉取新闻。
- 保存 raw 快照。
- 记录采集状态。

数据源适配器：

```text
DqdAdapter
FifaAdapter
SportmonksAdapter
ApiFootballAdapter
OpenMeteoAdapter
NewsAdapter
```

### 6.4 normalizer-service

职责：

- 队名归一。
- 球员名归一。
- 数据源 ID 映射。
- 时间格式标准化。
- 比赛状态标准化。

### 6.5 ai-insight-service

职责：

- 读取新闻。
- 调用 OpenAI。
- 抽取结构化情报。
- 生成影响分。
- 生成解释文本。
- 做冲突检查。

### 6.6 feature-service

职责：

- 生成比赛特征。
- 聚合球队状态。
- 聚合球员状态。
- 计算伤停影响。
- 计算阵容稳定。
- 计算环境影响。

### 6.7 model-service

职责：

- 训练模型。
- 保存模型版本。
- 批量预测比赛。
- 输出胜平负概率。
- 输出期望进球。
- 生成比分概率。

### 6.8 simulation-service

职责：

- 使用单场预测结果。
- 模拟小组赛。
- 模拟淘汰赛。
- 输出晋级概率和冠军概率。

### 6.9 admin-service

职责：

- 查看采集状态。
- 查看 AI 情报。
- 人工修正球队/球员映射。
- 人工确认伤停。
- 触发单场重算。
- 查看模型评估。

MVP 可以先不做完整后台，用脚本和简单管理接口代替。

## 7. 数据库设计

### 7.1 基础表

```text
teams
players
matches
venues
coaches
```

### 7.2 采集表

```text
raw_snapshots
collector_runs
data_source_mappings
team_aliases
player_aliases
```

### 7.3 统计表

```text
team_stat_snapshots
team_form_snapshots
player_form_snapshots
lineup_snapshots
injury_snapshots
```

### 7.4 AI 表

```text
news_items
ai_insights
ai_explanations
data_conflicts
```

### 7.5 模型表

```text
model_versions
model_features
prediction_snapshots
match_predictions
scoreline_predictions
group_simulations
ranking_predictions
prediction_reviews
```

## 8. API 设计

### 8.1 小程序接口

首页：

```text
GET /api/v1/home
```

比赛：

```text
GET /api/v1/matches/today
GET /api/v1/matches/{match_id}
GET /api/v1/matches/{match_id}/prediction
GET /api/v1/matches/{match_id}/review
```

小组：

```text
GET /api/v1/groups
GET /api/v1/groups/{group_id}
GET /api/v1/groups/{group_id}/simulation
```

预测榜：

```text
GET /api/v1/predictions/rankings?type=champion
GET /api/v1/predictions/rankings?type=semifinal
GET /api/v1/predictions/rankings?type=darkhorse
```

球队：

```text
GET /api/v1/teams/{team_id}
GET /api/v1/teams/{team_id}/profile
GET /api/v1/teams/{team_id}/matches
```

球员：

```text
GET /api/v1/players/{player_id}
```

### 8.2 管理接口

```text
POST /api/admin/collectors/run
POST /api/admin/predictions/recompute
POST /api/admin/ai/extract
POST /api/admin/mappings/teams
POST /api/admin/mappings/players
```

管理接口需要鉴权，不开放给小程序。

## 9. 任务调度设计

### 9.1 每日任务

```text
02:00 更新赛程和积分榜
02:10 更新球员榜和球队榜
02:30 更新新闻
03:00 AI 情报抽取
03:30 特征生成
04:00 模型批量预测
04:30 赛事模拟
12:00 检查天气、新闻、伤停
12:30 如特征变化则重算预测
```

### 9.2 比赛日前任务

```text
比赛前 24 小时：
  更新伤停、预计阵容、新闻
  生成赛前初版预测

比赛前 3 小时：
  更新关键情报
  生成最终赛前版

比赛前 90 分钟：
  刷新 FIFA start list / 最终首发
  若无法拿到最终首发，保留赛前 3 小时预测并降级置信度
```

### 9.3 赛后任务

```text
比赛结束后 30 分钟：
  更新比分
  更新积分榜
  更新预测复盘
  重算小组和赛事模拟
```

## 10. 数据源策略

### 10.1 原型阶段

```text
懂球帝：中文赛程、积分榜、球员榜、球队榜
FIFA：官方校验
Open-Meteo：天气
公开历史数据：模型训练
新闻源：懂球帝/FIFA/公开新闻
```

当前 MVP 内部验证阶段先把懂球帝作为同一套球队和球员身份源，尤其是 48 队名单、球员身价、教练、球队榜 45 项指标和球员近期状态。这样可以减少跨源姓名映射错误。所有入模数据必须写 `data_source_links`，并标明 `source_class=public_source` 或对应来源类别。

### 10.2 正式阶段

```text
Sportmonks / API-Football：主数据源
懂球帝：中文展示补充和交叉校验
FIFA：官方赛程校验
Open-Meteo：天气
OpenAI：AI 情报和解释
```

### 10.3 适配器原则

所有数据源统一通过适配器输出标准结构：

```text
ExternalMatch -> Match
ExternalTeam -> Team
ExternalPlayer -> Player
ExternalStanding -> GroupStanding
ExternalNews -> NewsItem
```

这样后续替换懂球帝为商业 API，不影响前端和模型。

## 11. 模型执行方案

### 11.1 第一阶段：Baseline

目标：先跑通可训练、可回测、可解释的预测链路。

```text
历史国家队比赛导入
Elo 和近期状态特征
history_core 胜平负小模型
Poisson 输出期望进球
Monte Carlo 输出出线概率
```

优点：

- 快。
- 可解释。
- 不依赖大量特征。

当前已进入 P0+ 阶段：在 baseline 之上增加 `context_calibrator`。它不是人工权重，而是用当前上下文特征学习对 `history_core` 概率的修正。

### 11.2 当前阶段：两层上下文校准模型

模型结构：

```text
history_core:
  输入历史可回测特征
  输出 base_probabilities

context_calibrator:
  输入 base_probabilities + 当前上下文特征差值
  输出 calibrated probabilities
```

`history_core` 训练特征：

```text
elo_diff
recent_10_points_per_match_diff
recent_10_goal_diff_per_match_diff
recent_20_points_per_match_diff
recent_20_goal_diff_per_match_diff
recent_20_goals_for_per_match_diff
recent_20_goals_against_per_match_diff
world_cup_experience_diff
rest_days_diff
neutral_site
is_world_cup
is_qualifier
is_friendly
```

`context_calibrator` 上下文特征：

```text
base_prob_home_win
base_prob_draw
base_prob_away_win
base_log_prob_home_win
base_log_prob_draw
base_log_prob_away_win
fifa_rank_strength_diff
team_market_value_log_diff
roster_market_value_log_diff
roster_player_count_diff
player_form_coverage_diff
player_form_goals_diff
player_form_assists_diff
player_form_shots_diff
player_form_key_passes_diff
player_form_minutes_diff
coach_win_rate_diff
coach_match_count_diff
availability_impact_diff
team_stat_goals_diff
team_stat_goal_against_diff
team_stat_shots_diff
team_stat_shots_on_target_diff
team_stat_key_passes_diff
team_stat_pass_accuracy_diff
team_stat_rating_diff
team_stat_market_value_log_diff
team_stat_yellow_cards_diff
team_stat_red_cards_diff
team_stat_fouls_diff
```

默认只使用稳定球队榜指标。需要实验全部 45 项懂球帝球队榜指标时，通过 `--include-all-team-stats` 单独训练并与默认模型对比。

推理规则：

```text
两队都有上下文:
  inference_mode = context_calibrated
  calibration_applied = true

任一球队缺少上下文:
  inference_mode = history_core_fallback
  calibration_applied = false
  fallback_reason = missing_context_features

仅历史模型:
  inference_mode = history_core
```

训练命令：

```powershell
$env:PYTHONPATH="."
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
python scripts/train_small_outcome_model.py --model-mode calibrated
```

验收：

- `calibrated_model` 的 Log Loss 和 Brier Score 不低于同一测试子集的 Elo baseline。
- `history_core_full_test` 单独记录，不能和上下文子集指标混在一起比较。
- 训练产物必须保存 `feature_names`、`context_feature_count`、`metrics`、`training_notes`。
- 预测样本必须输出 `base_probabilities`、`inference_mode`、`feature_snapshot` 和来源质量字段。

### 11.3 第二阶段：LightGBM / CatBoost

输入：

```text
elo_diff
fifa_rank_diff
market_value_diff
recent_10_points_diff
recent_10_goal_diff
vs_top30_points_diff
player_form_diff
lineup_stability_diff
injury_impact_diff
coach_score_diff
rest_days_diff
travel_distance_diff
venue_advantage
weather_impact
```

输出：

```text
home_win_prob
draw_prob
away_win_prob
```

训练数据：

```text
世界杯
洲际杯
世预赛
友谊赛
```

赛事权重：

```text
世界杯：1.0
洲际杯：0.8
世预赛：0.7
友谊赛：0.4
```

评估：

```text
Log Loss
Brier Score
Calibration Curve
Top-1 Accuracy
```

进入条件：

- 已有历史赛前特征快照，或能证明每个训练样本只使用该场比赛开球前已知信息。
- 国家队名称、球员名称、球队 ID、球员 ID 映射审计通过。
- LightGBM / CatBoost 在时间切分测试集上的 Log Loss 和 Brier Score 稳定优于两层 Logistic。

### 11.4 第三阶段：概率校准

模型输出概率后必须校准：

```text
Isotonic Regression
Platt Scaling
Temperature Scaling
```

目标：

- 44% 概率的比赛长期真的接近 44% 发生。
- 不让模型过度自信。

### 11.5 赛事模拟规则

小组模拟必须使用 2026 赛制：

- 12 个小组，每组前 2 名和 8 个成绩最好的小组第三进入 32 强。
- 小组同分先比较同分球队之间的积分、净胜球、进球数。
- 仍无法区分时，比较所有小组赛净胜球、所有小组赛进球数、公平竞赛分。
- 再无法区分时，按最近发布的 FIFA 男足世界排名；仍相同则继续使用上一版 FIFA 排名，直到可区分。
- 8 个最佳第三名按全组积分、净胜球、进球数、公平竞赛分、FIFA 排名确定。
- 32 强对阵要实现 2026 附录 C 的第三名组合映射，不能沿用 32 队世界杯旧模板。

验收测试必须覆盖：

- 两队同分。
- 三队同分并在相互战绩后仍无法区分。
- 最佳第三名排序。
- 公平竞赛分。
- FIFA 排名兜底。
- 第三名组合到 32 强对阵映射。

### 11.6 时间泄漏控制

所有入模特征必须有 `as_of_at` 或 `snapshot_id`。训练样本只能读取 `as_of_at <= kickoff_at` 的快照。

当前上下文特征主要来自 2026 赛中/当前快照，因此只能用于：

- 未来未开赛比赛推理。
- 上下文校准实验。
- 在文档和模型产物中明确标记训练口径。

不能把当前球员状态、当前球队榜、当前伤停直接回填到多年历史比赛上当作当时已知事实。

## 12. AI 执行方案

### 12.1 新闻抽取 Prompt 输入

```text
新闻标题
新闻正文
发布时间
来源 URL
关联球队
关联球员候选
```

### 12.2 结构化输出

```json
{
  "event_type": "injury",
  "team": "法国",
  "player": "某球员",
  "impact_area": "defense",
  "impact_score": -2.4,
  "confidence": 0.84,
  "evidence": "新闻中提到该球员因伤缺席首战",
  "source_url": "https://example.com/news"
}
```

### 12.3 AI 风控

规则：

- 没有来源 URL 的情报不进入模型。
- confidence 低于 0.65 不进入模型。
- 核心球员伤停需要两源确认或人工确认。
- AI 解释只能基于模型结果和已入库情报。

## 13. 缓存策略

小程序高频页面全部读缓存：

```text
home:v1
match:{id}:detail
match:{id}:prediction
group:{id}:summary
rankings:champion
team:{id}:profile
```

缓存更新时间：

- 数据任务结束后主动刷新。
- API fallback 可查数据库。
- 小程序页面显示 `updated_at`。

## 14. 安全设计

### 14.1 密钥

```text
OPENAI_API_KEY
SPORTMONKS_API_KEY
API_FOOTBALL_KEY
DATABASE_URL
REDIS_URL
ADMIN_TOKEN
```

全部放服务器环境变量，不进前端，不进 Git。

### 14.2 接口安全

```text
小程序公开接口：
  基础限流
  只读

管理接口：
  管理 token
  IP 白名单
  不暴露到小程序
```

### 14.3 数据安全

```text
不存用户敏感信息
MVP 不做登录
日志不记录 API key
Raw 快照定期归档
```

## 15. 监控和运维

MVP 最少需要：

```text
服务存活检查
定时任务成功/失败日志
API 错误率
数据库备份
磁盘空间监控
OpenAI 调用失败记录
采集失败告警
```

建议：

```text
每日自动备份 PostgreSQL
保留最近 7 天
Raw 快照按天压缩
日志按天切割
```

## 16. 费用预算

MVP 年成本：

```text
云服务器 2核4G：约 199 元/年左右，视活动而定
域名：约 40 - 80 元/年
SSL：0 元
备案：0 元
对象存储：可先不用，后续几十元/年
OpenAI：按调用量，MVP 可控
商业体育 API：正式版另算，可能是最大成本
```

建议第一阶段：

```text
先买 2核4G 轻量服务器
先买 .cn 域名
先不买商业体育 API
先用公开数据 + 懂球帝补充 + 手工校验
```

## 17. 开发里程碑

### 17.1 第 0 周：准备

交付：

```text
云服务器
域名
HTTPS
GitHub 仓库
Docker Compose
数据库初始化
```

### 17.2 第 1-2 周：前端原型

交付：

```text
Taro 项目
首页
比赛详情页
小组页
预测榜
球队页
真实数据空状态
```

### 17.3 第 3 周：后端 API

交付：

```text
FastAPI 项目
PostgreSQL schema
Redis 缓存
小程序接口
真实数据入库
```

### 17.4 第 4 周：数据采集

交付：

```text
赛程采集
积分榜采集
球员榜采集
球队榜采集
raw 快照
数据归一化
```

### 17.5 第 5 周：预测链路

交付：

```text
Elo baseline
Poisson 比分模型
赛事模拟
match_predictions 入库
prediction rankings API
```

### 17.6 第 6 周：AI 情报

交付：

```text
新闻采集
AI 结构化抽取
AI 解读生成
情报置信度
数据冲突检查
```

### 17.7 第 7 周：上线准备

交付：

```text
小程序体验版
合法域名配置
备案检查
错误监控
数据备份
小范围内测
```

## 18. 风险清单

### 18.1 数据源合规

风险最高。

处理：

- 原型低频使用懂球帝。
- 正式版接授权体育 API。
- 数据源通过适配器隔离。
- 关键字段保留来源。

### 18.2 模型可信度

处理：

- 从 baseline 开始。
- 做赛后复盘。
- 做概率校准。
- 不宣传“必中”。

### 18.3 AI 幻觉

处理：

- 只做抽取和解释。
- 必须引用来源。
- 低置信度不入模。
- 关键情报人工确认。

### 18.4 小程序上线

处理：

- 提前买域名和备案。
- 所有接口走 HTTPS。
- 域名配置到微信后台。
- 前端避免浏览器专属 API。

### 18.5 服务器资源

处理：

- 预测预计算。
- 首页和详情页缓存。
- 不在用户请求时跑模型。
- 任务错峰执行。

## 19. 第一版执行建议

第一版不要追求完整自动化。建议目标：

```text
前端 5 个页面可跑
后端 API 可用
赛程和积分榜能采集
预测结果可以批量生成
AI 解读可以生成
小程序体验版能访问云端 API
```

第一版可以接受：

- 部分数据手工补齐。
- 模型先用 baseline。
- 管理后台先用脚本。
- 球员页放到第二期。
- 商业 API 后置。

第一版不应接受：

- 小程序直接请求第三方源。
- API key 放前端。
- 没有数据快照。
- 没有预测更新时间。
- 没有赛后复盘入口。
