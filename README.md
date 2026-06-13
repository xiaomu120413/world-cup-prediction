# World Cup Prediction Mini Program

世界杯预测小程序项目文档仓库。

## Project

这是一个低频更新的世界杯赛前预测与 AI 解读小程序方案。产品目标是基于赛程、球队、球员、历史战绩、新闻情报、场馆环境和预测模型，为用户提供：

- 胜平负概率
- 比分概率
- 小组出线概率
- 冠军和晋级概率
- AI 赛前报告
- 赛后预测复盘

## Docs

完整文档放在：

[docs/world-cup-prediction](./docs/world-cup-prediction)

核心文档：

- [PRD](./docs/world-cup-prediction/PRD.md)
- [Architecture](./docs/world-cup-prediction/ARCHITECTURE.md)
- [Design](./docs/world-cup-prediction/DESIGN.md)
- [Data Model](./docs/world-cup-prediction/DATA_MODEL.md)
- [API Contract](./docs/world-cup-prediction/API_CONTRACT.md)
- [Functional Design](./docs/world-cup-prediction/FUNCTIONAL_DESIGN.md)
- [Technical Execution Plan](./docs/world-cup-prediction/TECHNICAL_EXECUTION_PLAN.md)
- [Execution Checklist](./docs/world-cup-prediction/EXECUTION_CHECKLIST.md)

## Apps

- [Miniapp](./apps/miniapp): Taro React 小程序前端骨架，当前使用 mock 数据。

## Services

- [API](./services/api): FastAPI 后端骨架，当前使用 mock 数据实现接口合约。

## Status

当前阶段：M1 前端原型骨架已完成。

- 5 个核心页面已接入 mock 数据：首页、比赛详情、小组、预测榜、球队页。
- 数据模型、API 合约和功能闭环设计已补齐。
- M2 FastAPI 接口骨架已开始，先用 mock 数据跑通 API 合约。
- H5 构建、微信小程序构建和 TypeScript 检查已通过。
- 下一阶段进入 M2 后端 API 与数据模型实现。
