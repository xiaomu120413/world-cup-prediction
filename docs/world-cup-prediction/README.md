# World Cup Prediction Mini Program

Data operations quick reference:

- [DATA_SOURCE_REFRESH_SUMMARY.md](./DATA_SOURCE_REFRESH_SUMMARY.md): real-data source ownership, refresh cadence, matchday/news rules, provenance gate, concurrency rules, and acceptance checks.

世界杯预测小程序项目文档。

## 项目定位

这是一个低频更新的世界杯赛前预测小程序方案。产品不做秒级实时比分，而是基于赛程、球队、球员、历史战绩、新闻情报、场馆环境和预测模型，为用户提供赛前概率、比分预测、出线概率和 AI 解读。

核心能力：

- 世界杯比赛预测
- 胜平负概率
- 比分概率
- 小组出线和冠军概率
- 球员与球队状态分析
- AI 新闻情报抽取
- AI 预测解释
- 赛后复盘

## 文档目录

| 文档 | 说明 |
| --- | --- |
| [PRD.md](./PRD.md) | 产品需求文档，包含用户场景、功能范围、页面设计、数据需求、AI 能力和 MVP 规划 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 技术架构设计，包含数据流、服务模块、模型服务、小程序访问架构和部署建议 |
| [DESIGN.md](./DESIGN.md) | 选定的 AI 赛前报告型设计方向，包含视觉系统、页面结构、组件和交互规范 |
| [DATA_MODEL.md](./DATA_MODEL.md) | 数据模型设计，包含核心表、字段、约束、数据质量和 MVP 建表范围 |
| [API_CONTRACT.md](./API_CONTRACT.md) | API 合约设计，包含公共接口、管理接口、响应格式、错误码和 curl 示例 |
| [FUNCTIONAL_DESIGN.md](./FUNCTIONAL_DESIGN.md) | 功能设计，包含首页、比赛详情、小组、预测榜、球队页、采集、预测、AI 情报和验收点 |
| [TECHNICAL_EXECUTION_PLAN.md](./TECHNICAL_EXECUTION_PLAN.md) | 可正式执行的技术方案，包含服务器、域名、部署、模块拆解、接口、任务、模型、AI 和上线里程碑 |
| [EXECUTION_CHECKLIST.md](./EXECUTION_CHECKLIST.md) | 执行清单，包含阶段任务、交付物、验收标准、测试点、上线检查和 Done 定义 |
| [TEST_REPORT.md](./TEST_REPORT.md) | 测试报告，记录自动化测试、HTTP smoke、浏览器 smoke、已知问题和下一轮重点 |
| [archive/](./archive/) | 历史方案归档，保留早期评审版和已被后续文档替代的资料 |

## MVP 范围

第一版目标是跑通完整闭环：

```text
数据采集 -> 特征生成 -> 模型预测 -> AI 解读 -> 小程序展示 -> 赛后复盘
```

MVP 包含：

- 比赛列表
- 比赛详情
- 胜平负概率
- Top 5 比分概率
- 关键因素
- AI 解读
- 小组积分榜
- 小组出线概率

## 当前数据策略

当前实现遵循“先采集入库，再由 API 和模型读取”的原则。小程序端不直接访问外部数据源，也不在页面查询时触发采集。

已接入的数据包括：

- 懂球帝世界杯赛程、积分榜、球队页、球员名单、球员排名、球队统计、比赛场馆和赛前上下文。
- FIFA 男足排名，用于国家队排名字段校验和补齐。
- Open-Meteo 场馆天气数据。
- Sky Sports、Sports Mole 等公开新闻源，经规则抽取生成 AI 情报信号。
- 历史男子国家队比赛结果，用于 Elo、近期状态、胜平负模型和比分模型训练。

标准化数据必须带 `data_source_links` 溯源记录。缺失数据应展示为空态、低置信度或待更新状态，不写入模拟数据。

## 当前模型策略

不训练大语言模型。预测使用结构化小模型和可回测规则：

- 胜平负概率：`small_outcome` LightGBM GBDT 多分类模型，结合历史国家队比赛、Elo、近期状态、赛前上下文和球队/球员结构化特征。
- 比分分布：`scoreline` Poisson 进球模型，输出期望进球、比分概率和 Top 比分。
- 冠军/四强/黑马榜：基于淘汰赛路径、单场晋级概率、球队身价/状态特征和 Monte Carlo 模拟生成。
- 小组出线概率：按 2026 世界杯 48 队、12 组、小组前二和 8 个最佳第三名规则计算。

推理结果必须标记 `model_version`、`inference_mode`、`feature_snapshot` 和关键证据。缺失关键特征时不能把缺失值当真实特征处理。

LLM 或 AI 文本层负责：

- 新闻抽取
- 伤停识别
- 战术和教练言论解析
- 数据冲突检查
- 预测解释生成
