# 世界杯预测小程序测试报告

测试日期：2026-06-15

## 1. 测试范围

本轮覆盖 MVP 当前可运行部分：

- 后端 FastAPI 契约测试
- 后端数据库 schema / repository 查询测试
- 本地 HTTP smoke test
- Taro 小程序 TypeScript 检查
- H5 构建
- 微信小程序构建
- H5 浏览器移动端和桌面端页面 smoke
- 首页到比赛详情跳转
- 底部导航跳转

## 2. 自动化测试结果

| 测试项 | 命令 | 结果 |
| --- | --- | --- |
| 后端 pytest | `.venv\Scripts\python.exe -m pytest` | 通过，27 passed |
| 小程序类型检查 | `npm.cmd run typecheck` | 通过 |
| H5 构建 | `npm.cmd run build:h5` | 通过，有 entrypoint size warning |
| 微信小程序构建 | `npm.cmd run build:weapp` | 通过 |

## 3. HTTP Smoke Test

本地 API 地址：`http://127.0.0.1:8001`

| 接口 | 结果 |
| --- | --- |
| `GET /health` | 200 |
| `GET /api/v1/version` | 200 |
| `GET /api/v1/home` | 200 |
| `GET /api/v1/matches/today` | 200 |
| `GET /api/v1/matches/usa-paraguay-2026-06-13` | 200 |
| `GET /api/v1/matches/usa-paraguay-2026-06-13/prediction` | 200 |
| `GET /api/v1/groups` | 200 |
| `GET /api/v1/groups/group-a` | 200 |
| `GET /api/v1/predictions/rankings?type=champion` | 200 |
| `GET /api/v1/teams/france` | 200 |

## 4. 浏览器 Smoke Test

H5 预览地址：`http://127.0.0.1:4173`

移动端视口：390 x 844

| 页面 | 必要内容 | 横向溢出 | 结果 |
| --- | --- | --- | --- |
| 首页 | 今日预测、AI 简报、冠军概率 | 无 | 通过 |
| 比赛详情 | AI 赛前报告、关键证据、比分分布、出线影响 | 无 | 通过 |
| 小组页 | A组形势、积分榜、出线概率、关键赛程 | 无 | 通过 |
| 预测榜 | 预测榜、AI 榜单解读、概率排名、今日变化 | 无 | 通过 |
| 球队页 | AI 球队判断、赛事概率、核心评分、关键球员 | 无 | 通过 |

桌面视口：1280 x 720

| 页面 | 横向溢出 | 结果 |
| --- | --- | --- |
| 首页 | 无 | 通过 |
| 比赛详情 | 无 | 通过 |
| 小组页 | 无 | 通过 |
| 预测榜 | 无 | 通过 |
| 球队页 | 无 | 通过 |

交互测试：

| 交互 | 结果 |
| --- | --- |
| 首页点击“查看 AI 赛前报告” | 通过，进入比赛详情 |
| 底部导航：比赛 -> 小组 | 通过 |
| 底部导航：小组 -> 预测 | 通过 |
| 底部导航：预测 -> 球队 | 通过 |
| 底部导航：球队 -> 比赛 | 通过 |

控制台错误：未发现 error。

## 5. 本轮发现并修复的问题

| 问题 | 处理 |
| --- | --- |
| H5 浏览器标题显示乱码 | 在 `apps/miniapp/src/index.html` 增加 `<meta charset="utf-8" />` |
| 底部导航自动化定位不稳定 | 在 `BottomNav` 导航项增加 `data-testid` |
| 后端接口测试覆盖不足 | 扩展 `tests/test_contract.py`，覆盖核心公开接口 |

## 6. 已知非阻断项

- H5 构建存在 Taro entrypoint size warning，当前约 290 KiB。MVP 阶段可接受，上线前需要做包体优化。
- 后端测试在 Python 3.14 下有 FastAPI / Starlette 的弃用警告。建议生产环境使用 Python 3.12。
- Redis 已启动但业务缓存尚未接入，当前只作为 M0/M2 基础设施预留。

## 7. 数据库验证补充

测试日期：2026-06-15

本轮新增验证：

| 测试项 | 结果 |
| --- | --- |
| `docker compose up -d postgres redis` | 通过，PostgreSQL 和 Redis 均 healthy |
| `alembic upgrade head` | 通过，迁移到 `202606130001` |
| `python scripts/init_db.py` | 通过，schema 幂等执行，不插入 seed 数据 |
| `RUN_DATABASE_TESTS=1 python -m pytest` | 通过，30 passed |
| 临时 `DATA_BACKEND=database` API HTTP smoke | 通过 |

数据库模式 HTTP smoke：

| 接口 | 结果 |
| --- | --- |
| `GET /health` | 200 |
| `GET /api/v1/matches/usa-paraguay-2026-06-13` | 200 |
| `GET /api/v1/matches/usa-paraguay-2026-06-13/prediction` | 200 |
| `GET /api/v1/teams` | 200 |

## 8. 小程序 API 模式验证

测试日期：2026-06-15

本轮新增验证：

| 测试项 | 结果 |
| --- | --- |
| `TARO_APP_API_BASE_URL=http://127.0.0.1:8001 npm.cmd run build:h5` | 通过 |
| H5 首页 API 模式 smoke | 通过 |
| H5 比赛详情 API 模式 smoke | 通过 |
| H5 小组页 API 模式 smoke | 通过 |
| H5 预测榜 API 模式 smoke | 通过 |
| H5 球队页 API 模式 smoke | 通过 |
| API 模式浏览器 console error | 未发现 |

本轮发现并修复：

| 问题 | 处理 |
| --- | --- |
| H5 运行时保留 `process.env.TARO_APP_API_BASE_URL` 导致页面空白 | 改为 Taro `defineConstants` 注入 `__API_BASE_URL__` |
| API 返回 `medium` 直接展示到首页 | 增加信心标签中文映射 |

## 9. 下一轮测试重点

- 将首页、小组、预测榜更多接口逐步切到 repository 读库。
- 接入 Redis 缓存降级测试。
- 补接口失败、空状态、超时状态自动化测试。
- 微信开发者工具真机预览。

## Backend Database Route Coverage Retest

Test date: 2026-06-15

| Test item | Result |
| --- | --- |
| `python scripts/init_db.py` with PostgreSQL on `127.0.0.1:54321` | Passed |
| `RUN_DATABASE_TESTS=1 python -m pytest` | Passed, 33 tests |
| Database route coverage | Home, matches, rankings, groups, teams |
| Seed repeatability | Ranking, group standing, and group simulation seed rows are idempotent |

## Backend Redis Cache Smoke

Test date: 2026-06-15

| Test item | Result |
| --- | --- |
| `CACHE_ENABLED=true` API startup on port 8002 | Passed |
| `GET /api/v1/home` | 200 |
| `GET /api/v1/predictions/rankings?type=champion` | 200 |
| `GET /api/v1/groups/group-a` | 200 |
| Redis key write check | Passed for `public:home:default:Asia/Shanghai`, `public:rankings:champion:20`, `public:groups:group-a` |

## Baseline Prediction Recompute Smoke

Test date: 2026-06-15

| Test item | Result |
| --- | --- |
| `RUN_DATABASE_TESTS=1 python -m pytest` | Passed, 38 tests |
| `python scripts/recompute_predictions.py --scope matchday --match-id usa-paraguay-2026-06-13 --seed 20260615` | Passed |
| `POST /api/admin/predictions/recompute` in database mode | 200, `status=completed` |
| Outputs written | Match prediction, scorelines, rankings, group simulations |

## Collector Framework Smoke

Test date: 2026-06-15

| Test item | Result |
| --- | --- |
| `RUN_DATABASE_TESTS=1 python -m pytest` | Passed, 41 tests |
| `python scripts/run_collector.py --source dongqiudi --source-type homepage --dry-run` | Passed |
| `POST /api/admin/collectors/run` in database mode | 200, `status=completed` |
| Idempotency check | Repeated schedule collector run did not duplicate `raw_snapshots` |

## Dongqiudi Collector Smoke

Test date: 2026-06-15

| Test item | Result |
| --- | --- |
| `RUN_DATABASE_TESTS=1 python -m pytest` | Passed, 45 tests |
| `python scripts/run_collector.py --source dongqiudi --source-type homepage --dry-run` | Passed, 39 candidate items |
| `python scripts/run_collector.py --source dongqiudi --source-type homepage` | Passed, raw snapshot written |
| `news_items` normalization | Passed, latest smoke wrote 24 candidate news items |
| Source URL | `https://pc.dongqiudi.com/` |

## Canonical Collector Normalization Smoke

Test date: 2026-06-15

| Test item | Result |
| --- | --- |
| `python -m pytest tests/test_collectors.py` | Passed, 8 tests |
| `python -m pytest` | Passed, 39 passed / 13 skipped |
| `RUN_DATABASE_TESTS=1 python -m pytest tests/test_database_backend.py` | Passed, 13 tests |
| `python scripts/run_collector.py --source thestatsapi --source-type fixtures --dry-run` | Passed |
| `python scripts/run_collector.py --source dongqiudi --source-type world_cup_standings --dry-run` | Passed |
| `python scripts/run_collector.py --source dongqiudi --source-type world_cup_player_rankings --dry-run` | Passed |
| Canonical tables verified | Real-source rows only; blocked source audit remains `0` |
| Concurrent same collector job | Passed, advisory transaction lock prevents duplicate `group_standings` rows |

Implementation notes:

- Collector snapshots now normalize into canonical `teams`, `team_aliases`, `matches`, `group_standings`, `players`, and `player_form_snapshots`.
- Same `source/source_type` collector writes are serialized with PostgreSQL advisory transaction locks.
- Raw snapshot uniqueness remains checksum-based; canonical writes are still executed for existing snapshots so upgraded normalizers can backfill missing canonical rows.
