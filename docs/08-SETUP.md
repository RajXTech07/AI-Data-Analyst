# 08 — Setup Guide

## 1. Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.11+ | `python --version` |
| Node.js | 20+ | `node --version` |
| PostgreSQL | 15+ (or Docker) | `psql --version` |
| Docker + Compose | recent | `docker compose version` |
| Git | any | `git --version` |
| LLM API key | Gemini or OpenAI | from provider console |

## 2. Environment variables

`.env.example` (copy to `.env`, never commit `.env`):

```env
# App
APP_ENV=development
API_PORT=8000
WEB_ORIGIN=http://localhost:3000

# Database
DATABASE_URL=postgresql+psycopg://analyst:analyst@localhost:5432/analyst

# Storage
STORAGE_BACKEND=local            # local | s3
STORAGE_DIR=./storage
MAX_UPLOAD_MB=10

# Auth
JWT_SECRET=change-me-to-a-long-random-string
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=7

# LLM
LLM_PROVIDER=gemini              # gemini | openai
GEMINI_API_KEY=
OPENAI_API_KEY=
LLM_MODEL=                       # set to a current model name from your provider
LLM_MAX_TOOL_CALLS=12
LLM_TIMEOUT_SECONDS=60

# Limits
TOOL_TIMEOUT_SECONDS=30
MAX_ROWS=200000
```

Generate a secret: `python -c "import secrets; print(secrets.token_urlsafe(48))"`

## 3. Option A — Docker (fastest)

```bash
cp .env.example .env
docker compose up --build
docker compose exec api alembic upgrade head
```

`docker-compose.yml` services: `db` (postgres), `api` (FastAPI, port 8000), `web` (Next.js, port 3000).

## 4. Option B — Local development

### Database
```bash
docker run -d --name analyst-db -p 5432:5432 \
  -e POSTGRES_USER=analyst -e POSTGRES_PASSWORD=analyst -e POSTGRES_DB=analyst postgres:15
```

### Backend
```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

`requirements.txt` (core):
```
fastapi
uvicorn[standard]
pydantic>=2
pydantic-settings
sqlalchemy>=2
alembic
psycopg[binary]
pandas
numpy
scipy
scikit-learn
plotly
python-multipart
argon2-cffi
pyjwt
jinja2
weasyprint
httpx
pytest
pytest-asyncio
google-genai          # or: openai
```

### Frontend
```bash
cd apps/web
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` in `apps/web/.env.local`.

## 5. First-run checks

1. `curl localhost:8000/healthz` → `{"status":"ok"}`
2. Open `localhost:8000/docs`, register a user, log in.
3. Upload `datasets/student_sample.csv`.
4. Start an analysis and watch events in the UI.

## 6. Sample datasets

Put under `datasets/`:
- `student_performance.csv` — group comparisons, correlations
- `supermarket_sales.csv` — trends, categories
- `customer_churn.csv` — segmentation
- `synthetic_planted.csv` — generated with known issues (see `12-TESTING-DEBUGGING.md`)

## 7. Deployment

| Part | Platform | Notes |
|------|----------|-------|
| Web | Vercel | set `NEXT_PUBLIC_API_URL` |
| API | Render or Fly.io | Dockerfile, set all env vars, health check `/healthz` |
| DB | Managed Postgres (Neon, Supabase, Render) | run `alembic upgrade head` on deploy |
| Files | S3-compatible bucket | `STORAGE_BACKEND=s3` plus bucket credentials |

Checklist: HTTPS only, CORS limited to `WEB_ORIGIN`, strong `JWT_SECRET`, API keys in platform secrets, upload size limit at proxy and app level, daily DB backup.

## 8. Useful commands

```bash
alembic revision --autogenerate -m "message"   # new migration
alembic upgrade head                            # apply
pytest -q                                       # tests
ruff check . && ruff format .                   # lint/format (add ruff to dev deps)
```

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `connection refused` on 5432 | DB not running | start container, check `DATABASE_URL` |
| CORS error in browser | `WEB_ORIGIN` mismatch | match exact origin |
| 413 on upload | proxy/app limit | raise limits consistently |
| LLM 401/403 | missing/invalid key | check env var and provider |
| PDF generation fails | WeasyPrint system libs | install pango/cairo packages in the image |
| SSE stops after ~60 s | proxy buffering/timeout | disable buffering, send heartbeat comments |
