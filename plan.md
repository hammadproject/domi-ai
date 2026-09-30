# US Real Estate AI Chatbot: Build Plan (for Claude Code)

Advanced conversational home-search chatbot for the **US market**, on a website with listing pages, a synced map and a streaming chat UI. Portfolio project, built to production-quality standards with a **$0 total running cost** (free tiers and open-source only).

---

## 0. Working rules for Claude Code

- Build **phase by phase** (Section 9). Finish a phase, run its tests, commit, then move on.
- **Zero-cost rule:** use only free tiers / open-source. Never add a paid service or a card-required signup. Ask before adding any dependency not listed in Section 2.
- **RentCast free tier = 50 requests/month.** NEVER call the live API if a cached response exists in `data/raw/`. The ingestion script must check the cache first and log every live call. Total budget: ~3 calls for initial pull, rest reserved.
- **Gemini free-tier quota is limited** (requests per minute and per day; limits change, check current docs). Design for few LLM calls per chat turn (see 5.0), cache aggressively, retry 429s with backoff, and never run evals in a tight loop.
- No invented data. The chatbot answers **only** from retrieved listings / tool outputs.
- Secrets only via env vars (`.env`, never committed). Provide `.env.example`.
- Do not send personal data to the LLM. Free-tier Gemini traffic may be used by Google to improve its products.
- Small, typed, tested functions. Python 3.11+, type hints, Pydantic v2, `ruff` for lint.

## 1. Scope

1. Natural-language home search (hybrid search + rerank), with follow-up refinement
2. US mortgage / affordability tools
3. Listing comparison (2 to 3 homes)
4. Map + chat sync (chat results highlight map pins)
5. Fair Housing guardrails (input and output)
6. Session conversation memory (budget, city, beds, etc.)
7. Production-ready backend: validation, rate limiting, caching, structured logging, tracing, health checks, automated tests

Design notes (not features): no crime or demographic data anywhere (Fair Housing steering risk). Keep the architecture open for a future neighborhood tool.

## 2. Tech stack (final, all free)

| Layer | Choice | Cost |
|---|---|---|
| Frontend | Next.js (App Router) + TypeScript + Tailwind; Leaflet + OpenStreetMap | Free |
| Backend | FastAPI (REST + SSE), Pydantic v2, SQLAlchemy 2 + Alembic | Free |
| Orchestration | LangGraph | Free |
| Database | Postgres + pgvector (Neon free tier; Supabase free is the alternative) | Free |
| Cache / rate limit | Redis (Upstash free tier, or local Redis in dev) | Free |
| LLM | **Gemini 3.1 Flash Lite** via Google AI Studio free API key (`google-genai` SDK). Model name comes from env; verify the exact model id in current docs (may carry a `-preview` suffix) | Free |
| Embeddings | **Gemini embeddings, free tier** (`gemini-embedding-001` or the current free Gemini embedding model; verify in docs). Set a fixed output dimension (default 768) and use the same value for the pgvector column | Free |
| Reranker | Local cross-encoder, no API. Default `cross-encoder/ms-marco-MiniLM-L-6-v2` (small, fits free hosts). `BAAI/bge-reranker-base` optional locally for better quality. Paid Cohere option removed | Free |
| Tracing | Langfuse (Hobby free cloud tier, or self-hosted) | Free |
| Tests | pytest, pytest-asyncio, httpx TestClient | Free |
| Hosting (later) | Vercel Hobby (frontend), Render free web service (backend), Neon (DB), Upstash (Redis) | Free |

Approved new dependency: `google-genai`. Note: a provider abstraction stays (thin `llm/` client interface) so the model can be swapped later, but only Gemini is implemented.

Free-hosting caveats to document in the README: Render free services sleep after inactivity (cold start of ~30 to 60 s) and have ~512 MB RAM, which is why the small reranker is the default in deployment. If `sentence-transformers`/torch is too heavy for the host, use an ONNX-based reranker (e.g. `fastembed`), ask before adding it.

## 3. Repo structure

```
realestate-ai/
  plan.md
  .env.example
  data/raw/                  # cached RentCast JSON (gitignored except samples)
  backend/
    app/
      main.py
      config.py              # pydantic-settings
      db.py
      models.py              # SQLAlchemy models
      schemas.py             # Pydantic schemas
      llm/                   # gemini client wrapper: retries, backoff, cache, quota-aware
      ingestion/             # rentcast client, normalize, load, embed
      rag/                   # query_parser, retrieval, fusion, rerank, generate
      tools/                 # mortgage.py, compare.py
      guardrails/            # input_guard.py, output_guard.py, rules.py
      agent/                 # langgraph graph, router, memory
      api/                   # routes: listings, chat, health
      observability/         # langfuse, logging setup
    tests/
    evals/                   # retrieval_set.jsonl, guardrail_set.jsonl, run_evals.py
    alembic/
  frontend/
```

## 4. Data layer

### 4.1 RentCast ingestion
- Endpoint: `GET https://api.rentcast.io/v1/listings/sale` with header `X-Api-Key`. **Verify params against the current RentCast docs before coding.**
- Cities: **Austin TX, Dallas TX, Phoenix AZ**. Params: `city`, `state`, `status=Active`, `limit=100`. Target ~300 listings total.
- Flow: call API (only if not cached) → save raw JSON to `data/raw/{city}_{date}.json` → normalize → upsert into Postgres.
- Normalization: consistent types, handle missing beds/baths/sqft, parse address, keep lat/lng, property type, HOA fee, year built, listing id (unique key), description/features.
- Idempotent upsert on listing id. Script: `python -m app.ingestion.run --city Austin --state TX`.

### 4.2 Schema (initial)
`listings`: id (pk), address, city, state, zip, lat, lng, price, beds, baths, sqft, lot_size, year_built, property_type, hoa_fee, description, features (jsonb), listing_card (text), embedding (vector(EMBEDDING_DIM)), tsv (tsvector), raw (jsonb), created_at, updated_at.

Indexes: btree on (city, price, beds), GIN on `tsv`. No HNSW index needed at ~300 rows (exact search).
Neon free storage is small (~0.5 GB): ~300 rows with 768-dim vectors is tiny, fine.

### 4.3 Listing card + embeddings
- Build `listing_card`, one natural-language string per listing, e.g. "3 bed, 2 bath house in Austin TX 78704, $525,000, 1,800 sqft, built 2015, HOA $80/mo. <description>".
- Embed `listing_card` with the Gemini embedding model (document/retrieval task type for listings, query task type for user queries, if the API supports it). Batch calls, respect rate limits, and **cache embeddings by content hash** so re-runs cost zero quota. Store in `embedding`.

## 5. RAG pipeline

### 5.0 LLM call budget (free-tier friendly)
Target **at most 2 LLM calls per chat turn** in the normal path:
1. One structured call that does **routing + query understanding** together (intent + filters + semantic query).
2. One grounded generation call.
Guardrails are **rules-first**: the input guard uses regex/keyword rules and only calls the LLM classifier for ambiguous cases; the output guard is rule-based first with an LLM rewrite only when a rule trips. Cache parse results in Redis by normalized message + session filters.

### 5.1 Pipeline
1. **Query understanding**: LLM structured output (Pydantic) → `{filters: {city, state, price_min, price_max, beds_min, baths_min, sqft_min, property_type, ...}, semantic_query: str}`. Merge with prior session filters for follow-ups ("raise budget" only changes `price_max`).
2. **Metadata pre-filter** (SQL) on the parsed filters.
3. **Vector search** (pgvector cosine) on the filtered set, top 30.
4. **Keyword search** (Postgres full-text on `tsv`), top 30. Catches exact terms ("pool", "78704").
5. **Reciprocal Rank Fusion** to merge both lists.
6. **Rerank** top 20 with the local cross-encoder, return top 5.
7. **Zero-result fallback**: relax one filter at a time (price +10%, beds -1, then drop secondary filters), re-query, and tell the user exactly what was relaxed. If still nothing, say so honestly.
8. **Grounded generation**: LLM receives only the retrieved listing records. Output schema: `{answer: str, listing_ids: [str]}`. Every claim must trace to a listing field. Validate that all `listing_ids` exist in the retrieved set; drop the rest.

## 6. Tools

### 6.1 Mortgage / affordability (`tools/mortgage.py`, pure Python, deterministic, NOT LLM math)
- Monthly payment = principal and interest (standard amortization formula) + property tax + homeowners insurance + HOA + PMI.
- PMI applies only when down payment < 20%. Tax rate, insurance and PMI rate are **configurable assumptions** (defaults in config, clearly labeled as estimates in responses).
- Interest rate: fixed editable default (no live-rates API, keeps it free).
- Features: down payment scenarios, 15 vs 30 year comparison, "how much house can I afford" from income, monthly debts and down payment using configurable DTI limits.
- Always present results as estimates, not a loan offer.

### 6.2 Listing comparison (`tools/compare.py`)
- Input: 2 to 3 listing ids → price, price per sqft, beds/baths, sqft, year built, HOA, estimated monthly payment, plus pros/cons derived from fields only.

## 7. Fair Housing guardrails

Goal: never steer users by protected classes (race, color, religion, sex, disability, familial status, national origin), and never use biased language.

- **Input guard**: rules first, small LLM classifier only for ambiguous cases (saves quota). If the user asks for areas "best for [group]" or to avoid/prefer areas by protected class, refuse politely and redirect to objective criteria (price, size, features, commute).
- **Output guard**: rule-based check of the drafted answer for steering or subjective neighborhood claims ("safe", "family-friendly", "good for young professionals"); rewrite or block.
- Do not add crime or demographic data anywhere.
- Log every guardrail trigger (trace + counter). Guardrail eval set is a release gate (Section 10).

## 8. Agent and API

### 8.1 LangGraph graph
`input_guard` → `router` → one of {`search` (RAG), `mortgage_tool`, `compare_tool`, `smalltalk/general`} → `generate` → `output_guard` → stream.
(Router and query parsing share one LLM call, see 5.0.)
State: session id, message history, merged filters, last result ids. Memory stored per session (Redis or Postgres table), with TTL.

### 8.2 Endpoints
- `GET /health` (DB + Redis + LLM config check; must not spend LLM quota)
- `GET /api/listings` (filters, pagination, sort), `GET /api/listings/{id}`
- `POST /api/chat` (SSE stream): events `token`, `listings` (structured payload of ids + coords for map), `done`, `error`
- `POST /api/mortgage/estimate` (direct calculator endpoint for UI use)

### 8.3 Production backend requirements
- Pydantic validation on every input; consistent error schema
- Rate limiting per IP/session (Redis), 429 with `Retry-After`. Also a global daily LLM-call counter so the app degrades gracefully ("high demand, try again later") before Gemini's quota is exhausted
- Redis caching for listing queries and repeated LLM-parse results
- Structured JSON logging with request id; Langfuse trace per chat request (spans per graph node)
- Timeouts and retries with exponential backoff on LLM/embedding calls (honor 429 retry hints); graceful failure messages
- CORS config, env-based settings, no secrets in logs
- Alembic migrations

## 9. Build phases (with acceptance criteria)

**Phase 1: Setup.** Repo skeleton, config, `.env.example`, Neon Postgres (with pgvector extension) and Redis (Upstash or local) connected, Alembic initial migration, `/health`. *Done when:* `/health` returns OK and migrations apply cleanly.

**Phase 2: Ingestion.** RentCast client with cache-first logic, normalize, upsert, listing cards, Gemini embeddings with content-hash cache. *Done when:* ~300 listings across 3 cities in DB with embeddings; re-running makes zero live RentCast calls and zero embedding calls.

**Phase 3: Retrieval.** Query parser, hybrid search, RRF, rerank, fallback logic, as a standalone `rag/` module with a CLI to try queries. *Done when:* sample queries return sensible top 5, filters are strictly respected, zero-result fallback works.

**Phase 4: Tools.** Mortgage calculator and comparison with unit tests. *Done when:* tests pass for known payment examples and edge cases (0% down, PMI threshold, zero HOA).

**Phase 5: Guardrails.** Input/output guards and eval set (30 steering + 30 normal prompts). *Done when:* steering prompts refused, normal prompts pass, pass rate reported.

**Phase 6: Agent and chat API.** LangGraph graph, session memory, SSE endpoint, Langfuse tracing. *Done when:* multi-turn conversation works ("3 bed in Austin under 500k" then "make it 550k" then "monthly payment for the first one").

**Phase 7: Backend hardening.** Rate limiting, daily quota guard, caching, logging, error handling, timeouts. *Done when:* 429 and 422 paths tested, logs carry request ids, traces visible in Langfuse.

**Phase 8: Frontend.** Listing grid + detail, filters, Leaflet map with pins, streaming chat panel, chat-to-map sync (listing ids highlight pins, pin click sends context to chat), responsive, loading and empty states, consistent design system. *Done when:* full flow works on desktop and mobile.

**Phase 9: Tests and evals.** Complete test suite and eval runner (Section 10). *Done when:* all deterministic tests green, eval report generated.

**Phase 10: Deploy and docs.** Frontend on Vercel, backend on Render free, DB on Neon, Redis on Upstash, production env vars, README with architecture diagram, demo GIF, eval results, free-tier limitations (cold starts, Gemini quota, RentCast 50 calls). *Done when:* public URL works end to end at $0.

## 10. Testing and evals

**A) Deterministic tests (`pytest`, no real LLM calls)**
- Mortgage calculator: known examples and edge cases
- Normalization: saved RentCast JSON → correct rows; missing fields handled
- Search filters on a small seed DB (10 to 20 fake listings): only matching listings returned; no-match path
- API: invalid input → 422, rate limit → 429, health → 200
- Router/tools with mocked LLM and mocked RentCast (use cached JSON)

**B) LLM evals (`backend/evals/run_evals.py`, run on demand, results logged to Langfuse)**
- Retrieval set: 30 to 50 questions with known correct listing ids → hit@5, MRR
- Guardrail set: steering vs normal prompts → pass rate (target: 100% on steering refusals)
- Faithfulness: answers contain no fields absent from the retrieved listings
- Quota-aware: throttle requests, cache responses, and allow resuming a partial run so evals fit inside the free daily limit.

Re-run evals after any prompt, model, or retrieval change.

## 11. Environment variables (`.env.example`)

```
DATABASE_URL=            # Neon connection string
REDIS_URL=               # Upstash or local
RENTCAST_API_KEY=
GEMINI_API_KEY=          # Google AI Studio free key (LLM + embeddings)
LLM_MODEL=               # Gemini 3.1 Flash Lite model id (verify exact name in docs)
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIM=768
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
LLM_DAILY_CALL_LIMIT=    # app-level guard below the Gemini free quota
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=
DEFAULT_INTEREST_RATE=
PROPERTY_TAX_RATE_DEFAULT=
HOME_INSURANCE_ANNUAL_DEFAULT=
PMI_RATE_DEFAULT=
RATE_LIMIT_PER_MINUTE=
```

## 12. Definition of done

- All phases' acceptance criteria met; deterministic tests green
- Eval report: retrieval hit@5 and MRR recorded, guardrail pass rate recorded
- Chat answers cite listing ids; map pins sync with results
- Total running cost is $0 (only free tiers used)
- README documents architecture, setup, data source limits (RentCast free tier, Gemini free quota, free-host cold starts), and the deliberate exclusion of crime/demographic data
