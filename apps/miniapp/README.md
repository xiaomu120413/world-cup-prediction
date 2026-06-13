# World Cup Prediction Miniapp

Taro React 小程序前端骨架，当前阶段使用 `src/services/mock.ts` 中的 mock 数据。

## Pages

- `pages/matches/index`: 首页比赛简报
- `pages/match-detail/index`: AI 赛前报告
- `pages/groups/index`: 小组形势
- `pages/predictions/index`: 预测榜
- `pages/team-detail/index`: 球队详情

## Commands

```bash
npm install
npm run typecheck
npm run build:h5
npm run build:weapp
```

本地 H5 静态预览可以在构建后执行：

```bash
cd dist
python -m http.server 4173
```

然后访问：

```text
http://127.0.0.1:4173
```

微信开发者工具导入路径：

```text
apps/miniapp/dist-weapp
```

## QA

本轮检查记录见 [design-qa.md](./design-qa.md)。

已知事项：

- H5 构建当前有 Taro 默认 entrypoint size warning，M1 阶段不阻塞。
- 依赖安装后 `npm audit` 会报告 Taro/webpack 依赖链上的安全提示，后续基础设施加固阶段统一评估升级。
