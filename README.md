# 小木绿茵手记

世界杯赛程、球队资料、AI 赛前解读和预测概率小程序。项目采用“数据采集入库 -> 特征生成 -> 模型预测 -> API 缓存 -> 小程序展示”的链路，小程序端只读后端接口，不直接抓取外部数据源。

当前线上 API：

```text
https://api.worldcupai-mu.cn
```

## 当前状态

- 前端：Taro + React + TypeScript，支持微信小程序和 H5 预览。
- 后端：FastAPI + PostgreSQL + Redis，公共接口默认读取数据库。
- 部署：Docker Compose 运行 API、PostgreSQL、Redis、Caddy。
- 数据：比赛、积分榜、球队、球员、身价、场馆、天气、新闻和历史国家队比赛数据先入库，再供 API 和模型读取。
- 模型：胜平负使用 LightGBM GBDT 小模型；比分使用 Poisson 进球模型；冠军/四强/黑马使用淘汰赛路径 Monte Carlo 模拟和历史回测参数。
- 审计：真实数据审计和覆盖率审计必须通过后，才认为当前数据可用于小程序展示。

## 目录结构

| 路径 | 说明 |
| --- | --- |
| [apps/miniapp](./apps/miniapp) | Taro 小程序/H5 前端 |
| [services/api](./services/api) | FastAPI 后端、数据库模型、采集脚本、特征和预测服务 |
| [deploy/production](./deploy/production) | 生产 Docker Compose、Caddy、systemd 刷新任务配置 |
| [docs/world-cup-prediction](./docs/world-cup-prediction) | 产品、架构、数据、API、部署和测试文档 |
| [docs/world-cup-prediction/archive](./docs/world-cup-prediction/archive) | 历史方案归档 |

## 核心链路

```text
外部公开数据源
  -> raw_snapshots / data_source_links
  -> 标准表：matches / teams / players / standings / news / features
  -> model_features / match_predictions / ranking_predictions
  -> Redis/API 缓存
  -> 微信小程序/H5 页面
```

公共页面只读 API，不在页面请求时触发采集、训练或外部站点访问。

## 数据来源

当前已接入和整理的数据包括：

- 懂球帝世界杯赛程、积分榜、球队页、球员名单、球员排名、球队统计、比赛场馆和赛前上下文。
- FIFA 男足排名，用于国家队排名字段校验和补齐。
- Open-Meteo 场馆天气数据。
- Sky Sports、Sports Mole 等公开新闻源，经规则抽取生成 AI 情报信号。
- 历史男子国家队比赛结果，用于 Elo、近期状态、胜平负模型和比分模型训练。

所有标准化数据都要求有 `data_source_links` 溯源记录。缺失数据应显示为空态或低置信度状态，不写入模拟数据。

## 模型

当前预测链路：

- `small_outcome`：LightGBM 多分类胜平负模型，使用历史国家队比赛、Elo、近期状态、赛前上下文和球队/球员结构化特征。
- `scoreline`：Poisson 进球模型，输出比分分布、期望进球和 Top 比分。
- `ranking_predictions`：基于已知淘汰赛路径、单场晋级概率、球队身价/状态特征和 Monte Carlo 模拟生成冠军、四强、黑马榜。
- `group_simulation`：按 2026 世界杯 48 队、12 组、前二和 8 个最佳第三名规则计算小组晋级概率。

LLM 不直接预测胜负，只负责新闻理解、情报抽取和解释文本生成。

## 本地开发

启动本地 PostgreSQL 和 Redis：

```powershell
cd services/api
docker compose up -d postgres redis
```

启动 API：

```powershell
cd services/api
$env:DATA_BACKEND="database"
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
$env:REDIS_URL="redis://127.0.0.1:63791/0"
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

H5 预览：

```powershell
cd apps/miniapp
$env:TARO_APP_API_BASE_URL="http://127.0.0.1:8001"
npm.cmd run build:h5
cd dist
python -m http.server 4173
```

打开：

```text
http://127.0.0.1:4173
```

微信小程序正式构建：

```powershell
cd apps/miniapp
npm.cmd run build:weapp:release
```

真实 AppID 放在 `apps/miniapp/project.private.config.json` 或环境变量中，不要提交到 Git。

## 数据刷新

刷新任务通过 `services/api/scripts/run_refresh_schedule.py` 执行，生产环境由 systemd timer 调度。

常用本地命令：

```powershell
cd services/api
$env:PYTHONPATH="."
$env:DATABASE_URL="postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
python scripts/run_refresh_schedule.py --cadence daily_00 --dry-run
python scripts/run_refresh_schedule.py --cadence daily_12
python scripts/run_refresh_schedule.py --cadence post_match
python scripts/run_refresh_schedule.py --cadence pre_match_90m
python scripts/audit_real_data.py
```

刷新策略详见 [DATA_SOURCE_REFRESH_SUMMARY.md](./docs/world-cup-prediction/DATA_SOURCE_REFRESH_SUMMARY.md) 和 [DATA_REFRESH_POLICY.md](./docs/world-cup-prediction/DATA_REFRESH_POLICY.md)。

## 测试

后端轻量测试：

```powershell
cd services/api
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe -m pytest tests/test_collectors.py tests/test_refresh_scheduler.py tests/test_repository_queries.py tests/test_prediction_rankings.py tests/test_ai_news_insights.py
```

前端类型检查：

```powershell
cd apps/miniapp
npm.cmd run typecheck
```

## 生产部署

生产目录：

```text
/opt/world-cup-prediction
```

启动或更新服务：

```bash
cd /opt/world-cup-prediction/deploy/production
docker compose --env-file .env.prod up -d
```

健康检查：

```bash
curl https://api.worldcupai-mu.cn/health
curl https://api.worldcupai-mu.cn/api/v1/data-status
```

部署细节见 [deploy/production/README.md](./deploy/production/README.md)。

## 文档入口

- [项目文档总览](./docs/world-cup-prediction/README.md)
- [技术架构](./docs/world-cup-prediction/ARCHITECTURE.md)
- [数据模型](./docs/world-cup-prediction/DATA_MODEL.md)
- [API 合约](./docs/world-cup-prediction/API_CONTRACT.md)
- [数据采集接口](./docs/world-cup-prediction/DATA_ACQUISITION_INTERFACES.md)
- [数据刷新策略](./docs/world-cup-prediction/DATA_REFRESH_POLICY.md)
- [测试报告](./docs/world-cup-prediction/TEST_REPORT.md)
