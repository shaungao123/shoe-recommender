# Shoe Recommender

Basketball-shoe recommendations from playstyle, budget, and aesthetic. Specs and reviews are scraped into Postgres, embedded with OpenAI, and retrieved with pgvector; a FastAPI layer and Next.js UI sit on top.

Today the **data pipeline**, **embedding index**, **retrieval path**, and **shoes browse API** are in place. Recommend/feedback endpoints and the LLM explainer are still stubs. The frontend UI flow exists but is not fully wired to the backend yet.

## Architecture

```
scrapers (×4) → staging JSON → upsert → Postgres (shoes)
                                              ↓
                                    embed corpus → embeddings (pgvector)
                                              ↓
                         FastAPI /api/shoes (+ /recommend, /feedback stubs)
                                              ↓
                              Next.js frontend ("The Assist")
```

| Layer | Status |
|-------|--------|
| Scrapers + entity resolution | Working |
| Staging corpus + Postgres upsert | Working |
| Schema (`shoes`, `embeddings` + pgvector) | Working |
| Embedding client (OpenAI `text-embedding-3-small`) | Working |
| Corpus embed job (`pipeline/embed`) | Working |
| RAG retriever + budget filter + no-vector fallback | Working |
| FastAPI `GET /api/health`, `GET /api/shoes`, `GET /api/shoes/{id}` | Working |
| Recommend + feedback APIs + LLM explainer | Stub |
| Frontend (intake → results UX) | Scaffolded — screens exist; API client / recommend wiring incomplete |

## Stack

- **API:** FastAPI + Uvicorn
- **DB:** Supabase Postgres (SQLAlchemy 2 + Alembic); `pgvector` for 1536-dim embeddings (`text-embedding-3-small`)
- **Embeddings:** OpenAI Embeddings API via shared `EmbeddingClient` (index + query time)
- **Pipeline:** httpx, BeautifulSoup4, lxml
- **Frontend:** Next.js 16 + React 19 + Tailwind CSS 4
- **Config:** pydantic-settings (`.env`)

## Project layout

```
backend/
  app/              # FastAPI app, shoes routes, RAG services
  shared/           # config, ORM models, embedding client
  pipeline/         # scrapers, normalize, staging, upsert, embed
  alembic/          # migrations
  tests/            # pipeline, API, services, shared (offline fixtures)
frontend/
  app/              # Next.js App Router entry
  components/       # RecommenderFlow + screens (home → intake → results)
```

Pipeline details live in [`backend/pipeline/README.md`](backend/pipeline/README.md).

## Quick start

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Set DATABASE_URL to your Supabase Postgres URL (sslmode=require)
# Set OPENAI_API_KEY for corpus embed + query-time retrieval

make migrate   # apply shoes + embeddings schema
make dev       # http://127.0.0.1:8000/api/health  ·  /docs
```

### Frontend

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev    # http://localhost:3000
```

`NEXT_PUBLIC_USE_MOCK_API=true` (default in `.env.example`) keeps the UI on placeholder picks until the recommend API is live. Point `NEXT_PUBLIC_API_URL` at the FastAPI server when wiring real calls.

### Env vars

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `sqlite:///./shoe_recommender.db` | Use Postgres for upsert, pgvector, and embed |
| `EMBEDDING_MODEL_ID` | `text-embedding-3-small` | Must match index and query |
| `OPENAI_API_KEY` | _(empty)_ | Required for `pipeline.embed` and vector retrieval |

### Data pipeline

Scrapers are offline/scheduled tools — never run them on the request path.

```bash
python -m pipeline.run --pilot                 # ~30 shoes in ≥2 sources
python -m pipeline.run                         # full crawl
python -m pipeline.run --source runrepeat --limit 10

python -m pipeline.upsert.writer --dry-run
python -m pipeline.upsert.writer               # requires Postgres DATABASE_URL

python -m pipeline.embed.embed_corpus --dry-run
python -m pipeline.embed.embed_corpus          # requires Postgres + OPENAI_API_KEY
```

**Sources:** basketballshoespecs, RunRepeat, The Hoops Geek, WearTesters. Staging output lands in `pipeline/staging/` (gitignored).

### Tests

```bash
cd backend
python -m pytest tests/
# or narrower:
python -m pytest tests/pipeline tests/api tests/services tests/shared
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
| `GET` | `/api/shoes` | Live — browse with filters (`brand`, `budget_min`/`budget_max`, `outdoor`, `playstyle`, `cut`, `width`, `position`, pagination) |
| `GET` | `/api/shoes/{id}` | Live — full shoe detail (specs + `extra_metadata`) |
| `POST` | `/api/recommend` | Planned — playstyle / budget / aesthetic → top-3 with explanations |
| `POST` | `/api/feedback` | Planned — thumbs up/down |

Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) when the server is running.

## Roadmap (rough)

1. Wire `POST /recommend` (retriever → LLM explainer → top-3) and `POST /feedback`
2. Finish frontend API client and point the flow at live recommend/feedback
3. Affiliate / live price feed (`affiliate_url` is always null today)
