# Basketball-shoe data pipeline

Scrapes complementary sources, normalizes each into a common record shape,
and resolves records across sources into **one canonical shoe per model**
with per-field provenance. Output is a JSON staging corpus for the RAG
engine to embed later — the scrape run never writes to the production
`shoes` table, never generates embeddings, and never fetches live prices
(`affiliate_url` stays null until the affiliate-feed step exists).
Writing the corpus to Postgres is a separate, explicit command (see
"Upsert to Postgres" below).

Scrapers are offline/scheduled tools — never run them in the request path.

## Sources

| module | what it contributes |
|---|---|
| `scrapers/basketballshoespecs.py` | manufacturer specs: cushioning, drop, weight, cut, traction, surface, positions/playstyles |
| `scrapers/runrepeat.py` | independent lab data (stack, drop, traction CoF, softness…), CoreScore, pros/cons |
| `scrapers/thehoopsgeek.py` | scores averaged over many expert reviews, fit/width, outdoor %, "best for" |
| `scrapers/weartesters.py` | long-form review prose per test category, pros/cons, reviewer verdict, category tags |

Planned-but-not-built sources are listed in `scrapers/FUTURE_SOURCES.md`.
RunRepeat sells an official data export (preferred over scraping if we ever
license it) — see the note at the top of `scrapers/runrepeat.py`.

## Run

From `backend/`:

```bash
python -m pipeline.run --pilot               # ~30 shoes seen in >=2 sources
python -m pipeline.run                       # full crawl, all sources
python -m pipeline.run --source runrepeat --limit 10
python -m pipeline.run --refresh             # bypass the HTML cache
```

Every run prints a coverage report (records per source, canonical count,
per-field fill rates) and writes to `pipeline/staging/`:

- `records_<source>.json` — normalized per-source records
- `canonical.json` — merged shoes with `provenance` per field and `sources`
- `unmatched.json` / `ambiguous.json` — records needing a human decision;
  ambiguous = near-identical model keys that were deliberately **not** merged

## Upsert to Postgres

Once the staging corpus looks right, push it to the `shoes` table (from
`backend/`, with migrations applied via `make migrate` and the Postgres
`DATABASE_URL` in `.env` — the writer refuses the SQLite fallback):

```bash
python -m pipeline.upsert.writer             # write staging/canonical.json
python -m pipeline.upsert.writer --dry-run   # report counts, roll back
python -m pipeline.upsert.writer --staging path/to/other.json
```

The writer makes the table match the batch: upserts by `canonical_id`
(idempotent — re-runs update in place, shoe ids stay stable), then deletes
rows not in the batch, including rows without a `canonical_id` (pre-pipeline
mock data). Structured spec fields go to the `specs` JSON column; per-source
`metrics` (never averaged), pros/cons/review text, provenance, and sources go
to `extra_metadata`. `affiliate_url` is always written as null. Embedding
vectors are a separate later step (`pipeline/embed/`).

## Refresh behaviour

Raw HTML is cached in `pipeline/.cache/<source>/` keyed by URL, so re-runs
and tests never re-hit the network. `--refresh` re-downloads. Deleting a
single source's cache dir refreshes just that source.

## Politeness / legal

- `robots.txt` is fetched per domain and honored (disallowed URLs are
  skipped); requests go out with a descriptive User-Agent + contact,
  1 request at a time per domain, ~3–4 s apart, exponential backoff on
  429/5xx honoring `Retry-After`.
- basketballshoespecs.com publishes Cloudflare Content-Signals
  (`ai-train=no, use=reference`): don't use its content for model training;
  RAG answers should cite the source (we keep per-field provenance for this).
- Prices and buy links must come from affiliate feeds, not scraped retail
  pages.

## How entity resolution works (`normalize.py`)

1. Each record gets a canonical brand (alias table: "Air Jordan" → Jordan,
   "Way of Wade" → Li-Ning, …) and a `model_key` — lowercased,
   punctuation-folded ("G.T. Cut 3" ≡ "GT Cut 3"), roman numerals → digits,
   noise tokens ("Performance Review", "EP") dropped. Colorway names never
   reach the key, so colorways collapse into one model.
2. Records sharing `(brand, model_key)` merge into one `CanonicalShoe`.
   Physical specs resolve by source priority (manufacturer specs →
   RunRepeat lab → aggregators), recording provenance per field.
   Per-source scores live under `metrics[<source>]` and are **never
   averaged across sources** (they aren't independent measurements).
3. Near-identical keys within a brand (SequenceMatcher ≥ 0.86, unless their
   trailing version numbers differ) go to `ambiguous.json` for manual
   review instead of being merged by guesswork.

## Adding a new source

1. Create `scrapers/<source>.py` subclassing `BaseScraper`; implement
   `list_shoes()` and `parse(html, url, fetched_at) -> SourceRecord`.
   Retry/rate-limit/caching/robots come free from the base class.
2. Register the class in `scrapers/__init__.py::get_scrapers`.
3. Add its name to `SOURCE_PRIORITY` in `normalize.py` (position = trust
   for physical specs).
4. Save one listing + one detail page under `tests/pipeline/fixtures/` and
   add parse tests. Tests must pass offline.

## Tests

```bash
python -m pytest tests/pipeline
```

All tests run against saved HTML fixtures in `tests/pipeline/fixtures/` —
no network.
