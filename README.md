# GridSight — team repo

## Golden rules
1. Contract first: `contracts/sample/*.json` are the source of truth for all JSON files.
2. Stay in your folder: `ml/` (Member 1), `backend/` (Member 2), `frontend/` (Member 3). Contract changes need all three approvals.
3. Use the word "house", never "community".
4. The chat AI only explains pre-computed results; it never computes forecasts.
5. No secrets in Git. Keys live in `.env` (git-ignored). See `.env.example`.
6. All times ISO-8601 tz-aware, display zone `Australia/Sydney`, internal storage UTC. Units kW, 1 slot = 30 min, 48 slots = 24 h.

## Layout
```
gridsight/
├── contracts/sample/   # shared JSON contracts
├── data/               # raw + processed data (git-ignored)
├── runs/               # one folder per forecast run (git-ignored)
├── ml/                 # Member 1
├── backend/            # Member 2
├── frontend/           # Member 3
└── docs/
```

## Backend quick start
```
pip install -r requirements.txt
uvicorn backend.main:app --reload   # http://localhost:8000/docs
pytest backend/tests -q
python -m backend.replay --start 2013-02-10 --days 7
```
