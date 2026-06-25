# World Cup Prediction Miniapp

Taro React mini program and H5 frontend for the World Cup prediction product.

API builds should set `TARO_APP_API_BASE_URL`; when the API is configured, pages read the backend directly and API failures are surfaced instead of silently falling back to local fixtures.

## Pages

- `pages/matches/index`: match schedule and home dashboard
- `pages/match-detail/index`: AI pre-match report
- `pages/groups/index`: group standings and qualification probabilities
- `pages/predictions/index`: prediction rankings
- `pages/team-detail/index`: team analysis

## Commands

```bash
npm install
npm run typecheck
npm run build:h5
npm run build:weapp
```

API-linked H5 build:

```powershell
$env:TARO_APP_API_BASE_URL="http://127.0.0.1:8001"
npm.cmd run build:h5
```

API-linked WeChat mini program build:

```powershell
$env:TARO_APP_API_BASE_URL="http://127.0.0.1:8001"
npm.cmd run build:weapp
```

Release WeChat mini program build:

```powershell
$env:TARO_APP_API_BASE_URL="https://api.worldcupai-mu.cn"
$env:TARO_APP_WEAPP_APPID="<your-wechat-mini-program-appid>"
npm.cmd run build:weapp:release
```

Do not commit the real AppID. For local WeChat DevTools usage, copy
`project.private.config.example.json` to `project.private.config.json` and put
the real AppID there, or provide it through `TARO_APP_WEAPP_APPID` / `WEAPP_APPID`.
`project.private.config.json` is ignored by Git.

Local H5 static preview after build:

```bash
cd dist
python -m http.server 4173
```

Open:

```text
http://127.0.0.1:4173
```

WeChat DevTools import path for preview/upload:

```text
apps/miniapp/dist-weapp
```

Importing `apps/miniapp` also works because the root `project.config.json` points
WeChat DevTools to `dist-weapp`, but direct `dist-weapp` import avoids scanning
local development folders such as `node_modules` and is safer when DevTools
reports `EMFILE: too many open files`.

## WeChat API domain

Use different API domains for local debug and release:

- Local H5: `http://127.0.0.1:8001`.
- WeChat DevTools debug: use the local API only with DevTools domain checks disabled.
- Release and preview builds: use `https://api.worldcupai-mu.cn`.

Before uploading a preview or release build, add the API origin to the WeChat
Mini Program admin console:

```text
WeChat public platform -> Development -> Development Settings -> Server Domains -> request legal domain
```

Only the origin needs to be configured. If the frontend uses
`https://api.worldcupai-mu.cn/api/v1/matches`, configure `https://api.worldcupai-mu.cn`.
Do not use `127.0.0.1`, `localhost`, plain HTTP, or an unregistered temporary
domain for release builds.

For this project, configure these DNS records before release:

```text
api.worldcupai-mu.cn     A record     47.122.125.7
static.worldcupai-mu.cn  A record     47.122.125.7
```

Then configure these WeChat legal domains:

```text
request legal domain: https://api.worldcupai-mu.cn
downloadFile legal domain: https://static.worldcupai-mu.cn
```

`npm run build:weapp:release` enforces this by requiring:

- `TARO_APP_API_BASE_URL` to be a public `https://` URL.
- `TARO_APP_WEAPP_APPID`, `WEAPP_APPID`, or local `project.private.config.json`
  to provide the real AppID.

The generated mini program uses `TARO_APP_API_BASE_URL` at compile time, so
changing domains requires a rebuild.

## QA

Known local warnings:

- Taro H5 currently reports an entrypoint size warning. It does not block local validation, but should be optimized before production submission.
- Dependency audit warnings come from the current Taro/webpack chain and should be reviewed during hardening.
