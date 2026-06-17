# Production Deployment

This deployment runs the API, PostgreSQL, Redis and Caddy on one small server.

For mainland servers where Docker Hub is slow or blocked, use the systemd
deployment:

- PostgreSQL, Redis and Nginx from apt.
- FastAPI in `/opt/world-cup-prediction/services/api/.venv`.
- `worldcup-api.service` for the API.
- systemd timers for `daily_00`, `daily_12`, `weekly`, `post_match` and `pre_match_90m` refresh cadences.

## First Server Setup

```bash
sudo bash deploy/production/server-init.sh
```

Create `/opt/world-cup-prediction/deploy/production/.env.prod` from `.env.example`.

Before DNS is ready:

```text
API_SITE_ADDRESS=:80
```

After DNS points to the server:

```text
API_SITE_ADDRESS=api.example.com
TLS_EMAIL=admin@example.com
```

## Start

```bash
cd /opt/world-cup-prediction/deploy/production
docker compose --env-file .env.prod up -d --build
```

Health check:

```bash
curl http://127.0.0.1/health
```

After DNS and TLS are ready:

```bash
curl https://api.example.com/health
```

## Refresh Timers

Install or update the timer units after deploying a new revision:

```bash
sudo cp deploy/production/systemd/worldcup-refresh@.service /etc/systemd/system/
sudo cp deploy/production/systemd/worldcup-refresh-*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now \
  worldcup-refresh-daily-00.timer \
  worldcup-refresh-daily-12.timer \
  worldcup-refresh-weekly.timer \
  worldcup-refresh-post-match.timer \
  worldcup-refresh-pre-match-90m.timer
```

`post_match` and `pre_match_90m` are frequent event checks. They skip when no target Dongqiudi match is due and only pass scoped `--match-id` values to lineup, feature and prediction jobs. Successful event runs write per-match markers, so overlapping checks during a busy morning do not refresh the same match twice.
