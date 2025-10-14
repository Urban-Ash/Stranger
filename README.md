<div align="center">

<h1>Stranger · OSINT 信息检索平台</h1>

[中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md)

<br/>

<img src="https://img.shields.io/badge/AI%20Authored-100%25-blueviolet?style=flat" alt="AI Authored 100%" />
<img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python" alt="Python" />
<img src="https://img.shields.io/badge/Flask-2.x-000?logo=flask" alt="Flask" />
<img src="https://img.shields.io/badge/PostgreSQL-13%2B-336791?logo=postgresql" alt="PostgreSQL" />

<p>An all-in-one OSINT aggregation and search system with multilingual UI, data source templating, validation utilities, and optional AI-assisted confidence assessment.</p>

</div>

## Features
- Smart search: detects query type (name/phone/email/QQ/ID/Weibo UID), supports pagination, sorting, and optional aggregation.
- Multilingual UI: Chinese, English, Traditional Chinese, Japanese, Korean; accessible language menu with ARIA hints.
- Data maintenance: add/edit modals, incremental source updates, record deletion.
- Source detail: click a source chip in results to open a modal with detailed hits.
- Validation queries: phone region, QQ profile, Weibo UID home info, ID-card parsing.
- AI confidence: assess and optionally write back to the main table.
- Health & metrics: unified endpoints for monitoring.

## Screens & UX
- PWA-ready: install to desktop, offline manifest & service worker.
- Dark/Light themes and language switching from the UI.
- Accessible components with keyboard navigation and ARIA labels.

<div align="center">

<img src="docs/screenshots/stranger-home-zh.png" alt="Stranger 首页（中文界面）" width="720" />

<br/>

<img src="docs/screenshots/stranger-home-en.png" alt="Stranger Home (English UI)" width="720" />

</div>

## Architecture
- Frontend: `static/` modular JS, entry `static/main.js`, template `templates/index.html`.
- Backend: Flask app `app/app.py` (`create_app()`), routes `app/api/routes.py`, unified responses in `app/api/response.py`.
- Database: PostgreSQL; main table `profile`, indexes created on startup; cross-table scans and dynamic aliases in `app/models/database.py`.
- Config: centralized `config/config.py` with env injection; CORS, compression, and rate limiting supported.

## Data Sources
- Configure friendly names and dates in `config/data_source.json`.
- The app auto-syncs missing entries from DB metadata when available.
- Template example:
  ```json
  {
    "example_table": { "name": "示例数据源", "date": "YYYY-MM-DD" }
  }
  ```

## Directory
- `app/` backend (API, services, DB models, app init)
- `static/` frontend assets (JS/CSS/icons)
- `templates/` Jinja templates
- `config/` configs and manifest
- `scripts/` helper scripts (smoke test, DB inspect)

## Quick Start
- Requirements: Python 3.9+, PostgreSQL
- Install deps: `pip3 install -r requirements.txt`
- Configure environment: copy `.env.example` to `.env` and set:
  - `FLASK_HOST`, `FLASK_PORT`, `FLASK_ENV`, `CORS_ORIGINS`
  - `PG_HOST`, `PG_PORT`, `PG_DATABASE`, `PG_USER`, `PG_PASSWORD`
  - `SOURCE_DETAIL_STATEMENT_TIMEOUT_MS` (default `60000` ms)
  - Optional proxy & crawler: `CRAWLER_TIMEOUT`, `CRAWLER_RETRIES`, `CRAWLER_BACKOFF`, `HTTP_PROXY`/`HTTPS_PROXY`
- Run dev: `python3 main.py`
- Run production: `gunicorn -w 4 -b 0.0.0.0:5082 app.app:app`

## Access
- Home: `http://127.0.0.1:5082/`
- Health: `http://127.0.0.1:5082/health`
- Metrics: `http://127.0.0.1:5082/api/metrics`

## API Overview
- `GET /api/search`: params `query`; optional `page`, `page_size`, `sort`, `order`, `expand`
- `POST /api/customer`: create record
- `PUT /api/customer/<id>`: update allowed fields
- `DELETE /api/customer/<id>`: delete record
- `GET /api/source_detail`: inspect table hit details by subject keys (`id_card`, `phones`, `qqs`, `weibo_uid`, `email`, `name`)
- Validators:
  - `GET /api/validate/phone`
  - `GET /api/validate/qq`
  - `GET /api/validate/weibo`
  - `GET /api/validate/id_card`
- AI: `POST /api/ai/assess_confidence`
- Introspection: `GET /api/schema_introspect`
- Health & metrics: `GET /health`, `GET /api/metrics`

> Note: For large or privacy-sensitive queries, `/api/search` and `/api/source_detail` can optionally support `POST` JSON bodies (dual-stack design).

## Deployment Examples
**Gunicorn (foreground test)**
- `pip3 install gunicorn`
- `gunicorn -w 4 -b 127.0.0.1:5082 app.app:app`

**Nginx reverse proxy**
```
upstream stranger_app {
    server 127.0.0.1:5082;
}

server {
    listen 80;
    server_name your.domain.com;

    location / {
        proxy_pass http://stranger_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 75s;
        proxy_send_timeout 75s;
    }

    location /static/ {
        proxy_pass http://stranger_app;
    }
}
```

**systemd service**
- Env file: `/etc/stranger/stranger.env` (see `.env.example`)
- Unit: `/etc/systemd/system/stranger.service`
```
[Unit]
Description=Stranger API Service
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/stranger
EnvironmentFile=/etc/stranger/stranger.env
ExecStart=/usr/bin/gunicorn -w 4 -b 0.0.0.0:${FLASK_PORT} app.app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Docker
Build a production image (Python 3.12-slim + Gunicorn):

**Build**
- `docker build -t stranger:latest .`

**Run** (map container 5082 to host 5082)
- `docker run --name stranger -p 5082:5082 --env FLASK_PORT=5082 stranger:latest`

**Notes**
- Default command: `gunicorn -w 4 -b 0.0.0.0:5082 app.app:app`.
- Change host port via `-p <host_port>:<container_port>` and `FLASK_PORT`.
- `.dockerignore` trims image size.

## Security Notes
- Do not commit `.env`; secrets (DB, API keys) are injected via environment.
- Rotate credentials if previously shared; use `.env.example` for placeholders.
- Review CORS origins and rate limit settings before exposing endpoints.

## Docker Compose
Use `docker-compose.yml` for one-command build & run.

- Start: `docker compose up -d --build`
- Logs: `docker compose logs -f stranger`
- Stop: `docker compose down`

Notes:
- Host port from `FLASK_PORT` (default `5082`); mapped to container `5082`.
- Compose reads `.env` automatically; Gunicorn runs `app.app:app` inside the container.

## Performance & Stability Tips
- Prefer index-friendly equality conditions for phone matching; avoid full scans.
- Tune `SOURCE_DETAIL_STATEMENT_TIMEOUT_MS`; maintain expression indexes for common columns.
- Control cross-table scan budgets: `SCAN_MAX_TABLES`, `SCAN_LIMIT_PER_TABLE`, `SCAN_TOTAL_TIME_BUDGET_MS`.
- Connection management: consider pools (`ThreadedConnectionPool`) or request-scoped connections.
- Rate limiting storage: use shared store (e.g., Redis) for multi-replica deployments.
- Logging & observability: structured logs, rotation, proper levels.

## Smoke Test
- `python3 scripts/smoke_test.py` or `python3 scripts/smoke_test.py http://<host>:<port>`
- Covers: `/`, `/api/metrics`, `/api/search`, `/api/source_detail`, `/api/schema_introspect`, `/api/validate/id_card`
- Expected: `PASS (6 passed, 0 failed)`

## Troubleshooting
- 503 / timeouts: check logs for `statement timeout`; increase timeout or optimize queries; ensure indexes.
- Slow cross-table scans: lower budgets or switch to key-based aggregation.
- External requests failing: set proxies and retry configs; verify outbound network policies.

## Contributing & License
- Issues and PRs welcome; run smoke tests and update docs before submitting.
- Licensed under the terms in `LICENSE`.