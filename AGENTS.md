# GridSight — team rules for the coding agent

Short-term energy demand forecasting agent. Full specs:
`docs/PRD_energy_demand_forecasting_agent.md`, `docs/01_Member1_AI-ML_Manohar.md`,
the other member docs, and the shared JSON contracts in `contracts/sample/`.

## Hard rules (all members)
1. **Contract first.** All outputs must match `contracts/sample/` exactly (field names, 48 points,
   timezone Australia/Sydney, unit kW). If a response field differs, fix the code, not the contract.
2. Stay in your own member folder (`ml/`, `backend/`, `frontend/`). Cross-folder changes only via a
   PR touching `contracts/` approved by all three members.
3. Use the word **house**, never "community", in code, columns, docs or UI.
4. Walk-forward (expanding window) validation only. Never shuffled k-fold, never fit on future data.
5. The LLM only explains pre-computed results (`explain_context.json`). It never computes forecasts
   and has no tools that change state. Always keep a template fallback.
6. Control is disabled and dry-run by default. Anything that can actuate must pass guardrails and be
   logged. `POST /control/override` disables automation immediately and persists the state.
7. No secrets in Git. Keys live in `.env` (git-ignored), see `.env.example`.
8. Outputs are advisory. Tariff / battery / generator values are assumptions and must be labelled.
9. All times tz-aware; store UTC, display `Australia/Sydney`. One slot = 30 min, 48 slots = 24 h.
10. All file paths come from config (`ml/config.yaml`, `backend/config.yaml`), relative to the repo root.

## Backend conventions (Member 2)
- Python 3.11+, FastAPI, Pydantic v2, SQLite via SQLAlchemy, APScheduler, pytest, ruff.
- The API never computes forecasts. It reads `runs/<run_id>/` written by `ml.run_cycle`; the default
  run is the latest; if `runs/` is empty, serve `contracts/sample/` (mock mode).
- No business logic in endpoints: routes delegate to services.

## Commands
```
# Member 1 (ML)
python -m ml.data
python -m ml.backtest
python -m ml.train --train-end 2013-02-01
python -m ml.run_cycle --origin 2013-02-15T00:00

# Member 2 (backend)
uvicorn backend.main:app --reload
pytest backend/tests -q
python -m backend.replay --start 2013-02-10 --days 7
```

## Workflow
- Small, working steps: finish a step, run its check, commit, move on.
- Branch per member (`m1-ml`, `m2-backend`, `m3-frontend`); merge into `main` at sync points S0–S4.