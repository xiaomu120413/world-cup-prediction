# 世界杯预测小程序执行清单

版本：v0.1  
更新时间：2026-06-15
用途：用于正式执行、排期、验收和测试。

## 1. 执行原则

第一版目标不是做全功能平台，而是交付一个能真实跑通的 MVP：

```text
小程序页面可访问
后端 API 可用
数据能低频更新
预测能批量生成
AI 解读能生成
结果能展示
赛后能复盘
```

第一版必须坚持：

- 小程序不直接请求第三方数据源。
- 小程序不保存任何 API key。
- 预测结果预计算，不在用户打开页面时实时跑模型。
- 所有预测必须显示更新时间。
- 所有 AI 情报必须保留来源和置信度。
- 所有核心页面必须有加载、空状态、错误状态。

## 2. 版本目标

### 2.1 MVP v0.1 范围

必须包含：

```text
首页
比赛详情页
小组页
预测榜
球队页
后端 API
PostgreSQL 数据库
Redis 缓存
数据采集任务
Baseline 预测任务
AI 解读任务
小程序体验版
```

暂不包含：

```text
用户登录
评论社区
付费
实时比分直播
复杂管理后台
完整商业 API 接入
完整球员页
```

## 3. 里程碑总览

| 阶段 | 名称 | 目标 | 验收结果 |
| --- | --- | --- | --- |
| M0 | 基础设施 | 服务器、域名、HTTPS、仓库、数据库准备完成 | 小程序可请求测试 API |
| M1 | 前端原型 | 5 个核心页面用 mock 数据跑通 | 可在 H5 和微信开发者工具预览 |
| M2 | 后端 API | 小程序所需 API 可返回稳定数据 | API 文档和接口测试通过 |
| M3 | 数据采集 | 赛程、积分榜、球员榜可低频入库 | 采集任务可重复运行 |
| M4 | 预测链路 | Baseline 预测、比分概率、出线模拟可生成 | 每场比赛有预测结果 |
| M5 | AI 情报 | 新闻抽取和 AI 解读可入库展示 | 比赛详情有 AI 报告 |
| M6 | 小程序联调 | 小程序从后端读取真实数据 | 体验版可完整浏览 |
| M7 | 上线准备 | 监控、备份、审核材料、验收完成 | 可提交微信审核 |

### 3.1 当前执行状态

截至 2026-06-15：

| 阶段 | 状态 | 说明 |
| --- | --- | --- |
| M1 | 已完成前端骨架 | `apps/miniapp` 已实现 5 个核心页面、mock 数据、通用组件和底部导航。 |
| M1 验证 | 已通过 | `npm run typecheck`、`npm run build:h5`、`npm run build:weapp` 已通过。 |
| M1 视觉 QA | 已通过 | 390 x 844 视口下检查首页、比赛详情、小组、预测榜、球队页，无横向溢出。 |
| M2 设计 | 已完成 | `DATA_MODEL.md`、`API_CONTRACT.md`、`FUNCTIONAL_DESIGN.md` 已定义数据表、接口合约和功能闭环。 |
| M2 API 骨架 | 已完成 | `services/api` 已提供 FastAPI 骨架、mock 数据接口、OpenAPI 文档和契约测试。 |
| M2 数据库 | 进行中 | `services/api/db` 已提供初始 PostgreSQL schema 和 mock seed；`services/api/alembic`、SQLAlchemy 元数据、初始化脚本、Docker Compose 已接入。`matches`、`predictions`、`teams` 已通过 PostgreSQL 读库集成测试，默认仍使用 mock。 |
| M6 小程序联调 | 已开始 | `apps/miniapp/src/services/data.ts` 已接入 API service 层，支持 `TARO_APP_API_BASE_URL` 从 mock 切后端 API；H5 API 模式 smoke 已通过。 |

## 4. M0 基础设施

### 4.1 任务清单

| ID | 任务 | 交付物 |
| --- | --- | --- |
| M0-01 | 购买云服务器 | 2核4G 轻量服务器 |
| M0-02 | 购买域名 | 一个可备案域名 |
| M0-03 | 完成备案 | ICP 备案通过 |
| M0-04 | 配置 DNS | `api.xxx.cn` 指向服务器 |
| M0-05 | 配置 HTTPS | API 域名 HTTPS 可访问 |
| M0-06 | 初始化服务器 | Docker、Nginx、Git、基础安全配置 |
| M0-07 | 配置数据库 | PostgreSQL 可访问 |
| M0-08 | 配置 Redis | Redis 可访问 |
| M0-09 | 配置环境变量 | `.env` / server env 完成 |
| M0-10 | 创建健康检查接口 | `GET /health` |

### 4.2 验收标准

必须满足：

- `https://api.xxx.cn/health` 返回 `200`。
- HTTPS 证书有效。
- 服务器重启后服务能自动恢复。
- PostgreSQL 容器或服务正常运行。
- Redis 容器或服务正常运行。
- `.env` 不提交到 Git。
- 微信小程序后台可以配置 `https://api.xxx.cn` 为 request 合法域名。

### 4.3 测试点

```text
curl https://api.xxx.cn/health
curl https://api.xxx.cn/api/v1/version
docker ps
docker compose restart
psql 连接测试
redis-cli ping
SSL Labs / 浏览器证书检查
```

### 4.4 阻塞条件

以下任一未完成，不进入 M1/M2 联调：

- 域名无法 HTTPS 访问。
- 服务器无法稳定访问。
- 数据库无法持久化。
- 环境变量未配置。

## 5. M1 前端原型

### 5.1 技术任务

| ID | 任务 | 交付物 |
| --- | --- | --- |
| M1-01 | 初始化 Taro 项目 | `apps/miniapp` |
| M1-02 | 配置 TypeScript 和基础样式 | 可编译 |
| M1-03 | 建立 mock 数据 | `src/services/mock.ts` |
| M1-04 | 实现底部导航 | 比赛 / 小组 / 预测 / 球队 |
| M1-05 | 实现首页 | 今日比赛、AI 简报、冠军概率 |
| M1-06 | 实现比赛详情页 | AI 报告、概率、比分、证据 |
| M1-07 | 实现小组页 | 积分榜、出线概率、关键赛程 |
| M1-08 | 实现预测榜 | 冠军 / 四强 / 黑马 |
| M1-09 | 实现球队页 | 球队评分、状态、关键球员、风险 |
| M1-10 | 实现通用状态 | loading / empty / error |

### 5.2 前端组件清单

必须实现：

```text
ProbabilitySummary
AIReportCard
EvidenceList
ScorelineDistribution
QualificationImpact
TeamRatingPanel
MatchRow
PredictionRankingList
GroupStandingTable
BottomNav
StatusView
```

### 5.3 验收标准

页面验收：

- 首页能展示今日重点比赛。
- 比赛详情能展示胜平负概率、AI 解读、证据列表、比分分布。
- 小组页能展示积分榜和出线概率。
- 预测榜能切换冠军、四强、黑马。
- 球队页能展示球队评分、近期状态、关键球员和风险提醒。
- 所有页面在 390px 宽度下无明显文字重叠。
- 页面跳转路径可用。
- 所有核心页面有 mock 数据。
- 所有接口异常场景有兜底 UI。

视觉验收：

- 视觉方向符合 `DESIGN.md`。
- 不出现博彩化文案。
- 重点概率清晰可读。
- AI 解读和证据分层清晰。
- 底部导航状态明确。

### 5.4 测试点

```text
npm run dev:h5
npm run dev:weapp
微信开发者工具打开 dist
页面跳转测试
390x844 截图检查
320px 宽度兼容检查
长球队名兼容检查
空列表状态检查
接口错误状态检查
```

### 5.5 不通过示例

以下任一出现，前端验收不通过：

- 概率数字被截断。
- 长中文文案溢出。
- 页面依赖浏览器 `window` 导致小程序编译失败。
- 使用 React Router。
- 小程序端编译报错。
- 页面没有 loading/error 状态。

## 6. M2 后端 API

### 6.1 技术任务

| ID | 任务 | 交付物 |
| --- | --- | --- |
| M2-01 | 初始化 FastAPI 项目 | `services/api` |
| M2-02 | 配置 PostgreSQL 连接 | 数据库连接池 |
| M2-03 | 配置 Redis 连接 | 缓存读写 |
| M2-04 | 建立 Alembic 迁移 | 初始 schema |
| M2-05 | 实现首页 API | `GET /api/v1/home` |
| M2-06 | 实现比赛 API | matches 相关接口 |
| M2-07 | 实现小组 API | groups 相关接口 |
| M2-08 | 实现预测榜 API | rankings 相关接口 |
| M2-09 | 实现球队 API | teams 相关接口 |
| M2-10 | 实现统一错误格式 | error response |
| M2-11 | 生成 OpenAPI 文档 | `/docs` |

### 6.2 必须接口

```text
GET /health
GET /api/v1/version
GET /api/v1/home
GET /api/v1/matches/today
GET /api/v1/matches/{match_id}
GET /api/v1/matches/{match_id}/prediction
GET /api/v1/groups
GET /api/v1/groups/{group_id}
GET /api/v1/groups/{group_id}/simulation
GET /api/v1/predictions/rankings?type=champion
GET /api/v1/predictions/rankings?type=semifinal
GET /api/v1/predictions/rankings?type=darkhorse
GET /api/v1/teams/{team_id}
```

### 6.3 响应规范

成功：

```json
{
  "data": {},
  "meta": {
    "updated_at": "2026-06-13T18:00:00+08:00",
    "version": "v1"
  }
}
```

失败：

```json
{
  "error": {
    "code": "MATCH_NOT_FOUND",
    "message": "比赛不存在"
  }
}
```

### 6.4 验收标准

- 所有必须接口返回 200 或明确业务错误。
- OpenAPI 页面可访问。
- 数据库迁移可从空库执行成功。
- API 不依赖本地文件路径。
- API 读取不到预测时返回明确空状态，而不是 500。
- 首页接口 P95 响应时间小于 500ms。
- 比赛详情接口 P95 响应时间小于 800ms。

### 6.5 测试点

```text
pytest
ruff / black
curl /api/v1/home
curl /api/v1/matches/{id}/prediction
数据库空表测试
Redis 不可用降级测试
错误 match_id 测试
并发 20 请求 smoke test
```

## 7. M3 数据采集

### 7.1 技术任务

| ID | 任务 | 交付物 |
| --- | --- | --- |
| M3-01 | 设计数据源适配器接口 | `BaseAdapter` |
| M3-02 | 实现懂球帝赛程采集 | schedule collector |
| M3-03 | 实现懂球帝积分榜采集 | standing collector |
| M3-04 | 实现懂球帝球员榜采集 | person ranking collector |
| M3-05 | 实现 raw 快照保存 | `raw_snapshots` |
| M3-06 | 实现球队映射 | `team_aliases` |
| M3-07 | 实现球员映射 | `player_aliases` |
| M3-08 | 实现采集运行日志 | `collector_runs` |
| M3-09 | 实现重复运行幂等 | 不重复插入脏数据 |
| M3-10 | 实现手动触发脚本 | CLI |

### 7.2 验收标准

- 能采集世界杯赛程并入库。
- 能采集积分榜并入库。
- 能采集至少 5 类球员榜：进球、助攻、射门、关键传球、评分。
- 每次采集保存 raw 快照。
- 同一个采集任务重复运行不会生成重复比赛。
- 采集失败会记录失败原因。
- 数据源返回异常时不会导致整个任务崩溃。

### 7.3 测试点

```text
python -m jobs.collect schedule
python -m jobs.collect standings
python -m jobs.collect person_rankings --type goals
重复执行同一采集任务
断网/超时模拟
错误 JSON 模拟
raw_snapshots 数量检查
matches 数量检查
collector_runs 状态检查
```

### 7.4 数据质量检查

必须检查：

```text
match_id 不为空
team_A_id/team_B_id 不为空
start_time 可解析
status 可标准化
积分榜球队数符合预期
球员榜 person_id 不为空
```

## 8. M4 预测链路

### 8.1 技术任务

| ID | 任务 | 交付物 |
| --- | --- | --- |
| M4-01 | 导入历史国家队比赛 | historical_matches |
| M4-02 | 实现 Elo 计算 | team_elo |
| M4-03 | 实现近期状态特征 | recent form |
| M4-04 | 实现基础特征表 | model_features |
| M4-05 | 实现 Poisson 比分模型 | expected goals |
| M4-06 | 实现胜平负 baseline | prediction baseline |
| M4-07 | 实现比分概率 | Top scorelines |
| M4-08 | 实现小组模拟 | group simulation |
| M4-09 | 实现冠军模拟 | tournament simulation |
| M4-10 | 保存模型版本 | model_versions |

### 8.2 MVP 预测输入

第一版最少特征：

```text
elo_diff
fifa_rank_diff
recent_10_points_diff
recent_10_goal_diff
market_value_diff
injury_impact_diff
rest_days_diff
venue_advantage
```

### 8.3 MVP 预测输出

```text
home_win_prob
draw_prob
away_win_prob
home_expected_goals
away_expected_goals
top_scorelines
key_factors
```

### 8.4 验收标准

- 任意一场未开赛比赛可以生成预测。
- 三个胜平负概率相加等于 1，误差小于 0.001。
- 期望进球为正数且合理，默认范围 0 到 5。
- Top 5 比分概率可生成。
- 小组出线概率可生成。
- 冠军概率榜可生成。
- 每次预测保存 `model_version_id`。
- 预测结果保存 `snapshot_id`。

### 8.5 测试点

```text
pytest tests/model
概率和为 1 测试
极端强弱队测试
空伤停数据测试
缺少市场身价测试
重复预测幂等测试
Monte Carlo 固定随机种子测试
历史回测 smoke test
```

### 8.6 模型质量底线

MVP 不要求预测多准，但必须：

- 结果不随机。
- 结果可复现。
- 结果可解释。
- 结果不出现明显荒谬概率。

明显荒谬示例：

```text
强队 vs 极弱队，强队胜率低于 20%
平局概率高于 70%
期望进球超过 8
比分 Top 5 概率为空
```

## 9. M5 AI 情报

### 9.1 技术任务

| ID | 任务 | 交付物 |
| --- | --- | --- |
| M5-01 | 新闻表设计 | `news_items` |
| M5-02 | 新闻采集 | news collector |
| M5-03 | AI 抽取 prompt | extraction prompt |
| M5-04 | AI 结构化输出 schema | JSON schema |
| M5-05 | 情报入库 | `ai_insights` |
| M5-06 | 情报置信度过滤 | confidence gate |
| M5-07 | AI 解读生成 | `ai_explanations` |
| M5-08 | 数据冲突检查 | conflict detector |
| M5-09 | 管理端人工确认脚本 | confirm insight |

### 9.2 AI 情报 Schema

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

### 9.3 验收标准

- AI 抽取结果必须是合法 JSON。
- 每条情报必须有 `source_url`。
- confidence 低于 0.65 的情报不进入模型特征。
- AI 解读只能引用已入库的预测和情报。
- 没有新闻时也能生成基础模型解读。
- AI 调用失败时，比赛详情仍能展示模型预测。

### 9.4 测试点

```text
固定新闻样本抽取测试
无关新闻过滤测试
伤停新闻抽取测试
教练言论抽取测试
低置信度过滤测试
OpenAI 超时模拟
非法 JSON 修复测试
无新闻 fallback 测试
```

## 10. M6 小程序联调

### 10.1 技术任务

| ID | 任务 | 交付物 |
| --- | --- |
| M6-01 | service 层从 mock 切 API | `services/api.ts` |
| M6-02 | 配置环境 API base URL | dev/prod |
| M6-03 | 微信开发者工具联调 | 体验版 |
| M6-04 | 配置 request 合法域名 | 小程序后台 |
| M6-05 | 页面错误兜底 | 全页面 |
| M6-06 | 分享卡片基础支持 | match share |
| M6-07 | 性能优化 | 首屏加载 |

### 10.2 验收标准

- 小程序体验版能访问云端 API。
- 首页真实接口展示成功。
- 比赛详情真实接口展示成功。
- 小组页真实接口展示成功。
- 预测榜真实接口展示成功。
- 球队页真实接口展示成功。
- 网络断开时显示错误状态。
- 接口返回空数据时显示空状态。
- 分享比赛详情能打开正确页面。

### 10.3 测试点

```text
微信开发者工具预览
真机预览
弱网模式
断网模式
接口 500 模拟
接口超时模拟
分享路径测试
缓存刷新测试
```

## 11. M7 上线准备

### 11.1 上线任务

| ID | 任务 | 交付物 |
| --- | --- | --- |
| M7-01 | 小程序名称和类目确认 | 微信后台配置 |
| M7-02 | 合法域名配置 | request 域名 |
| M7-03 | 隐私和用户协议 | 文档 |
| M7-04 | 服务器监控 | health check |
| M7-05 | 数据库备份 | backup job |
| M7-06 | 日志切割 | logrotate |
| M7-07 | 关键任务告警 | collector/model/ai |
| M7-08 | 审核前完整测试 | test report |
| M7-09 | 提交微信审核 | 审核版本 |

### 11.2 上线验收标准

- 体验版完整流程通过。
- 生产 API HTTPS 可访问。
- 备案和合法域名配置完成。
- 数据库每日备份可用。
- 后端重启后服务自动恢复。
- 所有核心接口有日志。
- 数据采集失败可发现。
- 页面没有博彩化文案。
- 页面没有诱导下注内容。

### 11.3 审核风险检查

必须检查：

```text
不出现下注、盘口、赔率推荐等文案
不提供博彩链接
不提供付费预测
不宣称必中
所有预测使用概率表达
用户可看到更新时间
AI 结果不冒充官方结论
```

## 12. 端到端验收用例

### 12.1 首页用例

步骤：

```text
打开小程序
进入首页
查看今日重点
点击查看 AI 赛前报告
```

期望：

```text
首页 2 秒内展示
今日重点有比赛
概率显示正常
点击后进入比赛详情
```

### 12.2 比赛详情用例

步骤：

```text
进入美国 vs 巴拉圭详情
查看胜平负概率
查看比分分布
查看证据列表
查看出线影响
```

期望：

```text
概率和为 100%
比分 Top 5 不为空
证据列表不少于 3 条
AI 解读不为空
显示更新时间
```

### 12.3 小组页用例

步骤：

```text
进入 A 组
查看积分榜
查看出线概率
切换 B 组
```

期望：

```text
A 组球队数正确
每队有积分
每队有出线概率
切换小组成功
```

### 12.4 预测榜用例

步骤：

```text
进入预测榜
查看冠军概率
切换四强
切换黑马
点击法国
```

期望：

```text
榜单不为空
概率条显示正常
切换 tab 正常
点击球队进入球队页
```

### 12.5 球队页用例

步骤：

```text
进入法国队页
查看 AI 判断
查看核心评分
查看关键球员
查看风险提醒
```

期望：

```text
球队基础信息完整
核心评分 0-10 范围内
关键球员列表不为空
风险提醒可为空但不能报错
```

### 12.6 赛后复盘用例

步骤：

```text
比赛结束
执行赛后任务
再次进入比赛详情
```

期望：

```text
显示实际比分
显示赛前预测
显示预测是否命中方向
显示复盘摘要
小组概率已重算
```

## 13. 回归测试清单

每次发布前执行：

```text
前端编译 H5
前端编译 weapp
后端 pytest
数据库迁移测试
采集任务 smoke test
预测任务 smoke test
AI fallback test
接口 smoke test
小程序真机预览
核心页面截图检查
```

## 14. 发布检查表

发布前确认：

```text
[ ] GitHub main 最新
[ ] 生产环境变量已配置
[ ] 数据库已备份
[ ] 后端镜像构建成功
[ ] 数据库迁移执行成功
[ ] API /health 正常
[ ] 小程序 API base URL 指向生产
[ ] request 合法域名已配置
[ ] 首页接口正常
[ ] 比赛详情接口正常
[ ] 预测任务成功
[ ] AI 解读任务成功或 fallback 正常
[ ] 日志无大量错误
[ ] 微信体验版可访问
```

## 15. Done 定义

MVP v0.1 完成必须同时满足：

```text
1. 小程序体验版可打开
2. 5 个核心页面可访问
3. 后端 API 部署在 HTTPS 域名下
4. 赛程和积分榜可低频采集
5. 至少 10 场比赛可生成预测
6. 比赛详情有 AI 解读或 fallback 解读
7. 小组页有出线概率
8. 预测榜有冠军概率
9. 球队页有球队评分
10. 赛后任务可生成复盘
11. 核心接口有测试
12. 发布检查表全部通过
```
## Backend Database Route Coverage Update

Update date: 2026-06-15

- `DATA_BACKEND=database` now covers home, matches today, match detail, match prediction, teams, team detail, team profile, team matches, prediction rankings, groups, group detail, and group simulation.
- PostgreSQL seed data now includes ranking predictions, group standings, and group simulation rows for the local baseline.
- Routes keep mock fallback for API areas where detailed content has not been collected yet.
- Backend verification: `RUN_DATABASE_TESTS=1 python -m pytest` passed with 33 tests.
