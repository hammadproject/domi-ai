# Domi: Progress

Last updated: 2026-09-30 · Source of truth for scope: `plan.md` · Repo: https://github.com/hammadproject/domi-ai

## Where to continue

**Next: Phase 7, Backend hardening** (rate limiting, daily LLM quota guard, Redis caching, error schema).
Phase 6 is done and verified, including Langfuse traces (one trace per chat turn, a span per graph node, LLM calls as generations).

Before starting Phase 6:
- Langfuse keys (Hobby cloud tier, free, no card) in `.env`: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`. Optional: the chat can be built first and tracing switched on once the keys exist.
- `langgraph` and `langfuse` are named in plan.md, so they are approved dependencies.

## Status: 6 of 10 phases done (the backend works end to end; hardening, frontend and deploy remain)

| # | Phase | Status | Commit | Notes |
|---|---|---|---|---|
| 1 | Setup | Done | `28aa3cc`, `66f06dc` | `/health` returns 200 (DB, Redis, LLM config); Alembic migration applies, downgrades and re-applies on Neon |
| 2 | Ingestion | Done | `01a6bbc`, `b3ad97c` | 300 listings (100 each Austin, Dallas, Phoenix), all embedded; re-run = 0 RentCast calls, 0 embedding calls |
| 3 | Retrieval | Done | `2b5dc77` | Parser, hybrid search, RRF, local rerank, relax-and-report fallback, CLI |
| 4 | Tools | Done | `11e4887` | Mortgage (PMI, scenarios, 15 vs 30, DTI affordability) and 2-3 listing comparison |
| 5 | Guardrails | Done | `f264e7e` | Input and output guards, eval runner. 60/60 main, 20/20 held-out, 24/24 output |
| 6 | Agent and chat API | Done | see git log | LangGraph agent, Redis session memory, SSE `/api/chat`, `/api/mortgage/estimate` |
| 7 | Backend hardening | Not started | | Rate limiting, daily LLM quota guard, Redis caching, tracing spans |
| 8 | Frontend | Not started | | Next.js + Leaflet, chat-to-map sync |
| 9 | Tests and evals | Partly done | | Guardrail evals exist; retrieval eval (hit@5, MRR) and faithfulness eval still to build |
| 10 | Deploy and docs | Not started | | Vercel, Render, Neon, Upstash; README with architecture and demo |

Everything is pushed to `origin/main` except this file.

## What exists

**Backend (`backend/app/`)**
- `config.py`, `db.py`, `models.py`, `redis.py`, `main.py` (FastAPI, CORS, request-id JSON logging), `api/health.py`
- `ingestion/`: RentCast client (cache-first, logs live calls), normalize (strips agent contact data), Gemini embeddings with on-disk content-hash cache, idempotent upsert, CLI `python -m app.ingestion.run`
- `rag/`: `query_parser`, `retrieval`, `fusion`, `rerank` (fastembed), `pipeline` (with fallback), CLI `python -m app.rag.cli`
- `llm/`: Gemini client wrapper with 429 backoff
- `tools/`: `mortgage.py`, `compare.py`
- `guardrails/`: `rules.py`, `input_guard.py`, `output_guard.py`
- `evals/`: `run_evals.py guardrails` with `guardrail_set.jsonl`, `guardrail_heldout.jsonl`, `guardrail_output_set.jsonl`

**Empty, to be built:** `agent/`, `api/` routes other than health, `frontend/`

**Tests:** 171 passing (`cd backend; .venv\Scripts\pytest`). Ruff clean.

**Data:** Neon holds 300 listings (90 are `Land`). Raw RentCast JSON is cached in `data/raw/` (gitignored).

## Free-tier budget used

- RentCast: 3 successful live calls (one per city) plus 2 failed calls (`403`, before the plan was activated). At most 5 of 50 this month. Cached responses mean no more are needed.
- Gemini: embeddings for 283 listing cards, a handful of test queries and held-out guardrail checks.

## Decisions made

- Reranker: `fastembed` (ONNX) with `Xenova/ms-marco-MiniLM-L-6-v2`, the same model as plan.md but light enough for Render's 512 MB. Approved.
- `Land` listings are excluded from home searches unless the user asks for land.
- Embeddings: `gemini-embedding-001`, 768 dimensions, L2-normalized by us.
- LLM: `gemini-3.1-flash-lite`.
- Project name is Domi (renamed from `realestate-ai`).

## Known limitations and things to watch

- RentCast has no listing descriptions or features. Cards use structured fields only, so keyword search for things like "pool" finds nothing.
- Vague words ("affordable", "cheap") don't sort by price.
- Guardrails: rules alone settle about 5 of 8 unseen steering prompts. The rest rely on the Gemini classifier, and the guard refuses politely when that classifier is unavailable. The 100% on the main set is optimistic because the rules were tuned on it.
- The parse result is not cached in Redis yet (Phase 7). Each chat turn will cost 1 parse call, 1 query embedding and 1 generation call.
- The daily LLM call counter is not built yet (Phase 7).
- Langfuse Cloud stores chat messages and answers in traces. Its legacy `/api/public/traces` API is gone for new orgs; query `/api/public/v2/observations` instead.
- Gemini sometimes returns brief 5xx errors; the LLM wrapper retries them up to 3 times, and chat degrades to a plain result list if generation still fails.

## Local setup gotchas

- Start the server with `python run.py` from `backend/`, not plain `uvicorn`: psycopg async needs a selector event loop on Windows. Alembic and the CLIs handle this themselves.
- `REDIS_URL` must use `redis://` for this provider (not `rediss://`).
- Python 3.14.7 in `backend/.venv`.
- The local folder is still named `real-estate-chatbot`.
- `.env` is gitignored. It holds `DATABASE_URL`, `REDIS_URL`, `GEMINI_API_KEY`, `RENTCAST_API_KEY`. The Gemini key was pasted into a chat, so consider rotating it.
