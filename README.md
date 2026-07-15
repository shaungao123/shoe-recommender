# Shoe Recommender

Basketball-shoe recommendation backend. User inputs (playstyle, budget, aesthetic) will drive a RAG retrieval over scraped specs and reviews, returning a top-3 with explanations and storing thumbs up/down feedback.

Today the **data pipeline** (scrape → normalize → upsert) is the mature piece. The FastAPI recommend/feedback layer and frontend are scaffolded or not started yet.

## Architecture

```
scrapers (×4) → staging JSON → upsert → Postgres (shoes + embeddings)
                                              ↓
                                    FastAPI (/api/…)  [recommend/feedback stubbed]
```

| Layer | Status |
|-------|--------|
| Scrapers + entity resolution | Working |
| Staging corpus + Postgres upsert | Working |
| Schema (`shoes`, `embeddings` + pgvector) | Working |
| FastAPI health check | Working |
| Embed corpus / OpenAI client | Stub |
| Recommend + feedback APIs | Stub |
| Frontend | Not started |

## Stack

- **API:** FastAPI + Uvicorn
- **DB:** Supabase Postgres (SQLAlchemy 2 + Alembic); `pgvector` for 1536-dim embeddings (`text-embedding-3-small`)
- **Pipeline:** httpx, BeautifulSoup4, lxml
- **Config:** pydantic-settings (`.env`)

## Project layout

```
backend/
  app/           # FastAPI app, routes, services, RAG stubs
  shared/        # config, ORM models, embedding client stub
  pipeline/      # scrapers, normalize, staging, upsert
  alembic/       # migrations
  tests/         # pipeline tests (offline fixtures)
```

Pipeline details live in [`backend/pipeline/README.md`](backend/pipeline/README.md).

## Quick start

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Set DATABASE_URL to your Supabase Postgres URL (sslmode=require)

make migrate   # apply shoes + embeddings schema
make dev       # http://127.0.0.1:8000/api/health  ·  /docs
```

### Env vars

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `sqlite:///./shoe_recommender.db` | Use Postgres for upsert + pgvector |
| `EMBEDDING_MODEL_ID` | `text-embedding-3-small` | Embedding generation not wired yet |

### Data pipeline

Scrapers are offline/scheduled tools — never run them on the request path.

```bash
python -m pipeline.run --pilot                 # ~30 shoes in ≥2 sources
python -m pipeline.run                         # full crawl
python -m pipeline.run --source runrepeat --limit 10

python -m pipeline.upsert.writer --dry-run
python -m pipeline.upsert.writer               # requires Postgres DATABASE_URL
```

**Sources:** basketballshoespecs, RunRepeat, The Hoops Geek, WearTesters. Staging output lands in `pipeline/staging/` (gitignored).

### Tests

```bash
python -m pytest tests/pipeline
```

### Makefile

| Target | What it does |
|--------|----------------|
| `make dev` | Uvicorn with reload on `app/` + `shared/` |
| `make migrate` | `alembic upgrade head` |
| `make migrate-new msg="…"` | Autogenerate a new revision |

## API (current)

| Method | Path | Status |
|--------|------|--------|
| `GET` | `/api/health` | Live — `{"status":"ok"}` |
| `POST` | `/recommend` | Planned — playstyle / budget / aesthetic → top-3 |
| `POST` | `/feedback` | Planned — thumbs up/down |

## Roadmap (rough)

1. Embedding client + `pipeline/embed` batch job
2. Wire recommend/feedback routes (RAG + hard filters + LLM explanations)
3. Frontend for the recommendation UX
4. Affiliate / live price feed (`affiliate_url` is always null today)
