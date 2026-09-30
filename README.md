# US Real Estate AI Chatbot

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
