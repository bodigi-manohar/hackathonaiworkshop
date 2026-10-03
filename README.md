# GridSight — Short-Term Energy Demand Forecasting Agent

Problem 27: energy demand forecasting for utilities. The system forecasts the next 24 hours
(48 half-hour slots) of electricity demand at **portfolio / zone / house** level with
P10–P50–P90 uncertainty bands, backed by a walk-forward validated ensemble. Everything is
advisory only — the LLM explains pre-computed results and never calculates numbers.

## Golden rules

1. Contract first: `contracts/sample/*.json` are the source of truth for every JSON file.
2. Stay in your folder: `ml/` (Member 1), `backend/` (Member 2), `frontend/` (Member 3).
   Contract changes need all three approvals.
3. Use the word **house**, never "community".
4. The chat AI only explains pre-computed results.
5. No secrets in Git — `.env` is git-ignored, see `.env.example`.
6. Times are tz-aware, display `Australia/Sydney`, internal UTC; unit kW; 1 slot = 30 min;
   48 slots = 24 h.

## Layout

```
gridsight/
├── contracts/sample/   # shared JSON contracts (full 48-point samples)
├── data/               # raw + processed data (git-ignored)
├── runs/               # one folder per forecast run (git-ignored)
├── ml/                 # Member 1 — data, features, models, backtest, run bundles
├── backend/            # Member 2 — FastAPI, alerts, optimizer, chat, scheduler
├── frontend/           # Member 3 — dashboard
├── reports/            # walk-forward report, metrics, results.xlsx, data quality
└── docs/               # PRD, role docs, DATA_SCHEMA.md, RESULTS.md
```

## Member 1 (`ml/`) quick start

```bash
pip install -r requirements.txt
export GRIDSIGHT_RAW_CSV=/path/to/Ausgrid_Community_Final.csv   # or put it at data/raw/

python -m ml.data                                  # tidy parquet + QC + docs/DATA_SCHEMA.md
python -m pytest ml/tests -q                       # leakage, aggregation, contract tests
python -m ml.backtest                              # walk-forward -> reports/, docs/RESULTS.md, results.xlsx
python -m ml.train --train-end 2013-02-01          # final models (leakage-free replay after this date)
python -m ml.run_cycle --origin 2013-02-15T00:00   # run bundle in runs/<run_id>/

# faster while iterating:
python -m ml.backtest --levels portfolio,zone
```

**Weather note:** the Kaggle dataset's weather columns are mislabeled (e.g. `T2M` held radiation).
`ml/data.py` detects implausible ranges and rebuilds `T2M/QV2M/PS/WS10M/T2MWET/PRECTOTCORR` from the
Open-Meteo archive for Sydney (cached under `data/cache/weather/`), so features, accuracy and the
explain context stay honest.

### Verified results (walk-forward, oracle weather)

| Level | Ensemble MAE | Skill vs seasonal-naive | P10–P90 coverage |
|---|---|---|---|
| Portfolio | 18.79 kW | 0.280 | 77.5% |
| Zone | 2.98 kW | 0.248 | 78.9% |
| House | 1.79 kW | 0.236 | 79.3% |

Full tables: `reports/backtest.md`, `reports/results.xlsx`, `docs/RESULTS.md`.

## Member 2 (`backend/`) quick start

```bash
uvicorn backend.main:app --reload    # http://localhost:8000/docs
pytest backend/tests -q
python -m backend.replay --start 2013-02-10 --days 7
```

The API reads `runs/<run_id>/` (written by `ml.run_cycle`); if `runs/` is empty it serves
`contracts/sample/` in mock mode.

## Run bundle (what Members 2 & 3 consume)

`runs/<run_id>/`: `forecast.json` (portfolio), `forecast_zone_*.json`, `forecast_house_*.json`,
`explain_context.json`, `metrics.json`, `run_meta.json`, `entities.json`.
48 points, unit kW, `p10 <= p50 <= p90`, timestamps in Australia/Sydney.

## Contribution workflow

| Member | Folder | Branch |
|---|---|---|
| 1 (Manohar) | `ml/` | `m1-ml` |
| 2 (Chaitu) | `backend/` | `m2-backend` |
| 3 | `frontend/` | `m3-frontend` |

```bash
git clone https://github.com/bodigi-manohar/hackathonaiworkshop.git
cd hackathonaiworkshop
git checkout -b m2-backend          # use your own branch
# ...work inside your folder...
git add backend/
git commit -m "m2: add /forecast endpoint"
git push -u origin m2-backend
```

Merge into `main` at sync points (S0–S4). Never edit another member's folder. `data/`, `runs/` and
`models/` are git-ignored; `reports/` and `docs/` are committed.