# GridSight — rules for the coding agent

## Hard rules
1. Use the word "house" everywhere. Never "community" in code, columns, docs or UI.
2. The API never computes forecasts. It reads files written into runs/<run_id>/ by ml.run_cycle. Default run is the latest run; if runs/ is empty, serve contracts/sample (mock mode).
3. The LLM receives only explain_context.json plus the user question. It cannot call tools or change state. Always keep a template fallback.
4. Control is disabled and dry-run by default. Anything that can actuate must pass guardrails and be logged. POST /control/override disables control immediately and persists the state.
5. No secrets in the repo. Read keys from environment variables (.env, git-ignored).
6. Outputs are advisory. Plan mode is "advisory"; tariff/battery values are assumptions and must be labelled as such.
7. All file paths come from config (backend/config.yaml + settings), relative to the project root. No hardcoded local paths.
8. Times are tz-aware; display Australia/Sydney, internal UTC.
9. If a response field differs from contracts/sample, fix the code, not the contract.

## Backend conventions
- Python 3.11+, FastAPI, Pydantic v2, SQLite via SQLAlchemy, APScheduler, pytest, ruff.
- No business logic in endpoints: routes delegate to services.
- After each step: run tests, summarise changes, stop.

## Commands
uvicorn backend.main:app --reload
pytest backend/tests -q
python -m backend.replay --start 2013-02-10 --days 7
