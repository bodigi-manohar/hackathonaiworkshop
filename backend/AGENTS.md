# Backend rules (Member 2)
- Work only inside backend/ (and runs/ for alerts.json and plan.json). Do not edit ml/ or frontend/.
- Python 3.11+, FastAPI, Pydantic v2, SQLite via SQLAlchemy, APScheduler, pytest, ruff.
- No business logic in endpoints: routes delegate to services. Schemas mirror contracts/sample exactly.
- Mock mode: when runs/ is empty, serve contracts/sample so the frontend can build immediately.
- LLM config: LLM_BASE_URL, LLM_API_KEY, LLM_MODEL from .env (OpenAI-compatible chat endpoint).
- Control is disabled and dry-run by default. Override is persisted.
- After each step: run tests, summarise changes, stop.
