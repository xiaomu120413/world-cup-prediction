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

Local H5 static preview after build:

```bash
cd dist
python -m http.server 4173
```

Open:

```text
http://127.0.0.1:4173
```

WeChat DevTools import path:

```text
apps/miniapp/dist-weapp
```

## QA

Known local warnings:

- Taro H5 currently reports an entrypoint size warning. It does not block local validation, but should be optimized before production submission.
- Dependency audit warnings come from the current Taro/webpack chain and should be reviewed during hardening.
