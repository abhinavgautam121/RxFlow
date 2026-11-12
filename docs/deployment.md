# Run, develop and deploy

## Docker Compose

```bash
cp .env.example .env
# Set ADMIN_API_KEY to a long random value in .env.
docker compose up --build -d
docker compose ps
docker compose logs -f backend
```

Use http://localhost:8080, with API docs at http://localhost:8000/docs. Database and API ports bind to loopback. Demo credentials in `.env.example` are for local use. An empty ADMIN_API_KEY disables imports. Never commit `.env` or trained joblib files.

First startup migrates the database, seeds only when orders are absent, trains only when the model artifact is absent, and records initial active-shipment predictions. Later starts preserve data. The seed command itself refuses to overwrite a non-empty order table. Schema changes require Alembic migrations; model retraining is an explicit command.

```bash
docker compose exec backend python -m app.ml
docker compose exec backend python -m pytest -q
docker compose exec backend alembic current
docker compose down
```

The generator is configurable through SEED_ORDERS (default 30000). For an initial smaller demo set SEED_ORDERS=3000 **before first startup**. Changing it later does not replace existing data. CLI `python -m app.seed --orders 3000 --seed 42 --days 180` is available only for an empty migrated database; at least 300 eligible completions with both classes are needed for model evaluation.

For a host-port conflict set `RXFLOW_DB_PORT`, `RXFLOW_API_PORT` or `RXFLOW_WEB_PORT` in `.env`. Internal Compose ports and service names remain stable. Default API URL in the browser is same-origin `/api/v1`, handled by Nginx or the Vite proxy.

## Native development

Requires Python 3.11+, Node.js 22 and an available PostgreSQL 16 service. Start only the database with `docker compose up -d db` if needed.

```bash
python -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cd backend
cp ../.env.example .env
# Update DATABASE_URL and ADMIN_API_KEY in backend/.env if necessary.
../.venv/bin/alembic upgrade head
../.venv/bin/python -m app.bootstrap
../.venv/bin/uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open the URL Vite prints (normally http://localhost:5173). On Windows, activate `.venv\Scripts\activate` and use `python`, `alembic`, and `uvicorn` instead of POSIX venv paths.

## Configuration

| Variable | Purpose |
|---|---|
| DATABASE_URL | PostgreSQL SQLAlchemy/psycopg DSN |
| ADMIN_API_KEY | X-Admin-Key value for imports; blank disables writes |
| SEED_ORDERS | First-run synthetic order count |
| MODEL_DIR | Local joblib/report directory; Compose uses a named volume |
| CORS_ORIGINS | Comma-separated development browser origins |
| POSTGRES_USER / PASSWORD / DB | Local Compose database settings |
| RXFLOW_DB_PORT / API_PORT / WEB_PORT | Host port overrides |

## API examples

```bash
curl -f 'http://localhost:8000/api/v1/overview?city=Bengaluru'
curl -f 'http://localhost:8000/api/v1/shipments?status=OVERDUE&page=1&page_size=25'
curl -f 'http://localhost:8000/api/v1/templates/zones' -o zones_template.csv
curl -f 'http://localhost:8000/api/v1/exports/quality' -o quality.csv
curl -f -X POST http://localhost:8000/api/v1/scenarios \
  -H 'Content-Type: application/json' \
  -d '{"scenario_type":"dispatch_improvement","scenario_name":"Two-hour pilot","percentage":20,"hours_reduced":2}'
```

Import requests are multipart (`file`) with a `table` query parameter and X-Admin-Key header. Use a secret-aware client or the UI rather than putting a real key into shell history. Templates use timezone-aware ISO timestamps, nonnegative finite quantities, fictional IDs and exact model columns. Foreign-key master data must already exist.

## Production path

The provided Compose setup is a local portfolio deployment. Before widening access, add user authentication/roles, restrict scenario writes, configure TLS/reverse-proxy policy, provision managed PostgreSQL and backups, define retention, set resource limits and schedule ingestion/model training outside web startup. Do not import patient or prescription data into this demonstration.

Dockerfiles support an optional BuildKit `proxy_ca` secret for development environments using an HTTPS inspection CA. It is never copied into the image. Ordinary developer builds need no proxy secret. Keep TLS verification enabled.
