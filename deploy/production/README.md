# Production Deployment

This deployment runs the API, PostgreSQL, Redis and Caddy on one small server.

For mainland servers where Docker Hub is slow or blocked, use the systemd
deployment:

- PostgreSQL, Redis and Nginx from apt.
- FastAPI in `/opt/world-cup-prediction/services/api/.venv`.
- `worldcup-api.service` for the API.
- systemd timers for `daily_00`, `daily_12` and `weekly` refresh cadences.

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
