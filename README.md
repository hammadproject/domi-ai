# Domi: US Real Estate AI Chatbot

Portfolio project with a strict $0 running cost (free tiers only). See `plan.md` for the full build plan.

## Backend setup (Phase 1)

```
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy ..\.env.example ..\.env       # then fill in DATABASE_URL, REDIS_URL, GEMINI_API_KEY
.venv\Scripts\alembic upgrade head
.venv\Scripts\python run.py        # http://localhost:8000/health
.venv\Scripts\pytest
```

Notes:
- Use `redis://` or `rediss://` in `REDIS_URL` depending on whether your provider uses TLS.
- Start the server with `python run.py`, not plain `uvicorn`: psycopg async cannot use Windows' default event loop.
- `/health` checks Postgres (+ pgvector), Redis and that an LLM key is configured. It never calls Gemini.

## Try retrieval (Phase 3)

```
cd backend
.venv\Scripts\python -m app.rag.cli "3 bed house in Austin under 500k"   # one-shot
.venv\Scripts\python -m app.rag.cli                                      # conversation, follow-ups keep filters
```

Each query uses 1 Gemini LLM call (parse) + 1 embedding call. The reranker runs locally (fastembed, downloads ~90 MB on first use).

## Guardrails and evals (Phase 4B)

Fair Housing guards live in `backend/app/guardrails/` (rules first; the LLM classifier only runs for ambiguous input and fails closed). Run the eval from `backend/`:

```
.venv\Scripts\python -m evals.run_evals guardrails                  # 30 steering + 30 normal prompts, plus output set
.venv\Scripts\python -m evals.run_evals guardrails --set heldout    # prompts the rules were NOT tuned on
.venv\Scripts\python -m evals.run_evals guardrails --no-llm         # rules only, zero Gemini calls
```
